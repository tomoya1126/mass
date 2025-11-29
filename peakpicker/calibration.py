# -*- coding: utf-8 -*-
"""
Mass calibration module for TOF-SIMS analysis.

Handles TOF to m/z conversion using the formula: t = A * sqrt(m/z) + B
"""

import logging
import warnings
import numpy as np
from scipy.optimize import curve_fit, OptimizeWarning
from typing import List, Tuple, Optional
from .data_models import Peak, CalibrationResult


logger = logging.getLogger(__name__)


def calibrate_mass(peaks: List[Peak]) -> CalibrationResult:
    """
    Perform mass calibration using identified peaks.

    Fits the calibration formula: t = A * sqrt(m/z) + B

    Args:
        peaks: List of Peak objects with known m/z values

    Returns:
        CalibrationResult object with calibration parameters

    Raises:
        ValueError: If insufficient valid peaks (< 2) are provided
        RuntimeError: If fitting fails
    """
    # Filter valid peaks (must have both TOF and m/z)
    valid_peaks = [p for p in peaks if p.center_mz is not None and p.center_mz > 0]

    if len(valid_peaks) < 2:
        raise ValueError(
            f"At least 2 valid peaks with positive m/z are required for calibration. "
            f"Found {len(valid_peaks)} valid peaks."
        )

    # Extract TOF and m/z arrays
    tof_array = np.array([p.center_tof for p in valid_peaks])
    mz_array = np.array([float(p.center_mz) for p in valid_peaks])

    logger.info(f"Calibrating with {len(valid_peaks)} peaks")
    logger.debug(f"TOF values: {tof_array}")
    logger.debug(f"m/z values: {mz_array}")

    # Calculate initial guess for parameters
    p0 = _calculate_initial_guess(tof_array, mz_array)

    # Perform curve fitting
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", OptimizeWarning)

            popt, pcov = curve_fit(
                _calibration_func,
                mz_array,
                tof_array,
                p0=p0,
                maxfev=5000,
                check_finite=True
            )

        A, B = popt

        # Calculate parameter uncertainties
        A_err, B_err = None, None
        if pcov is not None and np.all(np.isfinite(pcov)):
            try:
                diag = np.diag(pcov)
                if np.all(diag >= 0):
                    perr = np.sqrt(diag)
                    if np.all(np.isfinite(perr)):
                        A_err, B_err = perr[0], perr[1]
            except Exception as e:
                logger.warning(f"Could not calculate parameter uncertainties: {e}")

        # Calculate goodness of fit (R²)
        residuals = tof_array - _calibration_func(mz_array, *popt)
        ss_res = np.sum(residuals ** 2)
        ss_tot = np.sum((tof_array - np.mean(tof_array)) ** 2)
        r_squared = 1 - (ss_res / ss_tot) if ss_tot > 1e-9 else 1.0

        logger.info(f"Calibration complete: A={A:.4f}, B={B:.4f}, R²={r_squared:.4f}")

        return CalibrationResult(
            A=A,
            B=B,
            A_err=A_err,
            B_err=B_err,
            r_squared=r_squared,
            peaks_used=len(valid_peaks)
        )

    except RuntimeError as e:
        logger.error(f"Calibration fitting failed: {e}")
        raise RuntimeError(f"Mass calibration failed: {str(e)}") from e


def _calibration_func(mz: np.ndarray, A: float, B: float) -> np.ndarray:
    """
    Calibration function: t = A * sqrt(m/z) + B

    Args:
        mz: Mass-to-charge ratio values
        A: Coefficient A
        B: Coefficient B

    Returns:
        TOF values
    """
    safe_mz = np.maximum(np.array(mz), 1e-9)  # Avoid sqrt of negative/zero
    return A * np.sqrt(safe_mz) + B


def _calculate_initial_guess(tof: np.ndarray, mz: np.ndarray) -> Optional[List[float]]:
    """
    Calculate initial guess for calibration parameters.

    Uses linear regression on sqrt(m/z) vs TOF.

    Args:
        tof: TOF values
        mz: m/z values

    Returns:
        [A, B] initial guess, or None if calculation fails
    """
    try:
        if len(mz) < 2 or mz.max() <= mz.min():
            return None

        # Find min and max m/z points
        min_idx = np.argmin(mz)
        max_idx = np.argmax(mz)

        tof_min, tof_max = tof[min_idx], tof[max_idx]
        sqrt_mz_min = np.sqrt(mz[min_idx])
        sqrt_mz_max = np.sqrt(mz[max_idx])

        if sqrt_mz_max > sqrt_mz_min:
            # Linear regression: tof = A * sqrt(mz) + B
            A_guess = (tof_max - tof_min) / (sqrt_mz_max - sqrt_mz_min)
            B_guess = tof_min - A_guess * sqrt_mz_min

            logger.debug(f"Initial guess: A={A_guess:.2f}, B={B_guess:.2f}")
            return [A_guess, B_guess]

    except Exception as e:
        logger.warning(f"Could not calculate initial guess: {e}")

    return None


def apply_calibration_to_peaks(peaks: List[Peak], calibration: CalibrationResult) -> None:
    """
    Apply calibration to update m/z values in peak list (in-place).

    Args:
        peaks: List of Peak objects
        calibration: CalibrationResult to apply
    """
    for peak in peaks:
        mz = calibration.tof_to_mz(peak.center_tof)
        if mz is not None:
            peak.center_mz = mz

    logger.info(f"Applied calibration to {len(peaks)} peaks")
