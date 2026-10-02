# Kararlar ve sapmalar

Bu dosya, brifte kesin olmayan ya da brifteki öneriden saptığım yerleri ve nedenlerini kaydeder.

## Ortam

- **Python 3.11 kurulumu.** Geliştirme makinesinde yalnızca Python 3.13 vardı. `winget install Python.Python.3.11 --scope user` ile 3.11.9 kuruldu. ffmpeg de `winget install Gyan.FFmpeg` ile kuruldu. `install.bat` aynı yolu kullanıcıya önerir.
- **PyTorch 2.8.0 + CUDA 12.6.** WhisperX 3.8.6 `torch~=2.8.0` ister. Windows'ta PyPI yalnızca CPU sürümü verdiği için torch, `install.bat` içinde CUDA dizininden (`--index-url .../whl/cu126`) ayrıca kurulur. Kalan her şey `requirements.txt` içinde birebir sabitlenmiştir (`pip freeze` çıktısı, torch üçlüsü hariç).
- **cuBLAS ve cuDNN pip paketlerinden.** `nvidia-cublas-cu12` ve `nvidia-cudnn-cu12` kullanılır, CUDA Toolkit gerekmez. `app/pipeline/gpu.py`, `site-packages/nvidia/*/bin` ve `torch/lib` klasörlerini `os.add_dll_directory` ile ve `PATH` başına ekler. RTX 4060 Ti üzerinde torch ve CTranslate2'nin aynı süreçte birlikte çalıştığı doğrulandı.

## Yazıya dökme hattı

- **ASR için faster-whisper, hizalama ve konuşmacı ayrımı için WhisperX.** Brif "WhisperX hattı" ve "yalnızca faster-whisper yedeği" diyor. Uygulamada ASR her zaman faster-whisper'ın `BatchedInferencePipeline` (GPU) ya da `WhisperModel` (CPU) sınıfıyla yapılır. Bu, WhisperX'in kendi altında kullandığı motorun aynısıdır. Hizalama (`whisperx.align`) ve konuşmacı ayrımı (`whisperx.diarize`) WhisperX'ten gelir. Nedenleri: (1) faster-whisper bölümleri tembel (lazy) üretir, bu sayede gerçek ilerleme yüzdesi ve bölüm başına iptal noktası elde edilir, WhisperX'in `transcribe` işlevinde iptal yoktur; (2) WhisperX'in varsayılan VAD'ı ya `torch.hub` ile GitHub'dan indirme ya da pyannote 4 ile uyumsuz eski bir denetim noktası gerektirir, faster-whisper'ın kendi Silero VAD'ı pakete gömülüdür ve dış çağrı yapmaz. WhisperX yüklenemezse (ya da hizalama başarısız olursa) uygulama Whisper'ın kendi kelime zamanlarıyla devam eder ve işe kullanıcıya gösterilen bir not düşer.
- **Aşamalı bellek yönetimi.** Sıra: yazıya dök, ASR'yi boşalt, hizala, boşalt, konuşmacıları ayır, boşalt. Aynı anda iki model yüklenmez. Bu nedenle "son modeli bellekte tut" kuralı yalnızca hizalama ve konuşmacı ayrımı kapalıyken fiilen devreye girer (aynı model, sonraki iş için bellekte kalır). Hizalama açıkken ASR modeli hizalamadan önce boşaltılır. 8 GB kartta bu, brifin "asla iki model birden" kuralına öncelik verilerek seçildi.
- **Hizalama varsayılan olarak açık.** Türkçe için `mpoyraz/wav2vec2-xls-r-300m-cv7-turkish` kullanılır, ilk işte indirilir. Kapatılırsa Whisper'ın kelime zamanları kullanılır.
- **Yeniden bölümleme.** Toplu çıkarım 30 saniyelik parçalar için tek bölüm üretir. Düzenlenebilir olması için bölümler cümle sonu noktalamasında, 1,2 sn'den uzun duraklamada ve çok uzun cümlelerde virgül ya da en uzun boşlukta bölünür (`resegment`). Konuşmacı değişimleri de bölüm sınırı olur, tek kelimelik kopmalar komşuya katılır.
- **OOM davranışı.** CUDA bellek hatasında her şey boşaltılır, toplu işlem boyutu yarıya indirilerek bir kez yeniden denenir. İkinci hatada "GPU belleği yetersiz. Daha küçük bir model deneyin." iletisiyle iş başarısız olur. cuBLAS/cuDNN DLL hataları ayrı ve anlaşılır bir iletiye çevrilir. Bu mantık sahte hatalarla birim testlerle sınanır, gerçek 8 GB doluluğu denenmedi.
- **Konuşmacı modeli.** Varsayılan `pyannote/speaker-diarization-3.1` (brife uygun). WhisperX 3.8.6 pyannote-audio 4.x gerektirdiği için yüklenemezse `pyannote/speaker-diarization-community-1` denenir. Belirteç olmadan hat tam çalışır, yalnızca konuşmacı etiketleri atlanır ve iş için Türkçe bir not kaydedilir. **Belirteçle gerçek konuşmacı ayrımı bu makinede denenemedi** (belirteç yok).
- **Dil adları sunucuda.** Whisper'ın 100 dili ve Türkçe adları `app/languages.py` içindedir ve `/api/languages` ile arayüze verilir. DOCX üst bilgisi de aynı kaynağı kullanır, böylece liste tek yerde durur.

## Veri ve API

- **SQLite, standart `sqlite3`, WAL kipi.** Her işlem kendi bağlantısını açar, bu yüzden worker iş parçacığı ve istekler çakışmaz.
- **Yükleme ham gövde olarak.** `POST /api/jobs?filename=...&options=...` tek dosyayı ham gövde olarak alır, parça parça diske yazar ve boyut sınırını akış sırasında denetler. Çok parçalı (multipart) biçime göre bellek ve geçici disk kopyası gerekmez, 4 GB dosyalarda önemlidir. Tarayıcı her dosyayı sırayla yükler ve dosya başına ilerleme gösterir.
- **Canlı güncelleme.** SSE akışı sunucudaki sürüm sayacını izler, değişiklik olunca ya da 2 sn'de bir iş durumunu gönderir. Bağlantı koparsa istemci 2 sn aralıkla yoklamaya geçer.
- **Düzenlenmiş bölümler tek doğru kaynak.** Dışa aktarma her zaman kayıtlı bölümlerden üretilir. Düzenleyici dışa aktarmadan önce otomatik kaydı tamamlar.
- **Kayıt silme.** "Medyayı da sil" seçilmezse ses/video dosyası silinmez, özgün adıyla `data/kept_media/` klasörüne taşınır.
- **Tarayıcı oynatma kopyaları.** wma, avi ve mkv dosyaları tarayıcıda çalmaz. İşlem sırasında çalınabilir bir kopya (`mp4` ya da `m4a`) üretilir, özgün dosya dokunulmadan kalır.
- **Depolama klasörü.** Ayarlardan değiştirilen klasör `bootstrap.json` dosyasına yazılır ve yeniden başlatmada geçerli olur. Eski veriler taşınmaz (arayüz bunu söyler). `DESIFRE_DATA` ortam değişkeni her şeyin önüne geçer.
- **Yerel güvenlik.** Yalnızca `127.0.0.1`'e bağlanır. Ek olarak, yerel sunucuya başka web sitelerinden (DNS yeniden bağlama, çapraz site istekleri) erişilmesin diye `Host` başlığı yerel adlarla sınırlanır ve değiştirici isteklerde `Origin` aynı sunucu olmalıdır. Ağ erişimi ayarı açılırsa `Host` denetimi kalkar, `Origin` denetimi kalır.
- **Dış çağrılar.** Yalnızca Hugging Face'ten model indirme ve kullanıcı "Test et" düğmesine bastığında belirteç sınaması (`huggingface.co`). Telemetri ortam değişkenleri (`HF_HUB_DISABLE_TELEMETRY`, `DO_NOT_TRACK`, `ANONYMIZED_TELEMETRY`, `PYANNOTE_METRICS_ENABLED`) kapatılır. Günlüğe transkript metni ve belirteç yazılmaz.

## Dışa aktarma

- **CSV ayırıcısı `;`.** Türkçe Windows'ta Excel, virgülle ayrılmış dosyayı tek sütunda açar. Ayarlardan `,` ya da Tab seçilebilir.
- **BOM.** Varsayılan olarak SRT, TXT ve CSV dosyalarına eklenir, VTT ve JSON'a eklenmez (VTT bunu zaten UTF-8 kabul eder). Ayarlardan kapatılır.
- **Altyazı kesitleri bölüm sınırını geçmez.** Her bölüm kendi kesitlerine ayrılır. Sıra: cümle sonu noktalamasında böl, taşma olursa son noktalamada ya da kelime sınırında böl, tek kelimelik kuyruğu önlemek için bir kelime önceki kesitten al, kısa kesitleri birleştir ya da en az süreye uzat (sonraki kesitle çakışmadan). Satırlar, noktalama bonuslu en dengeli bölünmeyle kurulur. Karakterler NFC biçiminde sayılır.
- **Konuşmacı öneki** yalnızca konuşmacı değişen kesitin ilk satırına yazılır.
- **Metin paragrafları.** Konuşmacı değişince, bölümler arası boşluk 2 sn'yi aşınca ya da paragraf 700 karakteri geçince yeni paragraf başlar (konuşmacı bilgisi olmayan kayıtlar tek paragrafa dönmesin diye).

## Düzenleyici

- **Metin düzenleme iki kipli.** Satırlar kelime kelime tıklanabilir (arama ve vurgulama için), çift tıklayınca bir metin alanına dönüşür. Enter ve Ctrl+Enter düzenlemeyi bitirir, Shift+Enter imleç konumundan böler. Metin biçimlenmiş bir alan (contenteditable) yerine düz textarea olduğu için imleç ve geri alma güvenilirdir.
- **Metin = kelimelerin birleşimi.** Bir bölümün metni her zaman kelimelerinin boşlukla birleşimine eşittir. Metin düzenlenince eski kelimelerle en uzun ortak altdizi eşleştirilir: eşleşen kelimeler eski zamanını korur, değişenler komşu boşluğa ya da değiştirdikleri kelimelerin aralığına orantılı dağıtılır.
- **Altyazı görünümü** kesitleri sunucudaki aynı segmenter ile hesaplar (`POST /api/cues`), böylece ekranda görülen, dışa aktarılan dosyayla aynıdır. Kesit metni düzenlenince değişiklik, o kesitin kelimelerine aynı eşleştirme ile geri yazılır. Kesit içindeki satır kırılımları düzenlemeyle yeniden hesaplanır.
- **Geri al / yinele** değişmez (immutable) veri yapısı üzerinde, yalnızca başvuru saklayarak çalışır. Aynı bölümdeki ardışık yazma 1,2 sn içinde tek adımda birleşir. Ctrl+Z yalnızca metin alanı dışında ya da bölüm düzenleme alanında bizimdir, Bul/Başlık gibi alanlarda tarayıcının kendi geri almasına bırakılır.
- **Otomatik kayıt** son değişiklikten 1,5 sn sonra yapılır. Bunun yanında her değişiklik `localStorage` içine taslak olarak yazılır (sayfa yenilense ya da kapansa bile). Sayfa yeniden açılınca taslak sunucudaki kayıttan yeniyse geri yüklenir.
- **Bul/değiştir** Türkçe harfleri uzunluğu değiştirmeyen bir küçük harf dönüşümüyle karşılaştırır (`I`↔`ı`, `İ`↔`i`), böylece eşleşme konumları kaymaz.

## Testler

- Test sesi, Piper TTS'in `tr_TR-dfki-medium` sesiyle üretilmiş 24 saniyelik bir Türkçe konuşmadır (`tests/data/ornek_tr.wav`, metni `ornek_tr.txt`). Bu kaydı depo dışına dağıtmadan önce ses lisansını denetleyin.
- Playwright testleri varsayılan olarak sahte yazıya dökücüyle (hızlı, deterministik) çalışır. `DESIFRE_E2E_ENGINE=real` ile aynı testler gerçek `tiny` modeliyle CPU'da çalışır.
- Yavaş gerçek test `smoke` işaretlidir (`-m "not smoke"` ile atlanır).
