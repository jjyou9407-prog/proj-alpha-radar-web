@echo off
cd /d "%~dp0"
echo Alpha Radar AI mobile web server starting...
echo iPhone Safari URL: http://172.30.1.67:3000
npm run dev -- -H 0.0.0.0 -p 3000
