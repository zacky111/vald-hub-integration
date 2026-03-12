@echo off
REM Vald Hub Dashboard Setup for Windows

echo.
echo ========================================
echo  Vald Hub Dashboard Setup (Windows)
echo ========================================
echo.

REM Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo Error: Python is not installed or not in PATH
    echo Please install Python from https://www.python.org/downloads/
    pause
    exit /b 1
)

REM Create virtual environment
if not exist "venv\" (
    echo Creating virtual environment...
    python -m venv venv
    if errorlevel 1 (
        echo Error creating virtual environment
        pause
        exit /b 1
    )
)

REM Activate virtual environment
echo Activating virtual environment...
call venv\Scripts\activate.bat

REM Upgrade pip
echo Upgrading pip...
python -m pip install --upgrade pip

REM Install dependencies
echo Installing dependencies from requirements.txt...
pip install -r requirements.txt

REM Create .env if it doesn't exist
if not exist ".env" (
    echo Creating .env file...
    (
        echo VALD_HUB_API_KEY=your_api_key_here
        echo VALD_HUB_BASE_URL=https://api.vald-hub.com
    ) > .env
    echo Created .env file - UPDATE WITH YOUR CREDENTIALS
)

echo.
echo ========================================
echo  Setup Complete!
echo ========================================
echo.
echo Next steps:
echo   1. Edit .env with your Vald Hub API key
echo   2. Run: streamlit run app.py
echo.
echo The app will open at: http://localhost:8501
echo.
pause
