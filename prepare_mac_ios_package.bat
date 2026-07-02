@echo off
setlocal

set SRC=%~dp0
set DESKTOP=%USERPROFILE%\Desktop
set STAGE=%TEMP%\alpha_radar_ios_mac_package
set ZIP=%DESKTOP%\alpha_radar_ios_mac_package.zip

echo Preparing Alpha Radar iOS Mac package...

if exist "%STAGE%" rmdir /s /q "%STAGE%"
mkdir "%STAGE%"

robocopy "%SRC%" "%STAGE%\webapp_update" /E /XD node_modules .next .vercel .git /XF *.bak_* >nul

if exist "%ZIP%" del /f /q "%ZIP%"
powershell -NoProfile -ExecutionPolicy Bypass -Command "Compress-Archive -Path '%STAGE%\webapp_update' -DestinationPath '%ZIP%' -Force"

echo.
echo Done.
echo Created:
echo %ZIP%
echo.
pause

