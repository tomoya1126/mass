# -*- coding: utf-8 -*-
"""
Peak fitting module for TOF-SIMS spectrum analysis.

Provides automatic peak fitting capabilities:
- Level 1: Single peak fitting in a user-selected range
- Level 2: Auto-detect and fit multiple peaks in a range
- Level 3: Multi-peak fitting for overlapping peaks
"""

import logging
import warnings
import numpy as np
from scipy.optimize import curve_fit, OptimizeWarning
from scipy.signal import find_peaks as scipy_find_peaks
from scipy.ndimage import gaussian_filter1d
from typing import List, Tuple, Optional, Dict, Any
from .data_models import Spectrum, Peak, ROI


logger = logging.getLogger(__name__)


# ============================================================================
# Peak Models
# ============================================================================

def gaussian(x: np.ndarray, amp: float, center: float, sigma: float, offset: float) -> np.ndarray:
    """
    Gaussian peak model.

    Args:
        x: Independent variable (TOF)
        amp: Amplitude (peak height above offset)
        center: Peak center position
        sigma: Standard deviation (width parameter)
        offset: Baseline offset

    Returns:
        y values
    """
    return amp * np.exp(-((x - center) ** 2) / (2 * sigma ** 2)) + offset


def multi_gaussian(x: np.ndarray, *params) -> np.ndarray:
    """
    Sum of multiple Gaussian peaks with shared offset.

    Args:
        x: Independent variable
        params: [amp1, center1, sigma1, amp2, center2, sigma2, ..., offset]
                Last parameter is the shared offset

    Returns:
        Sum of all Gaussians plus offset
    """
    n_peaks = (len(params) - 1) // 3
    offset = params[-1]
    y = np.zeros_like(x) + offset

    for i in range(n_peaks):
        amp = params[i * 3]
        center = params[i * 3 + 1]
        sigma = params[i * 3 + 2]
        y += amp * np.exp(-((x - center) ** 2) / (2 * sigma ** 2))

    return y


def calculate_fwhm(sigma: float) -> float:
    """Calculate FWHM from Gaussian sigma."""
    return 2.355 * sigma  # 2 * sqrt(2 * ln(2)) * sigma


def calculate_gaussian_area(amp: float, sigma: float) -> float:
    """Calculate analytical area of a Gaussian peak."""
    return amp * sigma * np.sqrt(2 * np.pi)


def preprocess_signal(
    spectrum: Spectrum,
    roi: ROI,
    smoothing_sigma: float = 0.0,
    baseline_mode: str = "none"
) -> Tuple[np.ndarray, np.ndarray, float]:
    """
    Apply smoothing and baseline correction on a ROI.

    Returns processed intensity along with the baseline used for quality metrics.
    """
    tof_data, intensity_data = spectrum.get_range(roi.start, roi.end)
    if len(tof_data) == 0:
        return tof_data, intensity_data, 0.0

    if smoothing_sigma and smoothing_sigma > 0:
        intensity_proc = gaussian_filter1d(intensity_data, sigma=smoothing_sigma)
    else:
        intensity_proc = intensity_data.copy()

    baseline = 0.0
    if baseline_mode == "constant":
        edge_points = np.concatenate([intensity_proc[:3], intensity_proc[-3:]])
        baseline = float(np.mean(edge_points)) if len(edge_points) else 0.0
        intensity_proc = intensity_proc - baseline
    elif baseline_mode == "linear" and len(tof_data) >= 2:
        # Fit simple line through edges and subtract
        x_edges = np.array([tof_data[0], tof_data[-1]])
        y_edges = np.array([intensity_proc[0], intensity_proc[-1]])
        coeffs = np.polyfit(x_edges, y_edges, 1)
        baseline_line = np.polyval(coeffs, tof_data)
        baseline = float(np.mean(baseline_line))
        intensity_proc = intensity_proc - baseline_line

    return tof_data, intensity_proc, baseline


# ============================================================================
# Level 1: Single Peak Fitting
# ============================================================================

def fit_single_peak(
    spectrum: Spectrum,
    roi: ROI,
    model: str = 'gaussian',
    smoothing_sigma: float = 0.0,
    baseline_mode: str = "none"
) -> Peak:
    """
    Fit a single peak within the specified ROI.

    Args:
        spectrum: Spectrum object
        roi: ROI defining the fitting range
        model: Peak model to use (currently only 'gaussian' supported)

    Returns:
        Peak object with fit results

    Raises:
        ValueError: If ROI is invalid or no data in range
        RuntimeError: If fitting fails
    """
    logger.info(f"Fitting single peak in range {roi.start:.2f} - {roi.end:.2f}")

    # Extract data in ROI with preprocessing
    tof_data, intensity_data, baseline_used = preprocess_signal(
        spectrum, roi, smoothing_sigma=smoothing_sigma, baseline_mode=baseline_mode
    )

    if len(tof_data) == 0:
        raise ValueError(f"No data points found in ROI {roi.start} - {roi.end}")

    if len(tof_data) < 4:
        raise ValueError(f"Insufficient data points ({len(tof_data)}) for fitting. Need at least 4.")

    # Calculate initial parameters
    max_idx = np.argmax(intensity_data)
    center_init = tof_data[max_idx]
    height_init = intensity_data[max_idx]

    # Estimate baseline from edge points
    edge_points = np.concatenate([intensity_data[:3], intensity_data[-3:]])
    offset_init = np.mean(edge_points) if len(edge_points) > 0 else np.min(intensity_data)

    amp_init = height_init - offset_init
    if amp_init <= 0:
        amp_init = height_init * 0.5

    # Estimate sigma from range width
    sigma_init = (roi.end - roi.start) / 6.0

    p0 = [amp_init, center_init, sigma_init, offset_init]
    logger.debug(f"Initial guess: amp={amp_init:.1f}, center={center_init:.2f}, "
                 f"sigma={sigma_init:.2f}, offset={offset_init:.1f}")

    # Set parameter bounds
    bounds = (
        [0, roi.start, 0, -np.inf],  # Lower bounds
        [np.inf, roi.end, (roi.end - roi.start), np.inf]  # Upper bounds
    )

    # Perform fit
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", OptimizeWarning)

            popt, pcov = curve_fit(
                gaussian,
                tof_data,
                intensity_data,
                p0=p0,
                bounds=bounds,
                maxfev=5000
            )

        amp_fit, center_fit, sigma_fit, offset_fit = popt

        # Validate fit result
        if sigma_fit <= 0 or center_fit < roi.start or center_fit > roi.end:
            raise RuntimeError("Fit resulted in invalid parameters")

        # Calculate derived quantities
        height_fit = amp_fit + offset_fit
        fwhm = calculate_fwhm(sigma_fit)
        area_fit = calculate_gaussian_area(amp_fit, sigma_fit)

        # Calculate simple numerical integration for comparison
        area_integrated = np.trapz(intensity_data - offset_fit, tof_data)

        # Calculate residual (chi-square) and SNR
        y_fit = gaussian(tof_data, *popt)
        residuals = intensity_data - y_fit
        chi_square = np.sum(residuals ** 2) / len(tof_data)
        noise_floor = np.std(residuals) if len(residuals) > 1 else 0.0
        snr = (amp_fit / noise_floor) if noise_floor > 0 else None
        # Quality score: heuristic between 0 and 1
        quality_score = None
        if snr is not None:
            quality_score = max(0.0, min(1.0, 1.0 - min(chi_square, 1e6) / (1e3 + chi_square) + np.tanh(snr / 10) * 0.5))

        logger.info(f"Fit successful: center={center_fit:.2f}, sigma={sigma_fit:.2f}, "
                    f"FWHM={fwhm:.2f}, area={area_fit:.1f}")

        # Create Peak object
        peak = Peak(
            center_tof=center_fit,
            height=height_fit,
            roi=roi,
            sigma=sigma_fit,
            fwhm=fwhm,
            area_integrated=area_integrated,
            area_fit=area_fit,
            fit_params={
                'amp': amp_fit,
                'center': center_fit,
                'sigma': sigma_fit,
                'offset': offset_fit
            },
            fit_residual=chi_square,
            snr=snr,
            quality_score=quality_score,
            fit_success=True
        )

        return peak

    except Exception as e:
        logger.error(f"Single peak fit failed: {e}")
        raise RuntimeError(f"Peak fitting failed: {str(e)}") from e


# ============================================================================
# Level 2: Auto-detect and fit multiple peaks
# ============================================================================

class PeakDetectionParams:
    """Parameters for automatic peak detection."""

    def __init__(
        self,
        min_height: Optional[float] = None,
        min_distance: int = 10,
        prominence: Optional[float] = None,
        smoothing_sigma: float = 2.0
    ):
        """
        Args:
            min_height: Minimum peak height (intensity). If None, auto-calculated
            min_distance: Minimum distance between peaks (in data points)
            prominence: Minimum prominence of peaks. If None, auto-calculated
            smoothing_sigma: Sigma for Gaussian smoothing (0 = no smoothing)
        """
        self.min_height = min_height
        self.min_distance = min_distance
        self.prominence = prominence
        self.smoothing_sigma = smoothing_sigma


def detect_and_fit_peaks(
    spectrum: Spectrum,
    roi: ROI,
    params: Optional[PeakDetectionParams] = None,
    baseline_mode: str = "none"
) -> List[Peak]:
    """
    Automatically detect and fit multiple peaks within a range.

    Args:
        spectrum: Spectrum object
        roi: ROI defining the search range
        params: Peak detection parameters. If None, uses defaults.

    Returns:
        List of fitted Peak objects

    Raises:
        ValueError: If ROI is invalid
    """
    if params is None:
        params = PeakDetectionParams()

    logger.info(f"Auto-detecting peaks in range {roi.start:.2f} - {roi.end:.2f}")

    # Extract data in ROI
    tof_data, intensity_data, _ = preprocess_signal(
        spectrum, roi, smoothing_sigma=params.smoothing_sigma if params else 0.0, baseline_mode=baseline_mode
    )

    if len(tof_data) == 0:
        logger.warning("No data in ROI")
        return []

    # Apply smoothing if requested
    if params.smoothing_sigma > 0:
        intensity_smooth = gaussian_filter1d(intensity_data, sigma=params.smoothing_sigma)
    else:
        intensity_smooth = intensity_data

    # Auto-calculate parameters if not provided
    baseline = np.percentile(intensity_smooth, 10)
    noise_std = np.std(intensity_smooth[intensity_smooth < np.percentile(intensity_smooth, 25)])

    min_height = params.min_height
    if min_height is None:
        min_height = baseline + 3 * noise_std

    prominence = params.prominence
    if prominence is None:
        prominence = 2 * noise_std

    logger.debug(f"Detection params: min_height={min_height:.1f}, prominence={prominence:.1f}, "
                 f"min_distance={params.min_distance}")

    # Find peaks
    peak_indices, properties = scipy_find_peaks(
        intensity_smooth,
        height=min_height,
        distance=params.min_distance,
        prominence=prominence
    )

    if len(peak_indices) == 0:
        logger.info("No peaks detected in range")
        return []

    logger.info(f"Detected {len(peak_indices)} peaks")

    # Fit each detected peak
    fitted_peaks = []
    for idx in peak_indices:
        peak_tof = tof_data[idx]

        # Define local ROI for this peak
        # Use adaptive window based on local data spacing
        tof_step = np.median(np.diff(tof_data))
        window_half = max(params.min_distance * tof_step, (roi.end - roi.start) / 20)

        peak_roi = ROI(
            start=max(roi.start, peak_tof - window_half),
            end=min(roi.end, peak_tof + window_half),
            axis_type='tof'
        )

        try:
            peak = fit_single_peak(
                spectrum,
                peak_roi,
                smoothing_sigma=params.smoothing_sigma,
                baseline_mode=baseline_mode
            )
            fitted_peaks.append(peak)
            logger.debug(f"Fitted peak at TOF={peak.center_tof:.2f}")
        except Exception as e:
            logger.warning(f"Failed to fit peak at TOF={peak_tof:.2f}: {e}")
            continue

    logger.info(f"Successfully fitted {len(fitted_peaks)} / {len(peak_indices)} detected peaks")

    return fitted_peaks


# ============================================================================
# Level 3: Multi-peak fitting for overlapping peaks
# ============================================================================

def fit_overlapping_peaks(
    spectrum: Spectrum,
    roi: ROI,
    n_peaks: int = 2,
    initial_centers: Optional[List[float]] = None,
    smoothing_sigma: float = 0.0,
    baseline_mode: str = "none"
) -> List[Peak]:
    """
    Fit multiple overlapping Gaussian peaks simultaneously.

    Args:
        spectrum: Spectrum object
        roi: ROI containing the overlapping peaks
        n_peaks: Number of peaks to fit (2 or 3 recommended)
        initial_centers: Optional list of initial peak center positions.
                        If None, attempts auto-detection.

    Returns:
        List of fitted Peak objects

    Raises:
        ValueError: If parameters are invalid
        RuntimeError: If fitting fails
    """
    if n_peaks < 2 or n_peaks > 3:
        logger.warning(f"n_peaks={n_peaks} may be unstable. Recommend 2-3 peaks.")

    logger.info(f"Fitting {n_peaks} overlapping peaks in range {roi.start:.2f} - {roi.end:.2f}")

    # Extract data
    tof_data, intensity_data, _ = preprocess_signal(
        spectrum, roi, smoothing_sigma=smoothing_sigma, baseline_mode=baseline_mode
    )

    if len(tof_data) < n_peaks * 4:
        raise ValueError(f"Insufficient data points ({len(tof_data)}) for fitting {n_peaks} peaks")

    # Determine initial centers
    if initial_centers is None:
        # Auto-detect using peak finding
        params = PeakDetectionParams(min_distance=len(tof_data) // (n_peaks + 1))
        detected = detect_and_fit_peaks(spectrum, roi, params)

        if len(detected) < n_peaks:
            # Fallback: evenly space peaks
            logger.warning(f"Only detected {len(detected)} peaks, using evenly spaced initial centers")
            initial_centers = [roi.start + (roi.end - roi.start) * (i + 1) / (n_peaks + 1)
                               for i in range(n_peaks)]
        else:
            initial_centers = [p.center_tof for p in detected[:n_peaks]]

    if len(initial_centers) != n_peaks:
        raise ValueError(f"initial_centers must have length {n_peaks}, got {len(initial_centers)}")

    # Estimate initial parameters for each peak
    offset_init = np.percentile(intensity_data, 10)
    p0 = []
    bounds_lower = []
    bounds_upper = []

    for center_init in initial_centers:
        # Find nearest data point
        nearest_idx = np.argmin(np.abs(tof_data - center_init))
        amp_init = max(intensity_data[nearest_idx] - offset_init, 1.0)
        sigma_init = (roi.end - roi.start) / (n_peaks * 3)

        p0.extend([amp_init, center_init, sigma_init])

        # Bounds for this peak
        bounds_lower.extend([0, roi.start, 0])
        bounds_upper.extend([np.inf, roi.end, roi.end - roi.start])

    # Add shared offset
    p0.append(offset_init)
    bounds_lower.append(-np.inf)
    bounds_upper.append(np.inf)

    logger.debug(f"Initial guess for {n_peaks} peaks: {p0}")

    # Perform fit
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", OptimizeWarning)

            popt, pcov = curve_fit(
                multi_gaussian,
                tof_data,
                intensity_data,
                p0=p0,
                bounds=(bounds_lower, bounds_upper),
                maxfev=10000
            )

        offset_fit = popt[-1]

        # Extract individual peak parameters
        fitted_peaks = []
        for i in range(n_peaks):
            amp_fit = popt[i * 3]
            center_fit = popt[i * 3 + 1]
            sigma_fit = popt[i * 3 + 2]

            # Validate
            if sigma_fit <= 0 or center_fit < roi.start or center_fit > roi.end:
                logger.warning(f"Peak {i+1} has invalid parameters, skipping")
                continue

            height_fit = amp_fit + offset_fit
            fwhm = calculate_fwhm(sigma_fit)
            area_fit = calculate_gaussian_area(amp_fit, sigma_fit)
            area_integrated = np.trapz(intensity_data - offset_fit, tof_data)

            # Create individual ROI for this peak (approximate)
            peak_roi = ROI(
                start=center_fit - 2 * sigma_fit,
                end=center_fit + 2 * sigma_fit,
                axis_type='tof'
            )

            peak = Peak(
                center_tof=center_fit,
                height=height_fit,
                roi=peak_roi,
                sigma=sigma_fit,
                fwhm=fwhm,
                area_fit=area_fit,
                area_integrated=area_integrated,
                fit_params={
                    'amp': amp_fit,
                    'center': center_fit,
                    'sigma': sigma_fit,
                    'offset': offset_fit,
                    'multi_peak_index': i
                },
                fit_success=True
            )

            fitted_peaks.append(peak)
            logger.debug(f"Peak {i+1}: center={center_fit:.2f}, sigma={sigma_fit:.2f}")

        # Calculate overall fit quality
        y_fit = multi_gaussian(tof_data, *popt)
        residuals = intensity_data - y_fit
        chi_square = np.sum(residuals ** 2) / len(tof_data)

        noise_floor = np.std(residuals) if len(residuals) > 1 else 0.0
        for peak in fitted_peaks:
            peak.fit_residual = chi_square
            if noise_floor > 0:
                amp = peak.fit_params.get('amp', peak.height)
                peak.snr = amp / noise_floor
                peak.quality_score = max(0.0, min(1.0, 1.0 - min(chi_square, 1e6) / (1e3 + chi_square) + np.tanh(peak.snr / 10) * 0.5))

        logger.info(f"Multi-peak fit successful: fitted {len(fitted_peaks)} peaks, χ²={chi_square:.2e}")

        return fitted_peaks

    except Exception as e:
        logger.error(f"Multi-peak fit failed: {e}")
        raise RuntimeError(f"Multi-peak fitting failed: {str(e)}") from e
