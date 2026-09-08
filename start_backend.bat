@echo off
echo Starting CellLineFinder Backend...
cd /d "%~dp0backend_api"
if exist venv\Scripts\activate.bat (
    call venv\Scripts\activate.bat
) else (
    echo ERROR: No venv found. Run: python -m venv venv
    pause
    exit /b 1
)
pip install -r requirements.txt --quiet
uvicorn app.main:app --reload --port 8000
pause
