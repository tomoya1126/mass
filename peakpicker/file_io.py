# -*- coding: utf-8 -*-
"""
File I/O module for TOF-SIMS data.

Handles reading MPA files and other data formats with robust error handling.
"""

import os
import re
import logging
from typing import Tuple, Optional, Dict, Any
import pandas as pd
import numpy as np
from .data_models import Spectrum


# Configure logging
logger = logging.getLogger(__name__)


class FileReadError(Exception):
    """Custom exception for file reading errors."""
    pass


def read_spectrum_file(file_path: str) -> Spectrum:
    """
    Read spectrum data from a file.

    Automatically detects file format and uses the appropriate reader.

    Args:
        file_path: Path to the spectrum data file

    Returns:
        Spectrum object containing the loaded data

    Raises:
        FileReadError: If the file cannot be read or parsed
    """
    if not os.path.exists(file_path):
        raise FileReadError(f"File not found: {file_path}")

    file_ext = os.path.splitext(file_path)[1].lower()

    try:
        if file_ext == '.mpa':
            return read_mpa_file(file_path)
        elif file_ext in ['.csv', '.txt']:
            return read_csv_file(file_path)
        else:
            # Try generic read
            logger.warning(f"Unknown file extension '{file_ext}', attempting generic CSV read")
            return read_csv_file(file_path)
    except Exception as e:
        raise FileReadError(f"Failed to read file: {str(e)}") from e


def read_mpa_file(file_path: str) -> Spectrum:
    """
    Read MPA4 format file with robust header detection.

    This function:
    1. Tries multiple encodings (UTF-8, Shift-JIS, CP932, Latin-1)
    2. Detects data start using [TDAT marker
    3. Parses numerical data pairs (TOF, Count)

    Args:
        file_path: Path to the MPA file

    Returns:
        Spectrum object

    Raises:
        FileReadError: If the file cannot be read or parsed
    """
    logger.info(f"Reading MPA file: {file_path}")

    # Try multiple encodings
    encodings = ['utf-8', 'shift-jis', 'cp932', 'latin-1']
    lines = None
    encoding_used = None

    for encoding in encodings:
        try:
            with open(file_path, 'r', encoding=encoding) as f:
                lines = f.readlines()
            logger.info(f"Successfully read file with encoding: {encoding}")
            encoding_used = encoding
            break
        except UnicodeDecodeError:
            logger.debug(f"Failed to read with encoding: {encoding}")
            continue
        except Exception as e:
            logger.error(f"Error reading file with encoding {encoding}: {e}")
            continue

    if lines is None:
        raise FileReadError(
            "Could not read MPA file with any of the tried encodings "
            f"({', '.join(encodings)}).\n\n"
            "Possible solutions:\n"
            "- Check if the file is corrupted\n"
            "- Re-save the file with UTF-8 encoding\n"
            "- Try converting the file using a text editor"
        )

    # Find data start line using [TDAT marker
    data_start_line = None
    tdat_pattern = re.compile(r'\[TDAT\d*[,\s]')

    for i, line in enumerate(lines):
        if tdat_pattern.search(line):
            data_start_line = i + 1  # Data starts on the next line
            logger.info(f"Found TDAT marker at line {i+1}, data starts at line {data_start_line+1}")
            break

    if data_start_line is None:
        # Fallback: Try to detect data by finding first line with two numbers
        logger.warning("TDAT marker not found, attempting to detect data start by pattern")
        for i, line in enumerate(lines):
            parts = line.strip().split()
            if len(parts) == 2:
                try:
                    float(parts[0])
                    float(parts[1])
                    data_start_line = i
                    logger.info(f"Detected data start at line {i+1} (first numeric pair)")
                    break
                except ValueError:
                    continue

    if data_start_line is None:
        raise FileReadError(
            "Could not detect data start in MPA file.\n\n"
            "Expected format:\n"
            "- Header section with [TDAT0, ...] marker, OR\n"
            "- Data section with lines containing two numbers (TOF Count)\n\n"
            "Possible solutions:\n"
            "- Check if the file format matches MPA4 ASCII format\n"
            "- Verify that the file contains numerical data"
        )

    # Parse data lines
    data_lines = lines[data_start_line:]
    tof_list = []
    count_list = []
    parse_errors = 0

    for i, line in enumerate(data_lines):
        parts = line.strip().split()
        if len(parts) >= 2:
            try:
                tof_val = float(parts[0])
                count_val = float(parts[1])
                tof_list.append(tof_val)
                count_list.append(count_val)
            except ValueError:
                parse_errors += 1
                if parse_errors <= 5:  # Log only first few errors
                    logger.debug(f"Could not parse line {data_start_line + i + 1}: {line.strip()}")

    if not tof_list:
        raise FileReadError(
            "No valid numerical data found in MPA file.\n\n"
            "Expected format: Each line should contain two numbers (TOF Count)\n"
            "Example:\n"
            "  0.0  59\n"
            "  6.4  52\n"
            "  12.8 60\n\n"
            "Possible solutions:\n"
            "- Check if the file contains data section\n"
            "- Verify the data format matches TOF-SIMS MPA format"
        )

    logger.info(f"Successfully parsed {len(tof_list)} data points (skipped {parse_errors} invalid lines)")

    # Create Spectrum object
    tof_array = np.array(tof_list)
    intensity_array = np.array(count_list)

    metadata = {
        'filename': os.path.basename(file_path),
        'encoding': encoding_used,
        'data_start_line': data_start_line + 1,
        'points_count': len(tof_list)
    }

    return Spectrum(tof=tof_array, intensity=intensity_array, metadata=metadata)


def read_csv_file(file_path: str) -> Spectrum:
    """
    Read CSV/TSV format spectrum file.

    Tries multiple separators (comma, tab, whitespace) and encodings.

    Args:
        file_path: Path to the CSV file

    Returns:
        Spectrum object

    Raises:
        FileReadError: If the file cannot be read or parsed
    """
    logger.info(f"Reading CSV file: {file_path}")

    encodings = ['utf-8', 'shift-jis', 'cp932', 'latin-1']
    separators = [',', '\t', r'\s+']
    column_names = ['TOF', 'Count']

    # Try different combinations
    for encoding in encodings:
        for sep in separators:
            try:
                # Try reading with current combination
                df = pd.read_csv(
                    file_path,
                    sep=sep,
                    names=column_names,
                    skiprows=0,
                    encoding=encoding,
                    engine='python',
                    on_bad_lines='warn',
                    comment='#'
                )

                # Validate data
                if 'TOF' in df.columns and 'Count' in df.columns:
                    # Check if first row is actually data or header
                    if not pd.api.types.is_numeric_dtype(df['TOF']):
                        # Try skipping first row
                        df = pd.read_csv(
                            file_path,
                            sep=sep,
                            names=column_names,
                            skiprows=1,
                            encoding=encoding,
                            engine='python',
                            on_bad_lines='warn',
                            comment='#'
                        )

                    # Convert to numeric
                    df['TOF'] = pd.to_numeric(df['TOF'], errors='coerce')
                    df['Count'] = pd.to_numeric(df['Count'], errors='coerce')

                    # Remove invalid rows
                    df.dropna(subset=['TOF', 'Count'], inplace=True)

                    if len(df) > 10:  # Require at least 10 valid points
                        logger.info(f"Successfully read CSV with separator='{sep}', encoding='{encoding}'")

                        # Create Spectrum
                        tof_array = df['TOF'].values
                        intensity_array = df['Count'].values

                        metadata = {
                            'filename': os.path.basename(file_path),
                            'encoding': encoding,
                            'separator': sep,
                            'points_count': len(df)
                        }

                        return Spectrum(tof=tof_array, intensity=intensity_array, metadata=metadata)

            except Exception as e:
                logger.debug(f"Failed with sep='{sep}', encoding='{encoding}': {e}")
                continue

    # If all attempts failed
    raise FileReadError(
        "Could not parse CSV file with any tried format.\n\n"
        "Expected format:\n"
        "- Two columns: TOF and Count\n"
        "- Separator: comma, tab, or whitespace\n"
        "- Encoding: UTF-8, Shift-JIS, CP932, or Latin-1\n\n"
        "Example:\n"
        "  0.0,59\n"
        "  6.4,52\n"
        "  12.8,60\n\n"
        "Possible solutions:\n"
        "- Check the file format\n"
        "- Re-save with UTF-8 encoding and comma/tab separator\n"
        "- Verify the file contains numerical data"
    )


def save_peaks_to_csv(peaks, file_path: str, include_fit_results: bool = True):
    """
    Save peak list to CSV file.

    Args:
        peaks: List of Peak objects
        file_path: Output CSV file path
        include_fit_results: Whether to include fit parameters in output
    """
    if not peaks:
        raise ValueError("No peaks to save")

    # Convert peaks to dictionary format
    data = []
    for peak in peaks:
        row = peak.to_dict()
        if not include_fit_results:
            # Remove fit-specific fields
            for key in ['sigma', 'fwhm', 'area_fit', 'fit_params', 'fit_residual', 'fit_success']:
                row.pop(key, None)
        data.append(row)

    # Create DataFrame and save
    df = pd.DataFrame(data)

    # Reorder columns for readability
    preferred_order = [
        'status', 'center_tof', 'center_mz', 'height',
        'roi_start', 'roi_end',
        'area_integrated', 'area_manual', 'area_fit',
        'fwhm', 'sigma',
        'fit_residual', 'snr', 'quality_score', 'fit_success'
    ]
    existing_cols = [col for col in preferred_order if col in df.columns]
    other_cols = [col for col in df.columns if col not in existing_cols]
    df = df[existing_cols + other_cols]

    df.to_csv(file_path, index=False, float_format='%.6f', encoding='utf-8-sig')
    logger.info(f"Saved {len(peaks)} peaks to {file_path}")
