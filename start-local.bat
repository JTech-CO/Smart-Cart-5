@echo off
cd /d "%~dp0"
where py >nul 2>nul
if errorlevel 1 (
  where python >nul 2>nul
  if errorlevel 1 (
    echo Python 3 is required. Install it and run this file again.
    pause
    exit /b 1
  )
  start "" http://localhost:8000
  python -m http.server 8000 --bind 127.0.0.1
) else (
  start "" http://localhost:8000
  py -3 -m http.server 8000 --bind 127.0.0.1
)
pause
