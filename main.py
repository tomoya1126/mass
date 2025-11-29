#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
PeakPicker - TOF-SIMS Spectrum Analysis Tool

Main entry point for the application.
"""

import sys
import os

# Add package directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from peakpicker.config import load_config, save_config, setup_logging
from peakpicker.gui import PeakPickerGUI


def main():
    """Main entry point."""
    # Setup logging
    setup_logging(log_file="peakpicker.log")

    # Load configuration
    config = load_config("peakpicker_config.json")

    # Create and run GUI
    app = PeakPickerGUI(config)

    try:
        app.run()
    finally:
        # Save configuration on exit
        save_config(config, "peakpicker_config.json")


if __name__ == "__main__":
    main()
