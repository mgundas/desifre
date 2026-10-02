@echo off
chcp 65001 >nul
setlocal EnableExtensions
cd /d "%~dp0"
title Deşifre

if not exist ".venv\Scripts\python.exe" goto noinstall
if "%DESIFRE_PORT%"=="" set DESIFRE_PORT=7860
set URL=http://127.0.0.1:%DESIFRE_PORT%

rem Zaten çalışıyorsa yalnızca tarayıcıyı aç
powershell -NoProfile -Command "try { Invoke-WebRequest -UseBasicParsing '%URL%/api/settings' -TimeoutSec 2 | Out-Null; exit 0 } catch { exit 1 }" >nul 2>&1
if not errorlevel 1 goto already

call ".venv\Scripts\activate.bat"
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
set HF_HUB_DISABLE_TELEMETRY=1
set DO_NOT_TRACK=1
set ANONYMIZED_TELEMETRY=False

echo Deşifre başlatılıyor. Bu pencereyi kapatırsanız uygulama durur.
echo Tarayıcı sunucu hazır olunca kendiliğinden açılacak: %URL%
echo.

rem Sunucu yanıt verince tarayıcıyı aç (arka planda bekler). DESIFRE_NO_BROWSER=1 ise açılmaz.
if "%DESIFRE_NO_BROWSER%"=="1" goto runserver
start "" /b powershell -NoProfile -WindowStyle Hidden -Command "for ($i=0; $i -lt 240; $i++) { try { Invoke-WebRequest -UseBasicParsing '%URL%/api/settings' -TimeoutSec 2 | Out-Null; Start-Process '%URL%'; break } catch { Start-Sleep -Milliseconds 500 } }"

:runserver
python run.py
echo.
echo Sunucu durdu.
echo Kapatmak için bir tuşa basın...
pause >nul
exit /b 0


:already
if "%DESIFRE_NO_BROWSER%"=="1" exit /b 0
echo Deşifre zaten çalışıyor. Tarayıcı açılıyor: %URL%
start "" "%URL%"
timeout /t 2 >nul
exit /b 0

:noinstall
echo.
echo   Kurulum bulunamadı. Önce install.bat dosyasını çalıştırın.
echo.
echo Kapatmak için bir tuşa basın...
pause >nul
exit /b 1
