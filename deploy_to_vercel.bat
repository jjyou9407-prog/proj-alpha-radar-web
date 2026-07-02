@echo off
cd /d "%~dp0"
echo Alpha Radar AI - Vercel deploy helper
echo.
echo 1. First login if needed:
echo    npx vercel login
echo.
echo 2. Preview deploy:
echo    npx vercel
echo.
echo 3. Production deploy:
echo    npx vercel --prod
echo.
echo Running build check first...
npm run build
echo.
echo If build succeeded, run:
echo npx vercel --prod
echo.
pause
