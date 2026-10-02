@echo off
chcp 65001 >nul
setlocal EnableExtensions
cd /d "%~dp0"
title Deşifre model indirme

if not exist ".venv\Scripts\python.exe" goto noinstall
call ".venv\Scripts\activate.bat"
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8

set MODEL=%~1
if "%MODEL%"=="" set MODEL=large-v3

echo.
echo Varsayılan model önceden indiriliyor: %MODEL%
echo Başka bir model için: download-models.bat large-v3-turbo
echo.
python -m app.pipeline.download %MODEL% tr
echo.
echo Kapatmak için bir tuşa basın...
pause >nul
exit /b 0

:noinstall
echo.
echo   Kurulum bulunamadı. Önce install.bat dosyasını çalıştırın.
echo.
echo Kapatmak için bir tuşa basın...
pause >nul
exit /b 1
