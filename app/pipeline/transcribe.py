"""Gerçek yazıya dökme hattı: faster-whisper (ASR), WhisperX (hizalama), pyannote (konuşmacı ayrımı).

Aşamalar sırayla çalışır ve her aşamadan sonra model bellekten atılır:
yazıya dök -> ASR'yi boşalt -> hizala -> boşalt -> konuşmacıları ayır -> boşalt.
"""
from __future__ import annotations

import logging
import wave
from typing import Callable

import numpy as np

from ..errors import Cancelled, UserError
from ..export.segmenter import seg_words
from . import gpu

log = logging.getLogger("desifre.engine")

MSG_OOM = "GPU belleği yetersiz. Daha küçük bir model deneyin."
MSG_DLL = ("GPU kütüphaneleri yüklenemedi (cuBLAS veya cuDNN). README dosyasındaki sorun giderme bölümüne bakın "
           "ya da Ayarlar sayfasından aygıtı CPU yapın.")
MSG_DOWNLOAD = "Model indirilemedi. İnternet bağlantınızı kontrol edip yeniden deneyin."
PALETTE = ["#3b82f6", "#f97316", "#10b981", "#a855f7", "#ef4444", "#14b8a6", "#eab308", "#ec4899", "#6366f1", "#84cc16"]

Report = Callable[[str, float], None]


def load_wav(path: str) -> np.ndarray:
    with wave.open(path, "rb") as w:
        raw = w.readframes(w.getnframes())
    return np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0


def normalize_segment(seg: dict) -> dict:
    """Kelime zamanlarını doldurur, bölüm sınırlarını kelimelere eşitler, kelimelerden metni kurar."""
    raw = [w for w in (seg.get("words") or []) if str(w.get("word", "")).strip()]
    words = seg_words(seg)
    if raw and len(raw) == len(words):
        for w, r in zip(words, raw):
            if r.get("score") is not None:
                w["score"] = r["score"]
    if words:
        seg["start"], seg["end"] = round(words[0]["start"], 3), round(max(w["end"] for w in words), 3)
        seg["text"] = " ".join(w["word"] for w in words)
    for w in words:
        w["start"], w["end"] = round(w["start"], 3), round(w["end"], 3)
    seg["words"] = words
    return seg


SENT_END = (".", "?", "!", "…")
CLAUSE_END = (",", ";", ":")


def _ends(word: str, marks: tuple) -> bool:
    return word.rstrip("\"'”’)»]").endswith(marks)


def _split_long(words: list[dict], max_words: int, max_dur: float) -> list[list[dict]]:
    """Çok uzun bir cümleyi virgül ya da en uzun duraklama yakınından böler."""
    if len(words) < 4 or (len(words) <= max_words and words[-1]["end"] - words[0]["start"] <= max_dur):
        return [words]
    n = len(words)
    lo, hi = max(2, int(n * 0.3)), min(n - 2, int(n * 0.8))
    cands = [i for i in range(lo, hi + 1) if _ends(words[i - 1]["word"], CLAUSE_END)]
    if cands:
        cut = min(cands, key=lambda i: abs(i - n / 2))
    else:
        cut = max(range(lo, hi + 1), key=lambda i: words[i]["start"] - words[i - 1]["end"])
    return _split_long(words[:cut], max_words, max_dur) + _split_long(words[cut:], max_words, max_dur)


def resegment(segs: list[dict], max_words: int = 28, max_dur: float = 14.0, pause: float = 1.2) -> list[dict]:
    """30 sn'lik parçaları cümle sonu, uzun duraklama ve uzunluğa göre düzenlenebilir bölümlere ayırır."""
    out: list[dict] = []
    for seg in segs:
        words = seg.get("words") or []
        if len(words) < 2:
            out.append(seg)
            continue
        pieces: list[list[dict]] = [[]]
        for i, w in enumerate(words):
            pieces[-1].append(w)
            if i < len(words) - 1 and (_ends(w["word"], SENT_END) or words[i + 1]["start"] - w["end"] >= pause):
                pieces.append([])
        final: list[list[dict]] = []
        for p in pieces:
            final.extend(_split_long(p, max_words, max_dur))
        merged: list[list[dict]] = []
        for p in final:
            if merged and len(p) < 2 and not _ends(merged[-1][-1]["word"], SENT_END):
                merged[-1].extend(p)
            else:
                merged.append(p)
        for p in merged:
            out.append({"start": p[0]["start"], "end": p[-1]["end"], "text": " ".join(w["word"] for w in p), "words": p})
    return out


def _split_by_speaker(seg: dict) -> list[dict]:
    """Bir bölümde konuşmacı değişiyorsa bölümü böler. Tek kelimelik kopmalar komşuya katılır."""
    words = seg["words"]
    spk = [w.get("speaker") or seg.get("speaker") for w in words]
    runs: list[list] = []
    for w, s in zip(words, spk):
        if runs and runs[-1][0] == s:
            runs[-1][1].append(w)
        else:
            runs.append([s, [w]])
    merged: list[list] = []
    for r in runs:
        if merged and len(r[1]) < 2:
            merged[-1][1].extend(r[1])
        else:
            merged.append(r)
    if len(merged) > 1 and len(merged[0][1]) < 2:
        merged[1][1][0:0] = merged[0][1]
        merged.pop(0)
    # ardışık aynı konuşmacıları birleştir
    final: list[list] = []
    for r in merged:
        if final and final[-1][0] == r[0]:
            final[-1][1].extend(r[1])
        else:
            final.append(r)
    out = []
    for s, ws in final:
        ws = [{k: v for k, v in w.items() if k != "speaker"} for w in ws]
        out.append({"start": ws[0]["start"], "end": ws[-1]["end"], "speaker": s,
                    "text": " ".join(w["word"] for w in ws), "words": ws})
    return out or [seg]


class RealEngine:
    def __init__(self) -> None:
        self._model = None
        self._batched = None
        self._key: tuple | None = None

    # ---- bellek yönetimi ----
    def unload(self) -> None:
        self._model = None
        self._batched = None
        self._key = None
        gpu.free_gpu()

    def after_job(self, options: dict) -> None:
        """Konuşmacı ayrımı yapılan işlerden sonra ASR modeli tutulmaz."""
        if options.get("diarize"):
            self.unload()

    def _load_asr(self, name: str, device: str, compute: str, report: Report) -> None:
        key = (name, device, compute)
        if self._key == key:
            return
        self.unload()
        report("Model hazırlanıyor", 1)
        from faster_whisper import BatchedInferencePipeline, WhisperModel
        try:
            self._model = WhisperModel(name, device=device, compute_type=compute)
        except Exception as e:  # noqa: BLE001
            self.unload()
            text = str(e).lower()
            if gpu.is_oom(e):
                raise
            if "cublas" in text or "cudnn" in text or "cudart" in text or ".dll" in text:
                raise UserError(MSG_DLL) from e
            if "connect" in text or "offline" in text or "huggingface" in text or "cache" in text:
                raise UserError(MSG_DOWNLOAD) from e
            raise
        self._batched = BatchedInferencePipeline(self._model) if device == "cuda" else None
        self._key = key

    # ---- ana akış ----
    def run(self, wav_path: str, duration: float, options: dict, report: Report, cancelled: Callable[[], bool]) -> dict:
        device = gpu.resolve_device(options.get("device", "auto"))
        compute = gpu.resolve_compute_type(options.get("compute_type", "auto"), device)
        batch = int(options.get("batch_size", 8)) if device == "cuda" else 1
        try:
            return self._run_once(wav_path, duration, options, report, cancelled, device, compute, batch)
        except Cancelled:
            raise
        except Exception as e:  # noqa: BLE001
            if not (device == "cuda" and gpu.is_oom(e)):
                self._maybe_user_error(e)
                raise
            log.warning("GPU belleği doldu, daha küçük toplu işlem boyutuyla yeniden denenecek")
        self.unload()
        smaller = max(1, batch // 2)
        try:
            return self._run_once(wav_path, duration, options, report, cancelled, device, compute, smaller)
        except Cancelled:
            raise
        except Exception as e:  # noqa: BLE001
            self.unload()
            if gpu.is_oom(e):
                raise UserError(MSG_OOM) from e
            self._maybe_user_error(e)
            raise

    @staticmethod
    def _maybe_user_error(e: Exception) -> None:
        text = str(e).lower()
        if isinstance(e, UserError):
            return
        if "cublas" in text or "cudnn" in text or "cudart" in text:
            raise UserError(MSG_DLL) from e

    def _run_once(self, wav_path, duration, options, report, cancelled, device, compute, batch) -> dict:
        audio = load_wav(wav_path)
        duration = duration or len(audio) / 16000
        notice: list[str] = []
        want_diar = bool(options.get("diarize"))
        token = (options.get("hf_token") or "").strip()
        if want_diar and not token:
            notice.append("Konuşmacı ayrımı atlandı: Hugging Face belirteci girilmemiş. Ayarlar sayfasına bakın.")
            want_diar = False
        want_align = bool(options.get("align", True))
        bands = ({"asr": (0, 72), "align": (72, 84), "diar": (84, 97)} if want_diar and want_align
                 else {"asr": (0, 80), "diar": (80, 97)} if want_diar
                 else {"asr": (0, 85), "align": (85, 97)} if want_align
                 else {"asr": (0, 97)})

        def band_report(stage: str, band: str):
            lo, hi = bands[band]

            def cb(p: float) -> None:
                if cancelled():
                    raise Cancelled()
                report(stage, lo + (hi - lo) * max(0.0, min(100.0, p)) / 100.0)
            return cb

        # 1) ASR
        self._load_asr(options.get("model", "large-v3"), device, compute, report)
        if cancelled():
            raise Cancelled()
        segs, language = self._transcribe(audio, duration, options, device, batch, band_report("Yazıya dökülüyor", "asr"), cancelled)
        will_continue = want_align or want_diar
        if will_continue:
            self.unload()
        if not segs:
            return {"language": language, "segments": [], "speakers": {}, "notice": notice[0] if notice else ""}

        # 2) Hizalama
        if want_align:
            if cancelled():
                raise Cancelled()
            try:
                segs = self._align(segs, audio, language, device, band_report("Hizalanıyor", "align"))
            except (Cancelled, UserError):
                raise
            except Exception as e:  # noqa: BLE001
                if gpu.is_oom(e):
                    raise
                log.warning("Hizalama yapılamadı: %s", type(e).__name__)
                notice.append("Hizalama yapılamadı, Whisper'ın kendi kelime zamanları kullanıldı.")
            finally:
                gpu.free_gpu()

        for s in segs:
            normalize_segment(s)
        segs = resegment(segs)

        # 3) Konuşmacı ayrımı
        speakers: dict = {}
        if want_diar:
            if cancelled():
                raise Cancelled()
            try:
                segs = self._diarize(segs, audio, options, token, device, band_report("Konuşmacılar ayrılıyor", "diar"))
            except (Cancelled, UserError):
                raise
            except Exception as e:  # noqa: BLE001
                if gpu.is_oom(e):
                    raise
                log.warning("Konuşmacı ayrımı yapılamadı: %s", type(e).__name__)
                text = str(e).lower()
                if any(k in text for k in ("401", "403", "gated", "access", "token", "authorization")):
                    notice.append("Konuşmacı modeline erişilemedi. Belirteci ve model koşullarını Ayarlar sayfasından kontrol edin.")
                else:
                    notice.append("Konuşmacı ayrımı yapılamadı, kayıt konuşmacı etiketi olmadan kaydedildi.")
            finally:
                gpu.free_gpu()

        out = []
        for i, s in enumerate(segs):
            s = {k: v for k, v in s.items() if not k.startswith("_")}
            s["speaker"] = s.get("speaker") or None
            if s["speaker"]:
                speakers.setdefault(s["speaker"], {"name": "", "color": PALETTE[len(speakers) % len(PALETTE)]})
            s["id"] = f"s{i}"
            out.append(s)
        return {"language": language, "segments": out, "speakers": speakers, "notice": " ".join(notice)}

    # ---- aşamalar ----
    def _transcribe(self, audio, duration, options, device, batch, cb, cancelled) -> tuple[list[dict], str]:
        lang = None if options.get("language", "tr") == "auto" else options.get("language", "tr")
        task = options.get("task", "transcribe")
        vad = bool(options.get("vad", True))
        common = dict(language=lang, task=task, word_timestamps=True,
                      initial_prompt=(options.get("initial_prompt") or None), vad_filter=vad)
        if self._batched is not None:
            kwargs = dict(common, batch_size=max(1, batch))
            if not vad:
                kwargs["clip_timestamps"] = [{"start": float(i), "end": float(min(i + 30, duration))}
                                              for i in range(0, int(np.ceil(duration)), 30)] or [{"start": 0.0, "end": duration}]
                kwargs["vad_filter"] = True
            seg_iter, info = self._batched.transcribe(audio, **kwargs)
        else:
            seg_iter, info = self._model.transcribe(audio, **common, beam_size=5, condition_on_previous_text=False)
        segs: list[dict] = []
        for seg in seg_iter:
            if cancelled():
                raise Cancelled()
            text = (seg.text or "").strip()
            if text:
                words = [{"word": w.word.strip(), "start": w.start, "end": w.end, "score": round(float(w.probability), 3)}
                         for w in (seg.words or []) if w.word.strip()]
                segs.append({"start": seg.start, "end": seg.end, "text": text, "words": words})
            cb(100.0 * min(seg.end, duration) / max(duration, 1e-6))
        language = "en" if task == "translate" else (info.language or lang or "tr")
        return segs, language

    def _align(self, segs, audio, language, device, cb) -> list[dict]:
        import whisperx
        from whisperx import alignment
        if language not in alignment.DEFAULT_ALIGN_MODELS_TORCH and language not in alignment.DEFAULT_ALIGN_MODELS_HF:
            return segs
        model_a, meta = whisperx.load_align_model(language_code=language, device=device)
        try:
            res = whisperx.align([{"text": s["text"], "start": s["start"], "end": s["end"]} for s in segs],
                                 model_a, meta, audio, device, return_char_alignments=False, progress_callback=cb)
        finally:
            del model_a
        aligned = res.get("segments") or []
        if len(aligned) != len(segs):
            return segs
        merged = []
        for old, new in zip(segs, aligned):
            words = [w for w in (new.get("words") or []) if str(w.get("word", "")).strip()]
            if not words:
                merged.append(old)
                continue
            merged.append({"start": new.get("start", old["start"]), "end": new.get("end", old["end"]),
                           "text": old["text"], "words": [{"word": w["word"], "start": w.get("start"), "end": w.get("end"),
                                                          "score": w.get("score")} for w in words]})
        return merged

    def _diarize(self, segs, audio, options, token, device, cb) -> list[dict]:
        from whisperx.diarize import DiarizationPipeline, assign_word_speakers
        names = [options.get("diarization_model") or "pyannote/speaker-diarization-3.1"]
        if names[0] != "pyannote/speaker-diarization-community-1":
            names.append("pyannote/speaker-diarization-community-1")
        pipe, last = None, None
        for name in names:
            try:
                pipe = DiarizationPipeline(model_name=name, token=token, device=device)
                break
            except Exception as e:  # noqa: BLE001
                last = e
                log.warning("Konuşmacı modeli yüklenemedi (%s): %s", name, type(e).__name__)
        if pipe is None:
            raise last or RuntimeError("diarization model could not be loaded")
        try:
            df = pipe(audio, min_speakers=options.get("min_speakers"), max_speakers=options.get("max_speakers"),
                      progress_callback=cb)
        finally:
            del pipe
        result = assign_word_speakers(df, {"segments": segs}, fill_nearest=True)
        out: list[dict] = []
        for s in result["segments"]:
            out.extend(_split_by_speaker(s))
        return out
