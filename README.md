# Deşifre

Bilgisayarınızda çalışan, gizli bir yazıya dökme ve altyazı uygulaması. Ses ya da video dosyası yükleyin, Whisper ile ekran kartınızda yazıya dökün, konuşmacıları ayırın, metni ve altyazıyı tarayıcıda oynatmayla eşzamanlı düzenleyin, TXT, SRT, VTT, DOCX, JSON ve CSV olarak dışa aktarın.

Dosyalarınız bilgisayarınızdan çıkmaz. Dış bağlantı yalnızca Hugging Face'ten model indirmek içindir.

## İçindekiler

1. [Gereksinimler](#gereksinimler)
2. [Kurulum](#kurulum)
3. [Kullanım](#kullanım)
4. [Hugging Face belirteci (konuşmacı ayrımı)](#hugging-face-belirteci-konuşmacı-ayrımı)
5. [8 GB ekran kartı için model seçimi](#8-gb-ekran-kartı-için-model-seçimi)
6. [Klavye kısayolları](#klavye-kısayolları)
7. [Dışa aktarma](#dışa-aktarma)
8. [Sorun giderme](#sorun-giderme)
9. [Veriler nerede saklanır](#veriler-nerede-saklanır)
10. [Testler](#testler)
11. [Gizlilik ve güvenlik](#gizlilik-ve-güvenlik)

## Gereksinimler

- Windows 11 (Windows 10 da çalışmalı)
- Python 3.11 (`py -3.11` komutu çalışmalı)
- NVIDIA ekran kartı ve güncel sürücü (önerilir). Kart yoksa uygulama işlemcide çalışır ama çok yavaştır.
- Yaklaşık 8 GB boş disk (PyTorch ve modeller için) ve ilk kurulumda internet
- ffmpeg (kurulum betiği kurmayı önerir)

Python 3.11 yoksa: `winget install Python.Python.3.11`

## Kurulum

1. `install.bat` dosyasına çift tıklayın. Betik sırasıyla Python 3.11'i denetler, `.venv` sanal ortamını kurar, CUDA destekli PyTorch'u ve diğer bağımlılıkları yükler, ffmpeg'i denetler (yoksa `winget` ile kurmayı önerir), ekran kartınızı bildirir ve GPU hızlandırmasının çalışıp çalışmadığını söyler.
2. `start.bat` dosyasına çift tıklayın. Sunucu başlar ve tarayıcı `http://127.0.0.1:7860` adresinde kendiliğinden açılır. Siyah pencereyi kapatırsanız uygulama durur.
3. İsteğe bağlı: `download-models.bat` modeli önceden indirir, böylece ilk iş beklemez. Başka bir model için `download-models.bat large-v3-turbo` yazın.

Kurulum yarıda kesilirse `install.bat` dosyasını yeniden çalıştırmak güvenlidir.

## Kullanım

1. **Yeni Yükleme:** Dosyaları sürükleyip bırakın ya da "Dosya seç" ile seçin (birden çok dosya olabilir, her biri ayrı iş olur). Dili (varsayılan Türkçe, otomatik algılama ya da arayüzde aranabilir 100 dil), modeli, konuşmacı ayrımını, görevi (yazıya dök ya da İngilizceye çevir) ve isteğe bağlı başlangıç ipucunu seçin. İpucuna özel adları ve terimleri yazarsanız doğru yazılma olasılıkları artar.
2. **Kuyruk:** İşler tek tek çalışır. Çalışan işte aşama adı, yüzde, geçen süre ve tahmini kalan süre görünür. Bekleyen işleri sıralayabilir, çalışan ya da bekleyen işi iptal edebilir, başarısız ya da iptal edilen işi yeniden deneyebilirsiniz. Uygulama yeniden başlarsa yarım kalan iş otomatik olarak kuyruğa döner.
3. **Kütüphane:** Tüm kayıtlar. Başlıkta ve metin içinde arayın (Türkçe büyük/küçük harf kurallarına uygun: `IŞIK`, `ışık` ile eşleşir), tarihe, başlığa ya da süreye göre sıralayın, dışa aktarın, yeniden adlandırın, silin.
4. **Düzenleyici:** Bir kaydı açın.
   - Üstte oynatıcı: oynat/duraklat, 5 sn geri/ileri, 0,5x ile 2x hız, konuşmacı renkli zaman çizelgesi (aynı zamanda arama çubuğudur).
   - **Metin görünümü:** Oynatılan bölüm vurgulanır ve otomatik kayar, oynatılan kelime işaretlenir. Bir kelimeye ya da bölüme tıklamak oraya gider. Çift tıklayınca metni düzenlersiniz. Seçili bölümün altında araçlar çıkar: konuşmacı değiştirme, başlangıç ve bitişi ±100 ms ayarlama ya da şimdiki ana alma, bölümü çalma, bölme, sonrakiyle birleştirme, silme.
   - **Konuşmacılar** düğmesi: bir konuşmacının adını değiştirince her yerde güncellenir, her konuşmacıya renk seçebilirsiniz.
   - **Altyazı görünümü:** Ayarlardaki kurallara göre otomatik oluşturulan altyazı kesitleri. Metinlerini ve zamanlarını düzenleyebilirsiniz. Süresi çok uzun ya da okuma hızı yüksek kesitler uyarı rengiyle işaretlenir.
   - **Bul ve değiştir** (Ctrl+F): eşleşme sayacı, sonraki/önceki, değiştir, tümünü değiştir. Türkçe harflere duyarlıdır.
   - Geri al/yinele, otomatik kayıt ("Kaydedildi" göstergesi). Sayfayı yenileseniz ya da kapatsanız bile yazdıklarınız kaybolmaz.
5. **Ayarlar:** Varsayılan dil ve model, hesaplama türü, toplu işlem boyutu, aygıt, sessizlik algılama, kelime hizalama, Hugging Face belirteci, altyazı kuralları, dosya biçimi (BOM, CSV ayırıcı), depolama klasörü ve diskte kullanılan yer, ağ erişimi, sistem bilgisi (GPU, VRAM, CUDA, ffmpeg, indirilmiş modeller).

## Hugging Face belirteci (konuşmacı ayrımı)

**Belirteç olmadan uygulama tam çalışır.** Yalnızca konuşmacı etiketleri (Konuşmacı 1, Konuşmacı 2...) atlanır ve işe bunu söyleyen bir not düşülür. Konuşmacı ayrımı istiyorsanız (ücretsiz):

1. [huggingface.co](https://huggingface.co) adresinde hesap açın ve giriş yapın.
2. [pyannote/speaker-diarization-3.1](https://huggingface.co/pyannote/speaker-diarization-3.1) sayfasını açın, koşulları kabul edin ("Agree and access repository").
3. [pyannote/segmentation-3.0](https://huggingface.co/pyannote/segmentation-3.0) sayfası için aynısını yapın.
4. Hesap ayarlarındaki **Access Tokens** bölümünden "Read" izinli yeni bir belirteç oluşturun ve kopyalayın.
5. Deşifre'de **Ayarlar > Konuşmacı ayrımı** alanına yapıştırın, "Ayarları kaydet"e basın, sonra **Test et**'e basın. Belirtecin geçerli olup olmadığını ve koşulların kabul edilip edilmediğini söyler.
6. Yüklerken "Konuşmacıları ayır" kutusunu işaretleyin (Ayarlar'dan varsayılan da yapabilirsiniz).

Belirteç yalnızca bu bilgisayarda `data/settings.json` içinde durur, arayüzde maskelenir ve günlüğe yazılmaz. İsterseniz "En az/en çok konuşmacı" alanlarına sayıyı yazarak ayrımı iyileştirebilirsiniz.

## 8 GB ekran kartı için model seçimi

RTX 4060 Ti (8 GB) üzerinde, 144 saniyelik Türkçe kayıtla ölçülen değerler (hizalama açık, `int8_float16`, ısınmış model):

| Model | Ek VRAM (tepe) | Hız | Ne zaman |
| --- | --- | --- | --- |
| `large-v3` (varsayılan) | yaklaşık 4,3 GB | yaklaşık 7 kat gerçek zamanlı | En iyi doğruluk. Röportaj, toplantı, altyazı. |
| `large-v3-turbo` | yaklaşık 3,5 GB | yaklaşık 10 kat gerçek zamanlı | Neredeyse aynı doğruluk, daha hızlı. Uzun kayıtlar. |
| `medium` | daha az | daha hızlı | Doğruluk biraz düşer. |
| `small`, `base`, `tiny` | çok az | çok hızlı | Taslak ve deneme için. Türkçede hata artar. |

Bu ölçümlere göre 10 dakikalık bir kayıt `large-v3` ile yaklaşık bir dakikada yazıya dökülür (ek olarak model yüklemek yaklaşık 10 sn sürer). Masaüstü uygulamalarınız da VRAM kullanır. `large-v3` tepe noktasında toplam kullanım yaklaşık 6 GB'a çıkar, 8 GB'a sığar. Bellek hatası alırsanız önce Ayarlar'dan toplu işlem boyutunu 4'e indirin, sonra `large-v3-turbo` ya da `medium` deneyin. Uygulama bellek hatasında kendiliğinden bir kez daha küçük toplu işlem boyutuyla yeniden dener.

Konuşmacı ayrımı açıkken ek bir model (pyannote) yüklenir. Bellek taşmasını önlemek için modeller her zaman sırayla yüklenir ve her aşamadan sonra boşaltılır.

## Klavye kısayolları

Düzenleyicide F1 tuşu bu listeyi açar.

| Kısayol | İşlev |
| --- | --- |
| Space ya da Ctrl+Space | Oynat/duraklat (Ctrl+Space metin alanındayken de çalışır) |
| Alt+← / Alt+→ | 5 saniye geri / ileri |
| Ctrl+Z | Geri al |
| Ctrl+Y ya da Ctrl+Shift+Z | Yinele |
| Çift tıklama (ya da seçili satırda Enter, F2) | Bölümün metnini düzenle |
| Ctrl+Enter (ya da Enter, Esc) | Düzenlemeyi bitir |
| Shift+Enter | Düzenlerken imleç konumundan böl |
| Ctrl+F | Bul ve değiştir |
| Ctrl+S | Hemen kaydet |
| Alt+↑ / Alt+↓ | Önceki / sonraki bölüm |
| ↑ / ↓ (listeye odaklanınca) | Bölümler arasında gez |
| F1 | Kısayol panelini aç |

## Dışa aktarma

Düzenleyiciden ve Kütüphane'den, en son düzenlemelerinizle:

- **TXT:** Zaman damgası ve konuşmacı adı seçenekleri. Aynı konuşmacının ardışık cümleleri tek paragrafta toplanır.
- **SRT ve VTT:** Kelime zamanlarından üretilir. Satır başına en çok karakter (42), kesit başına en çok satır (2), en uzun süre (7 sn), en kısa süre (1 sn) ayarlanabilir. Satırlar önce noktalamadan, sonra en dengeli yerden kırılır. İsteğe bağlı konuşmacı öneki.
- **DOCX:** Başlık, bilgi satırı (tarih, süre, dil), konuşmacı etiketli paragraflar, isteğe bağlı zaman damgaları.
- **JSON:** Kelime zamanları dahil tüm veri.
- **CSV:** başlangıç, bitiş, konuşmacı, metin. Ayırıcı varsayılan olarak `;` (Türkçe Excel için).

Dosyalar UTF-8'dir, Türkçe karakterler (ç ğ ı İ ö ş ü) bozulmaz. TXT, SRT ve CSV dosyalarına varsayılan olarak BOM eklenir (eski Windows oynatıcıları ve Excel için). Ayarlar'dan kapatabilirsiniz. Dosya adı, kaydın başlığından Türkçe harfler korunarak üretilir.

## Sorun giderme

**"Could not load library cudnn_ops64_9.dll" ya da "cublas64_12.dll bulunamadı" (CUDA/cuDNN DLL hataları)**
Uygulama, cuBLAS ve cuDNN kütüphanelerini pip paketlerinden (`.venv\Lib\site-packages\nvidia\...`) bulup yola kendisi ekler, CUDA Toolkit kurmanız gerekmez. Hata alırsanız:
1. Sürücünüzü güncelleyin. `nvidia-smi` komutu çalışmalı.
2. Paketleri yeniden kurun: `.venv\Scripts\pip install --force-reinstall nvidia-cublas-cu12==12.9.2.10 nvidia-cudnn-cu12==9.27.0.42`
3. Bilgisayarınızda başka bir CUDA/cuDNN sürümü PATH'te öne geçiyorsa, o klasörü PATH'ten geçici olarak çıkarıp `start.bat` ile yeniden başlatın.
4. Hâlâ olmuyorsa Ayarlar > Aygıt > "İşlemci (CPU)" seçerek çalışmaya devam edebilirsiniz (yavaş).
Ayarlar > Sistem bilgisi bölümü "CUDA kullanılabilir" durumunu gösterir.

**"ffmpeg bulunamadı"**
Komut satırında `winget install Gyan.FFmpeg` çalıştırın ve `start.bat` ile uygulamayı yeniden başlatın. Elle kurmak isterseniz ffmpeg'i [gyan.dev](https://www.gyan.dev/ffmpeg/builds/) adresinden indirip `bin` klasörünü PATH'e ekleyin ya da bu klasörde `ffmpeg\bin\ffmpeg.exe` olacak biçimde yerleştirin. Uygulama winget'in kurduğu konumu da kendisi bulur.

**"GPU belleği yetersiz. Daha küçük bir model deneyin."**
Başka uygulamaların (tarayıcı, oyun) VRAM kullanımını azaltın, Ayarlar'dan toplu işlem boyutunu düşürün (8 yerine 4 ya da 2), sonra `large-v3-turbo` ya da `medium` modelini seçin. Konuşmacı ayrımı çok uzun kayıtlarda belleği artırır, kaydı bölmeyi deneyin.

**İşlemci modunda çok yavaş**
GPU yoksa ya da CUDA kullanılamıyorsa uygulama CPU'da çalışır. Bu modda `tiny` ve `base` makul sürelerde biter (24 saniyelik örnek `tiny` ile yaklaşık 15 saniye), `large-v3` ise çok uzun sürer. CPU kullanacaksanız `small` ya da daha küçük bir model seçin ve hizalamayı gerekirse kapatın.

**Konuşmacı etiketleri gelmiyor**
Kuyruktaki işin altındaki "Not" satırına bakın. "Belirteç girilmemiş" diyorsa yukarıdaki Hugging Face adımlarını izleyin. Belirteç var ama erişim hatası görüyorsanız Ayarlar'daki "Test et" düğmesi hangi model sayfasında koşulların kabul edilmediğini söyler.

**İlk iş çok uzun sürüyor**
Modeller ilk kullanımda indirilir (`large-v3` yaklaşık 3 GB, Türkçe hizalama modeli yaklaşık 1,2 GB). `download-models.bat` ile önceden indirebilirsiniz. Modeller `%USERPROFILE%\.cache\huggingface\hub` içinde durur.

**Port kullanımda**
`start.bat` çalışmaya başlamadan önce uygulama zaten açıksa tarayıcıyı açıp kapanır. Başka bir uygulama 7860 portunu kullanıyorsa: `set DESIFRE_PORT=7870` yazıp `start.bat` çalıştırın.

**Yarım kalan ya da takılan iş**
Uygulamayı kapatıp açın: "işleniyor" durumunda kalan işler otomatik olarak "beklemede" olur ve yeniden başlar.

## Veriler nerede saklanır

Varsayılan olarak proje klasöründeki `data/` içinde (Ayarlar > Depolama'dan değiştirilebilir, yeniden başlatma gerekir ve eski veriler taşınmaz):

- `data/desifre.db`: işler ve kayıtlar (SQLite)
- `data/settings.json`: ayarlar (Hugging Face belirteci dahil)
- `data/uploads/`: yüklenen dosyalar (UUID adlarıyla) ve tarayıcı oynatma kopyaları
- `data/kept_media/`: "medyayı da sil" seçilmeden silinen kayıtların dosyaları
- `data/work/`: geçici çözülmüş ses (iş bitince silinir)

Yedeklemek için `data/` klasörünü kopyalayın. Yazılan modeller `%USERPROFILE%\.cache\huggingface\hub` içindedir.

## Testler

Sanal ortam etkinken (ya da `.venv\Scripts\python` ile) proje klasöründe:

```
:: hızlı testler: birim, API (sahte yazıya dökücü), düzenleyici mantığı (Node)
.venv\Scripts\python -m pytest -m "not smoke and not e2e"

:: gerçek model duman testi (tiny, CPU; ilk seferde model indirir)
.venv\Scripts\python -m pytest tests/test_smoke_real.py -s

:: tarayıcı testleri (ilk kez: Playwright kurulumu gerekir)
.venv\Scripts\pip install -r requirements-dev.txt
.venv\Scripts\python -m playwright install chromium
.venv\Scripts\python -m pytest tests/test_e2e_ui.py
:: aynı tarayıcı testlerini gerçek tiny modeliyle çalıştırmak için:
set DESIFRE_E2E_ENGINE=real
.venv\Scripts\python -m pytest tests/test_e2e_ui.py

:: yalnızca düzenleyici mantığının Node testleri
node --test tests/js/ops.test.mjs
```

Tarayıcı testlerinin ekran görüntüleri `tests/_artifacts/screenshots/` klasörüne yazılır.

## Gizlilik ve güvenlik

- Sunucu varsayılan olarak yalnızca `127.0.0.1` adresine bağlanır. Ayarlar'dan yerel ağ erişimi açılabilir (uyarılı, yeniden başlatma gerekir).
- Telemetri yoktur ve ilgili kütüphanelerin telemetrisi kapatılır. Dış bağlantı yalnızca Hugging Face'ten model indirmek ve "Test et" düğmesine bastığınızdaki belirteç sınaması içindir.
- Yüklenen dosyaların adları temizlenir ve UUID tabanlı yollara kaydedilir. En büyük yükleme boyutu varsayılan 4 GB'tır (Ayarlar'dan değişir).
- Transkript metni ve belirteç günlüğe yazılmaz.
- Yerel sunucu, başka web sitelerinin isteklerine (DNS yeniden bağlama dahil) karşı `Host` ve `Origin` başlıklarını denetler.

## Proje yapısı

```
app/            FastAPI uygulaması, işçi, ayarlar, veritabanı
  pipeline/     ffmpeg, faster-whisper, WhisperX hizalama ve konuşmacı ayrımı, GPU yardımcıları
  export/       TXT, SRT/VTT, DOCX, JSON/CSV, altyazı segmenteri
  api/          uç noktalar (işler, kayıtlar, ayarlar, sistem, canlı güncelleme)
static/         arayüz (derleme adımı yok, çevrimdışı çalışır)
  i18n/tr.js    tüm arayüz metinleri
  js/editor/    düzenleyici mantığı ve görünümleri
tests/          pytest, Node ve Playwright testleri
DECISIONS.md    kararlar ve sapmalar
```
