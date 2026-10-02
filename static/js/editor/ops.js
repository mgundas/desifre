// Düzenleyicinin saf (yan etkisiz) işlemleri. Tüm işlevler yeni diziler döndürür, girdiyi değiştirmez.
// Değişmez kural: bir bölümün metni, kelimelerinin boşlukla birleşimine eşittir.

import { T, fmt } from '../../i18n/tr.js';

const MIN_DUR = 0.05;
const SEEK_SLACK = 0.02; // arama sonrası küçük zaman kayması için tolerans (sn)

export const trLower = (s) => s.toLocaleLowerCase('tr-TR');
export const trUpper = (s) => s.toLocaleUpperCase('tr-TR');

/** Uzunluğu değiştirmeyen Türkçe küçük harf dönüşümü (eşleşme konumları kaymasın diye). */
export function foldLower(s) {
  let out = '';
  for (const ch of s) {
    const l = ch.toLocaleLowerCase('tr-TR');
    out += l.length === ch.length ? l : ch;
  }
  return out;
}

export const tokenize = (text) => (text || '').trim().split(/\s+/).filter(Boolean);
export const round3 = (x) => Math.round(x * 1000) / 1000;
export const wordsText = (words) => words.map((w) => w.word).join(' ');

function distribute(tokens, start, end) {
  const weights = tokens.map((t) => Math.max(1, t.length));
  const total = weights.reduce((a, b) => a + b, 0);
  const span = Math.max(0, end - start);
  let t = start;
  return tokens.map((tok, i) => {
    const d = (span * weights[i]) / total;
    const w = { word: tok, start: round3(t), end: round3(t + d) };
    t += d;
    return w;
  });
}

/** Bölümde kelime yoksa metinden, uzunluğa göre orantılı zamanlı kelimeler üretir. */
export function ensureWords(seg) {
  if (seg.words && seg.words.length) return seg;
  const toks = tokenize(seg.text);
  return { ...seg, words: distribute(toks, seg.start, seg.end) };
}

const normTok = (s) => foldLower(s).replace(/[^\p{L}\p{N}]+/gu, '');

/**
 * Metin değişince kelime zamanlarını korur: eşleşen kelimeler eski zamanını alır,
 * yeni ya da değişen kelimeler komşu kelimeler arasındaki boşluğa orantılı dağıtılır.
 */
export function retimeWords(oldWords, newText, start, end) {
  const toks = tokenize(newText);
  if (!toks.length) return [];
  if (!oldWords.length) return distribute(toks, start, end);
  const a = oldWords.map((w) => normTok(w.word));
  const b = toks.map(normTok);
  const n = a.length, m = b.length;
  // en uzun ortak altdizi
  const dp = Array.from({ length: n + 1 }, () => new Int32Array(m + 1));
  for (let i = n - 1; i >= 0; i--) {
    for (let j = m - 1; j >= 0; j--) {
      dp[i][j] = a[i] === b[j] && a[i] !== '' ? dp[i + 1][j + 1] + 1 : Math.max(dp[i + 1][j], dp[i][j + 1]);
    }
  }
  const match = new Array(m).fill(-1);
  let i = 0, j = 0;
  while (i < n && j < m) {
    if (a[i] === b[j] && a[i] !== '' && dp[i][j] === dp[i + 1][j + 1] + 1) { match[j] = i; i++; j++; }
    else if (dp[i + 1][j] >= dp[i][j + 1]) i++;
    else j++;
  }
  const out = new Array(m);
  let k = 0;
  let prevOld = -1;
  let prevEnd = oldWords[0].start ?? start;
  while (k < m) {
    if (match[k] >= 0) {
      const o = oldWords[match[k]];
      out[k] = { ...o, word: toks[k] };
      prevOld = match[k];
      prevEnd = o.end;
      k++;
      continue;
    }
    let e = k;
    while (e < m && match[e] < 0) e++;
    const nextOld = e < m ? match[e] : n;
    const replaced = oldWords.slice(prevOld + 1, nextOld);
    const run = toks.slice(k, e);
    let part;
    if (replaced.length === run.length) {
      part = replaced.map((o, x) => ({ ...o, word: run[x] }));
    } else if (replaced.length > 0) {
      part = distribute(run, replaced[0].start, replaced[replaced.length - 1].end);
    } else {
      const nextStart = e < m ? oldWords[nextOld].start : (oldWords[n - 1].end ?? end);
      part = distribute(run, prevEnd, Math.max(nextStart, prevEnd));
    }
    for (let x = 0; x < part.length; x++) out[k + x] = part[x];
    prevEnd = part[part.length - 1].end;
    k = e;
  }
  return out;
}

function withWords(seg, words) {
  return {
    ...seg,
    words,
    text: wordsText(words),
    start: words.length ? words[0].start : seg.start,
    end: words.length ? Math.max(words[words.length - 1].end, words[0].start) : seg.end,
  };
}

const replaceAt = (arr, i, ...items) => [...arr.slice(0, i), ...items, ...arr.slice(i + 1)];

export function newId(segments) {
  let max = -1;
  for (const s of segments) {
    const m = /^s(\d+)$/.exec(s.id);
    if (m) max = Math.max(max, +m[1]);
  }
  return `s${max + 1}`;
}

/** Bölümün metnini değiştirir, kelime zamanlarını korumaya çalışır. */
export function setText(segments, idx, text) {
  const seg = ensureWords(segments[idx]);
  const clean = (text || '').replace(/\s+/g, ' ').trim();
  if (clean === seg.text) return segments;
  const words = retimeWords(seg.words, clean, seg.start, seg.end);
  if (!words.length) return replaceAt(segments, idx, { ...seg, words: [], text: '' });
  return replaceAt(segments, idx, withWords(seg, words));
}

/** wordIndex kelimesinden önce böler (1..n-1). */
export function splitAt(segments, idx, wordIndex) {
  const seg = ensureWords(segments[idx]);
  if (wordIndex < 1 || wordIndex >= seg.words.length) return segments;
  const left = withWords(seg, seg.words.slice(0, wordIndex));
  const right = withWords({ ...seg, id: newId(segments) }, seg.words.slice(wordIndex));
  return replaceAt(segments, idx, left, right);
}

/** Metin içindeki karakter konumuna en yakın kelime sınırından böler. */
export function splitAtChar(segments, idx, charPos) {
  const seg = ensureWords(segments[idx]);
  let offset = 0, best = -1, bestDist = Infinity;
  seg.words.forEach((w, i) => {
    if (i > 0) {
      const d = Math.abs(offset - charPos);
      if (d < bestDist) { bestDist = d; best = i; }
    }
    offset += w.word.length + 1;
  });
  return best < 0 ? segments : splitAt(segments, idx, best);
}

/** Zamana göre böler: t anından sonra başlayan ilk kelimeden önce. */
export function splitAtTime(segments, idx, t) {
  const seg = ensureWords(segments[idx]);
  let k = seg.words.findIndex((w) => w.start >= t);
  if (k < 0) k = seg.words.length - 1;
  k = Math.min(Math.max(k, 1), seg.words.length - 1);
  return splitAt(segments, idx, k);
}

/** Sonraki bölümle birleştirir. Konuşmacı birinci bölümden gelir. */
export function mergeNext(segments, idx) {
  if (idx < 0 || idx >= segments.length - 1) return segments;
  const a = ensureWords(segments[idx]);
  const b = ensureWords(segments[idx + 1]);
  const merged = withWords(a, [...a.words, ...b.words]);
  merged.end = Math.max(a.end, b.end);
  return [...segments.slice(0, idx), merged, ...segments.slice(idx + 2)];
}

export function deleteSegment(segments, idx) {
  return [...segments.slice(0, idx), ...segments.slice(idx + 1)];
}

export function setSpeaker(segments, idx, speaker) {
  if ((segments[idx].speaker || null) === (speaker || null)) return segments;
  return replaceAt(segments, idx, { ...segments[idx], speaker: speaker || null });
}

function fixWordBounds(words) {
  return words.map((w) => (w.end < w.start ? { ...w, end: w.start } : w));
}

/** Bölüm başlangıcını ya da bitişini taşır. İlk/son kelime de buna uyar. */
export function setTime(segments, idx, which, t) {
  const seg = ensureWords(segments[idx]);
  t = round3(Math.max(0, t));
  const words = seg.words.map((w) => ({ ...w }));
  if (which === 'start') {
    t = Math.min(t, seg.end - MIN_DUR);
    if (t < 0) return segments;
    words[0].start = t;
    if (words[0].end < t) words[0].end = t;
    return replaceAt(segments, idx, { ...seg, start: t, words: fixWordBounds(words) });
  }
  t = Math.max(t, seg.start + MIN_DUR);
  const last = words.length - 1;
  words[last].end = t;
  if (words[last].start > t) words[last].start = t;
  return replaceAt(segments, idx, { ...seg, end: t, words: fixWordBounds(words) });
}

export function nudge(segments, idx, which, delta) {
  const seg = segments[idx];
  return setTime(segments, idx, which, (which === 'start' ? seg.start : seg.end) + delta);
}

/** Altyazı kesitinin (w0..w1 kelime aralığı) metnini değiştirir. */
export function replaceCueText(segments, segIdx, w0, w1, text) {
  const seg = ensureWords(segments[segIdx]);
  const before = seg.words.slice(0, w0), mid = seg.words.slice(w0, w1), after = seg.words.slice(w1);
  const start = mid.length ? mid[0].start : seg.start;
  const end = mid.length ? mid[mid.length - 1].end : seg.end;
  const fresh = retimeWords(mid, text, start, end);
  const words = [...before, ...fresh, ...after];
  if (!words.length) return segments;
  return replaceAt(segments, segIdx, withWords(seg, words));
}

/** Tek bir kelimenin başlangıç ya da bitişini taşır (altyazı kesiti zamanlaması için). */
export function nudgeWord(segments, segIdx, wordIdx, which, delta) {
  const seg = ensureWords(segments[segIdx]);
  const words = seg.words.map((w) => ({ ...w }));
  const w = words[wordIdx];
  if (!w) return segments;
  if (which === 'start') {
    w.start = round3(Math.max(0, Math.min(w.start + delta, w.end - MIN_DUR)));
  } else {
    w.end = round3(Math.max(w.start + MIN_DUR, w.end + delta));
  }
  return replaceAt(segments, segIdx, withWords(seg, fixWordBounds(words)));
}

export function setWordTime(segments, segIdx, wordIdx, which, t) {
  const w = ensureWords(segments[segIdx]).words[wordIdx];
  if (!w) return segments;
  return nudgeWord(segments, segIdx, wordIdx, which, t - (which === 'start' ? w.start : w.end));
}

// ---- arama ----

/** Eşleşmeleri {seg, from, to} olarak döndürür. Metin kaydı değişmez kuralı sayesinde konumlar kelimelerle uyumludur. */
export function findMatches(segments, query, caseSensitive = false) {
  if (!query) return [];
  const q = caseSensitive ? query : foldLower(query);
  const out = [];
  segments.forEach((s, si) => {
    const hay = caseSensitive ? s.text : foldLower(s.text);
    let from = 0;
    for (;;) {
      const at = hay.indexOf(q, from);
      if (at < 0) break;
      out.push({ seg: si, from: at, to: at + q.length });
      from = at + Math.max(1, q.length);
    }
  });
  return out;
}

export function replaceMatch(segments, match, replacement) {
  const s = segments[match.seg];
  return setText(segments, match.seg, s.text.slice(0, match.from) + replacement + s.text.slice(match.to));
}

/** Tüm eşleşmeleri değiştirir. {segments, count} döndürür. */
export function replaceAll(segments, query, replacement, caseSensitive = false) {
  const matches = findMatches(segments, query, caseSensitive);
  let out = segments;
  const bySeg = new Map();
  for (const m of matches) {
    if (!bySeg.has(m.seg)) bySeg.set(m.seg, []);
    bySeg.get(m.seg).push(m);
  }
  for (const [si, list] of bySeg) {
    let text = out[si].text;
    for (const m of list.slice().reverse()) text = text.slice(0, m.from) + replacement + text.slice(m.to);
    out = setText(out, si, text);
  }
  return { segments: out, count: matches.length };
}

// ---- gezinme ve gruplama ----

/** Başlangıcı sıralı bölümler içinde t anında konuşulan bölümün indeksi (yoksa -1). */
export function segmentAt(segments, t) {
  let lo = 0, hi = segments.length - 1, ans = -1;
  while (lo <= hi) {
    const mid = (lo + hi) >> 1;
    if (segments[mid].start <= t + SEEK_SLACK) { ans = mid; lo = mid + 1; } else hi = mid - 1;
  }
  if (ans < 0) return -1;
  return t <= segments[ans].end + 0.25 ? ans : -1;
}

export function wordAt(seg, t) {
  const words = seg.words || [];
  let ans = -1;
  for (let i = 0; i < words.length; i++) {
    if (words[i].start <= t + SEEK_SLACK) ans = i; else break;
  }
  return ans;
}

/** Ardışık aynı konuşmacıdaki bölümleri tur olarak gruplar. */
export function speakerTurns(segments) {
  const turns = [];
  segments.forEach((s, i) => {
    const last = turns[turns.length - 1];
    if (last && last.speaker === (s.speaker || null)) last.items.push(i);
    else turns.push({ speaker: s.speaker || null, items: [i] });
  });
  return turns;
}

/** Konuşmacı kimliğinden varsayılan görünen ad. */
export function defaultSpeakerName(id) {
  const m = /^SPEAKER_(\d+)$/.exec(id || '');
  return m ? fmt(T.editor.speakerDefault, { n: +m[1] + 1 }) : id || '';
}

export function nextSpeakerId(speakers, segments) {
  const used = new Set([...Object.keys(speakers || {}), ...segments.map((s) => s.speaker).filter(Boolean)]);
  for (let i = 0; ; i++) {
    const id = `SPEAKER_${String(i).padStart(2, '0')}`;
    if (!used.has(id)) return id;
  }
}
