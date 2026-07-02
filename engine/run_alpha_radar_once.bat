@echo off
cd /d %~dp0
echo [Alpha Radar AI] Installing requirements...
python -m pip install -r requirements.txt
if not exist .env (
  echo.
  echo [ERROR] .env file not found.
  echo Copy .env.example to .env and put your keys first.
  pause
  exit /b 1
)
echo.
echo [Alpha Radar AI] Running scan once...
python alpha_radar_engine_v1.py
pause
