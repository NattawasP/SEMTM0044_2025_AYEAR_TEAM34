@echo off
REM ── Start CellLineFinder backend (FastAPI on port 8000) ──
cd /d "%~dp0backend_api"
call "%~dp0venv\Scripts\activate.bat"
echo.
echo ============================================
echo   Starting BACKEND  ->  http://localhost:8000
echo   Keep this window open while using the app.
echo   Press Ctrl+C to stop.
echo ============================================
echo.
python run.py
pause
