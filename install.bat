@echo off
chcp 65001 >nul
setlocal EnableExtensions
cd /d "%~dp0"
title Deşifre Kurulum

echo.
echo ==============================================================
echo   Deşifre kurulumu
echo   Yerel ve gizli yazıya dökme. Dosyalarınız bilgisayarınızdan çıkmaz.
echo ==============================================================
echo.

echo [1/6] Python 3.11 denetleniyor...
py -3.11 --version >nul 2>&1
if errorlevel 1 goto nopython
for /f "delims=" %%v in ('py -3.11 --version') do echo       %%v bulundu.

echo [2/6] Sanal ortam hazırlanıyor ^(.venv^)...
if not exist ".venv\Scripts\python.exe" py -3.11 -m venv .venv
if errorlevel 1 goto fail
call ".venv\Scripts\activate.bat"
python -m pip install --upgrade pip
if errorlevel 1 goto fail

echo [3/6] PyTorch ^(CUDA 12.6^) kuruluyor. Bu adım büyüktür ^(yaklaşık 3 GB^), lütfen bekleyin...
python -m pip install torch==2.8.0 torchaudio==2.8.0 torchvision==0.23.0 --index-url https://download.pytorch.org/whl/cu126
if errorlevel 1 goto fail

echo [4/6] Diğer bağımlılıklar kuruluyor...
python -m pip install -r requirements.txt
if errorlevel 1 goto fail

echo [5/6] ffmpeg denetleniyor...
where ffmpeg >nul 2>&1
if not errorlevel 1 goto ffmpegok
if exist "%LOCALAPPDATA%\Microsoft\WinGet\Links\ffmpeg.exe" goto ffmpegok
echo       ffmpeg bulunamadı. Ses ve video dosyalarını çözmek için gereklidir.
where winget >nul 2>&1
if errorlevel 1 goto ffmpegmanual
choice /c EH /m "      winget ile şimdi kurulsun mu? (E=Evet, H=Hayır)"
if errorlevel 2 goto ffmpegmanual
winget install --id Gyan.FFmpeg -e --accept-package-agreements --accept-source-agreements
if errorlevel 1 goto ffmpegmanual
echo       ffmpeg kuruldu. Uygulamayı başlattığınızda otomatik bulunur.
goto ffmpegdone
:ffmpegmanual
echo.
echo       Elle kurulum: https://www.gyan.dev/ffmpeg/builds/ adresinden "release essentials"
echo       paketini indirin, açın ve bin klasörünü PATH'e ekleyin.
echo       Ya da bu klasörde "ffmpeg\bin\ffmpeg.exe" olacak biçimde yerleştirin.
echo       Komut satırından kurmak için: winget install Gyan.FFmpeg
echo.
goto ffmpegdone
:ffmpegok
echo       ffmpeg bulundu.
:ffmpegdone

echo [6/6] Ekran kartı denetleniyor...
where nvidia-smi >nul 2>&1
if errorlevel 1 goto nogpu
nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv,noheader
python -c "from app.pipeline import gpu; print('      GPU hızlandırma: ' + ('ÇALIŞIYOR' if gpu.cuda_available() else 'ÇALIŞMIYOR, işlemci kullanılacak'))"
goto gpudone
:nogpu
echo       NVIDIA ekran kartı bulunamadı. Deşifre işlemcide çalışır ama çok daha yavaştır.
:gpudone

echo.
echo ==============================================================
echo   Kurulum tamamlandı!
echo.
echo   Başlatmak için start.bat dosyasına çift tıklayın.
echo   İsteğe bağlı: download-models.bat ile modeli önceden indirebilirsiniz,
echo   böylece ilk iş beklemez.
echo   Konuşmacı ayrımı için Hugging Face belirteci gerekir, ayrıntılar README.md içinde.
echo ==============================================================
echo.
echo Kapatmak için bir tuşa basın...
pause >nul
exit /b 0

:nopython
echo.
echo   HATA: Python 3.11 bulunamadı.
echo   python.org adresinden Python 3.11 sürümünü kurun ^(kurulumda "Add python.exe to PATH"
echo   ve "py launcher" seçeneklerini işaretli bırakın^) ya da komut satırında şunu çalıştırın:
echo       winget install Python.Python.3.11
echo   Sonra install.bat dosyasını yeniden çalıştırın.
echo.
echo Kapatmak için bir tuşa basın...
pause >nul
exit /b 1

:fail
echo.
echo   HATA: Kurulum tamamlanamadı. Yukarıdaki iletiyi okuyun.
echo   Yaygın nedenler: internet bağlantısı kesildi ya da disk dolu. install.bat dosyasını
echo   yeniden çalıştırmak güvenlidir, kaldığı yerden devam eder.
echo.
echo Kapatmak için bir tuşa basın...
pause >nul
exit /b 1
