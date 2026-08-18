@echo off
REM ── Start CellLineFinder frontend (Vite on port 3000) ──
cd /d "%~dp0frontend"
echo.
echo ============================================
echo   Starting FRONTEND ->  http://localhost:3000
echo   Keep this window open while using the app.
echo   Press Ctrl+C to stop.
echo ============================================
echo.
call npm run dev
pause
