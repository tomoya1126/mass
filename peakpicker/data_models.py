# -*- coding: utf-8 -*-
"""
Data models for TOF-SIMS spectrum analysis.

This module defines the core data structures used throughout the application:
- Spectrum: Holds TOF/m/z and intensity data
- Peak: Represents a single identified or fitted peak
- ROI: Region of Interest for peak detection/fitting
"""

from dataclasses import dataclass, field
from typing import Optional, Dict, Any
import numpy as np


@dataclass
class Spectrum:
    """
    Represents a TOF-SIMS spectrum.

    Attributes:
        tof: Array of Time-of-Flight values
        intensity: Array of ion count/intensity values
        metadata: Optional dictionary for additional information (filename, conditions, etc.)
    """
    tof: np.ndarray
    intensity: np.ndarray
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        """Validate spectrum data after initialization."""
        if len(self.tof) != len(self.intensity):
            raise ValueError("TOF and intensity arrays must have the same length")
        if len(self.tof) == 0:
            raise ValueError("Spectrum data cannot be empty")

    def get_range(self, start: float, end: float):
        """
        Extract a subset of the spectrum within the given TOF range.

        Args:
            start: Start TOF value
            end: End TOF value

        Returns:
            Tuple of (tof_subset, intensity_subset)
        """
        mask = (self.tof >= start) & (self.tof <= end)
        return self.tof[mask], self.intensity[mask]

    def copy(self):
        """Create a deep copy of the spectrum."""
        return Spectrum(
            tof=self.tof.copy(),
            intensity=self.intensity.copy(),
            metadata=self.metadata.copy()
        )


@dataclass
class ROI:
    """
    Region of Interest for peak detection/fitting.

    Attributes:
        start: Start position (in TOF or m/z, depends on axis_type)
        end: End position (in TOF or m/z)
        axis_type: Either 'tof' or 'mz'
        label: Optional label for this ROI
    """
    start: float
    end: float
    axis_type: str = 'tof'  # 'tof' or 'mz'
    label: Optional[str] = None

    def __post_init__(self):
        """Validate ROI data."""
        if self.start >= self.end:
            raise ValueError(f"ROI start ({self.start}) must be less than end ({self.end})")
        if self.axis_type not in ['tof', 'mz']:
            raise ValueError(f"axis_type must be 'tof' or 'mz', got '{self.axis_type}'")

    @property
    def width(self) -> float:
        """Return the width of the ROI."""
        return self.end - self.start

    @property
    def center(self) -> float:
        """Return the center position of the ROI."""
        return (self.start + self.end) / 2


@dataclass
class Peak:
    """
    Represents a single identified or fitted peak.

    Attributes:
        center_tof: Peak center position in TOF
        center_mz: Peak center position in m/z (if calibrated)
        height: Peak height (maximum intensity)
        roi: ROI used for this peak (start/end range)

        # Fit-related attributes (populated after fitting)
        sigma: Gaussian sigma (or equivalent width parameter)
        fwhm: Full Width at Half Maximum
        area_integrated: Area calculated by simple numerical integration
        area_fit: Area calculated from fit parameters (e.g., Gaussian integral)
        fit_params: Dictionary of all fit parameters (model-specific)
        fit_residual: Fit quality metric (e.g., chi-square, R-squared)
        fit_success: Whether the fit converged successfully

        # Graphics references (for GUI)
        line: Reference to matplotlib line artist (for vertical line)
        text: Reference to matplotlib text artist (for label)
    """
    center_tof: float
    height: float
    roi: ROI
    center_mz: Optional[float] = None

    # State
    status: str = 'proposed'  # 'proposed', 'accepted', 'rejected'

    # Fit results
    sigma: Optional[float] = None
    fwhm: Optional[float] = None
    area_integrated: Optional[float] = None
    area_fit: Optional[float] = None
    fit_params: Optional[Dict[str, float]] = None
    fit_residual: Optional[float] = None
    fit_success: bool = False

    # Graphics references (not serialized)
    line: Any = field(default=None, repr=False)
    text: Any = field(default=None, repr=False)

    def __post_init__(self):
        """Initialize fit_params dictionary if not provided."""
        if self.fit_params is None:
            self.fit_params = {}

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert peak to dictionary (for export/serialization).
        Excludes graphics references.
        """
        return {
            'center_tof': self.center_tof,
            'center_mz': self.center_mz,
            'height': self.height,
            'roi_start': self.roi.start,
            'roi_end': self.roi.end,
            'status': self.status,
            'sigma': self.sigma,
            'fwhm': self.fwhm,
            'area_integrated': self.area_integrated,
            'area_fit': self.area_fit,
            'fit_params': self.fit_params,
            'fit_residual': self.fit_residual,
            'fit_success': self.fit_success
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Peak':
        """Create a Peak instance from a dictionary."""
        roi = ROI(
            start=data['roi_start'],
            end=data['roi_end'],
            axis_type='tof'
        )
        return cls(
            center_tof=data['center_tof'],
            center_mz=data.get('center_mz'),
            height=data['height'],
            roi=roi,
            status=data.get('status', 'proposed'),
            sigma=data.get('sigma'),
            fwhm=data.get('fwhm'),
            area_integrated=data.get('area_integrated'),
            area_fit=data.get('area_fit'),
            fit_params=data.get('fit_params'),
            fit_residual=data.get('fit_residual'),
            fit_success=data.get('fit_success', False)
        )


@dataclass
class CalibrationResult:
    """
    Result of mass calibration (TOF to m/z conversion).

    Calibration formula: t = A * sqrt(m/z) + B

    Attributes:
        A: Coefficient A in the calibration formula
        B: Coefficient B in the calibration formula
        A_err: Error/uncertainty in A (optional)
        B_err: Error/uncertainty in B (optional)
        r_squared: Goodness of fit (R²)
        peaks_used: Number of peaks used for calibration
    """
    A: float
    B: float
    A_err: Optional[float] = None
    B_err: Optional[float] = None
    r_squared: float = 0.0
    peaks_used: int = 0

    def tof_to_mz(self, tof: float) -> Optional[float]:
        """
        Convert TOF to m/z using the calibration formula.

        Args:
            tof: Time-of-Flight value

        Returns:
            m/z value, or None if calculation is invalid
        """
        if self.A == 0 or tof <= self.B:
            return None
        mz = ((tof - self.B) / self.A) ** 2
        return mz if mz > 0 else None

    def mz_to_tof(self, mz: float) -> float:
        """
        Convert m/z to TOF using the calibration formula.

        Args:
            mz: Mass-to-charge ratio

        Returns:
            TOF value
        """
        if mz <= 0:
            raise ValueError("m/z must be positive")
        return self.A * np.sqrt(mz) + self.B

    def to_dict(self) -> Dict[str, Any]:
        """Convert calibration to dictionary."""
        return {
            'A': self.A,
            'B': self.B,
            'A_err': self.A_err,
            'B_err': self.B_err,
            'r_squared': self.r_squared,
            'peaks_used': self.peaks_used
        }
