@echo off
REM xobliam - Gmail Analytics Dashboard Launcher
REM Double-click this file to start the dashboard

echo.
echo ========================================
echo   xobliam - Gmail Analytics Dashboard
echo ========================================
echo.

REM Get the directory where this script is located
cd /d "%~dp0"

REM Check for virtual environment
if exist ".venv\Scripts\activate.bat" (
    echo Activating virtual environment...
    call .venv\Scripts\activate.bat
) else if exist "venv\Scripts\activate.bat" (
    echo Activating virtual environment...
    call venv\Scripts\activate.bat
) else (
    echo No virtual environment found. Using system Python.
)

REM Check if streamlit is available
where streamlit >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo.
    echo ERROR: Streamlit is not installed.
    echo Please run: pip install -r requirements.txt
    echo.
    pause
    exit /b 1
)

echo Starting xobliam dashboard...
echo.
echo The dashboard will open in your browser.
echo Press Ctrl+C in this window to stop the server.
echo.

REM Run streamlit
streamlit run xobliam/app.py --server.headless true

pause
