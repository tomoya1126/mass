#!/bin/bash
# PeakPicker Launcher for Linux/Mac
# This script launches the PeakPicker application

echo "===================================="
echo "PeakPicker - TOF-SIMS Spectrum Analyzer"
echo "===================================="
echo ""

# Check if Python is available
if ! command -v python3 &> /dev/null; then
    echo "ERROR: Python 3 is not installed or not in PATH."
    echo "Please install Python 3.7 or later."
    exit 1
fi

echo "Python found. Checking dependencies..."
echo ""

# Check if required packages are installed
python3 -c "import numpy, pandas, matplotlib, scipy" 2>/dev/null
if [ $? -ne 0 ]; then
    echo "Some required packages are missing."
    echo "Installing dependencies from requirements.txt..."
    echo ""
    pip3 install -r requirements.txt
    if [ $? -ne 0 ]; then
        echo ""
        echo "ERROR: Failed to install dependencies."
        echo "Please run manually: pip3 install -r requirements.txt"
        exit 1
    fi
fi

echo "Starting PeakPicker..."
echo ""

# Run the application
python3 main.py

if [ $? -ne 0 ]; then
    echo ""
    echo "ERROR: PeakPicker encountered an error."
    echo "Please check peakpicker.log for details."
fi
