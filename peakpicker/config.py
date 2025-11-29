# -*- coding: utf-8 -*-
"""
Configuration management for PeakPicker application.
"""

import json
import logging
import os
from typing import Dict, Any
from dataclasses import dataclass, asdict


logger = logging.getLogger(__name__)


@dataclass
class AppConfig:
    """Application configuration settings."""

    # Peak detection parameters
    peak_min_height: float = None  # None = auto
    peak_min_distance: int = 10
    peak_prominence: float = None  # None = auto
    peak_smoothing_sigma: float = 2.0

    # Window settings
    window_width: int = 1200
    window_height: int = 800

    # Default directories
    last_directory: str = ""

    # Visualization
    default_zoom_window: int = 5000

    def to_dict(self) -> Dict[str, Any]:
        """Convert config to dictionary."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'AppConfig':
        """Create config from dictionary."""
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


def load_config(config_path: str = "peakpicker_config.json") -> AppConfig:
    """
    Load configuration from JSON file.

    Args:
        config_path: Path to config file

    Returns:
        AppConfig object (default if file doesn't exist)
    """
    if os.path.exists(config_path):
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            logger.info(f"Loaded configuration from {config_path}")
            return AppConfig.from_dict(data)
        except Exception as e:
            logger.warning(f"Failed to load config from {config_path}: {e}")
            return AppConfig()
    else:
        logger.info("No config file found, using defaults")
        return AppConfig()


def save_config(config: AppConfig, config_path: str = "peakpicker_config.json") -> None:
    """
    Save configuration to JSON file.

    Args:
        config: AppConfig object
        config_path: Path to save config file
    """
    try:
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(config.to_dict(), f, indent=2)
        logger.info(f"Saved configuration to {config_path}")
    except Exception as e:
        logger.error(f"Failed to save config to {config_path}: {e}")


def setup_logging(log_file: str = "peakpicker.log", level: int = logging.INFO) -> None:
    """
    Setup logging configuration.

    Args:
        log_file: Path to log file
        level: Logging level
    """
    # Create formatters
    file_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    console_formatter = logging.Formatter(
        '%(levelname)s: %(message)s'
    )

    # File handler
    file_handler = logging.FileHandler(log_file, encoding='utf-8')
    file_handler.setLevel(level)
    file_handler.setFormatter(file_formatter)

    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(console_formatter)

    # Root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)

    logger.info("Logging configured")
