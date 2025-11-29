@echo off
REM PeakPicker Launcher for Windows
REM This script launches the PeakPicker application

echo ====================================
echo PeakPicker - TOF-SIMS Spectrum Analyzer
echo ====================================
echo.

REM Check if Python is available
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed or not in PATH.
    echo Please install Python 3.7 or later from https://www.python.org/
    echo.
    pause
    exit /b 1
)

echo Python found. Checking dependencies...
echo.

REM Check if required packages are installed (attempt import)
python -c "import numpy, pandas, matplotlib, scipy" >nul 2>&1
if errorlevel 1 (
    echo Some required packages are missing.
    echo Installing dependencies from requirements.txt...
    echo.
    pip install -r requirements.txt
    if errorlevel 1 (
        echo.
        echo ERROR: Failed to install dependencies.
        echo Please run manually: pip install -r requirements.txt
        echo.
        pause
        exit /b 1
    )
)

echo Starting PeakPicker...
echo.

REM Run the application
python main.py

if errorlevel 1 (
    echo.
    echo ERROR: PeakPicker encountered an error.
    echo Please check peakpicker.log for details.
    echo.
    pause
)
