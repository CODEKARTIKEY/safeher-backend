@echo off
if not exist venv (
    echo Creating virtual environment...
    where python >nul 2>nul
    if %errorlevel%==0 (
        python -m venv venv
    ) else (
        py -3 -m venv venv
    )
)
call venv\Scripts\activate
pip install -q -r requirements.txt
python app.py
pause
