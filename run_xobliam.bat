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

echo Starting xobliam dashboard...
echo.
echo The dashboard will open in your browser.
echo Press Ctrl+C in this window to stop the server.
echo.

REM Run streamlit using py launcher
py -m streamlit run xobliam/app.py --server.headless true

pause
