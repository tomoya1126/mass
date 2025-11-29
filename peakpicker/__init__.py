# -*- coding: utf-8 -*-
"""
PeakPicker: TOF-SIMS Spectrum Analysis Tool

A modular application for analyzing TOF-SIMS spectra with automatic peak fitting.
"""

__version__ = '2.0.0'
__author__ = 'TOF-SIMS Research Team'

from .data_models import Spectrum, Peak, ROI, CalibrationResult
from .file_io import read_spectrum_file, read_mpa_file, read_csv_file, save_peaks_to_csv
from .calibration import calibrate_mass, apply_calibration_to_peaks
from .peak_fitting import (
    fit_single_peak,
    detect_and_fit_peaks,
    fit_overlapping_peaks,
    PeakDetectionParams
)
from .config import AppConfig, load_config, save_config, setup_logging

__all__ = [
    'Spectrum',
    'Peak',
    'ROI',
    'CalibrationResult',
    'read_spectrum_file',
    'read_mpa_file',
    'read_csv_file',
    'save_peaks_to_csv',
    'calibrate_mass',
    'apply_calibration_to_peaks',
    'fit_single_peak',
    'detect_and_fit_peaks',
    'fit_overlapping_peaks',
    'PeakDetectionParams',
    'AppConfig',
    'load_config',
    'save_config',
    'setup_logging'
]
