# -*- coding: utf-8 -*-
"""
Control functionality for PeakPicker GUI.

Handles user interactions: calibration, peak fitting, range selection, etc.
"""

import logging
import numpy as np
from tkinter import messagebox, simpledialog
from typing import TYPE_CHECKING

from .data_models import ROI
from .calibration import calibrate_mass
from .peak_fitting import (
    fit_single_peak,
    detect_and_fit_peaks,
    fit_overlapping_peaks,
    PeakDetectionParams
)

if TYPE_CHECKING:
    from .gui import PeakPickerGUI


logger = logging.getLogger(__name__)


class ControlsMixin:
    """Mixin class providing control methods for GUI."""

    def calibrate_mass(self: 'PeakPickerGUI'):
        """Perform mass calibration using identified peaks."""
        # Need at least 2 peaks with m/z values
        valid_peaks = [p for p in self.peaks if p.center_mz is not None and p.center_mz > 0]

        if len(valid_peaks) < 2:
            messagebox.showwarning(
                "キャリブレーションエラー",
                "キャリブレーションには少なくとも2つのピーク（正のm/z値付き）が必要です。"
            )
            return

        try:
            self.calibration = calibrate_mass(valid_peaks)

            msg = (
                f"m/z キャリブレーション完了\n\n"
                f"A = {self.calibration.A:.4f}"
            )
            if self.calibration.A_err:
                msg += f" ± {self.calibration.A_err:.4f}"

            msg += f"\nB = {self.calibration.B:.4f}"
            if self.calibration.B_err:
                msg += f" ± {self.calibration.B_err:.4f}"

            msg += f"\nR² = {self.calibration.r_squared:.4f}"
            msg += f"\n使用ピーク数: {self.calibration.peaks_used}"

            messagebox.showinfo("キャリブレーション成功", msg)

            # Update all peaks with new m/z values
            for peak in self.peaks:
                mz = self.calibration.tof_to_mz(peak.center_tof)
                if mz:
                    peak.center_mz = mz

            logger.info("Calibration successful")

            # Update UI
            self._update_button_states()
            self._update_peak_table()
            self._update_info_text()
            self.update_plot()

        except Exception as e:
            messagebox.showerror("キャリブレーションエラー", f"キャリブレーションに失敗しました:\n{e}")
            logger.error(f"Calibration error: {e}")

    def fit_selected_range(self: 'PeakPickerGUI'):
        """Fit a single peak in the user-selected range."""
        if self.spectrum is None:
            messagebox.showwarning("フィットエラー", "スペクトルデータを読み込んでください。")
            return

        if len(self.range_selection_points) != 2:
            messagebox.showwarning("フィットエラー", "プロット上で2点をクリックして範囲を選択してください。")
            return

        tof_start, tof_end = sorted(self.range_selection_points)
        roi = ROI(start=tof_start, end=tof_end, axis_type='tof')

        try:
            peak = fit_single_peak(self.spectrum, roi)

            # Assign m/z if calibrated
            if self.calibration:
                mz = self.calibration.tof_to_mz(peak.center_tof)
                if mz:
                    peak.center_mz = mz
            else:
                # Manual m/z input
                mz_str = simpledialog.askstring(
                    "m/z 入力",
                    f"ピーク中心 TOF: {peak.center_tof:.2f}\n整数 m/z を入力してください:",
                    parent=self.root
                )

                if mz_str:
                    try:
                        mz_int = int(mz_str)
                        if mz_int > 0:
                            peak.center_mz = float(mz_int)
                        else:
                            raise ValueError("m/z must be positive")
                    except ValueError as e:
                        messagebox.showerror("入力エラー", f"無効なm/z値: {mz_str}")
                        logger.error(f"Invalid m/z input: {e}")
                        return

            # Add peak to list
            self.peaks.append(peak)
            self.peaks.sort(key=lambda p: p.center_tof)

            logger.info(f"Fitted peak: TOF={peak.center_tof:.2f}, m/z={peak.center_mz}, "
                       f"FWHM={peak.fwhm:.2f}, Area={peak.area_fit:.1f}")

            # Clear range selection
            self.range_selection_points = []
            self.range_lines = []

            # Update UI
            self._update_peak_table()
            self._update_info_text()
            self.update_plot()

            messagebox.showinfo("フィット成功", f"ピークをフィットしました\n"
                                              f"TOF: {peak.center_tof:.2f}\n"
                                              f"FWHM: {peak.fwhm:.2f}\n"
                                              f"面積: {peak.area_fit:.1f}")

        except Exception as e:
            messagebox.showerror("フィットエラー", f"ピークフィットに失敗しました:\n{e}")
            logger.error(f"Single peak fit error: {e}")

    def auto_detect_and_fit(self: 'PeakPickerGUI'):
        """Automatically detect and fit multiple peaks in selected range."""
        if self.spectrum is None:
            messagebox.showwarning("エラー", "スペクトルデータを読み込んでください。")
            return

        if len(self.range_selection_points) != 2:
            messagebox.showwarning("エラー", "プロット上で2点をクリックして範囲を選択してください。")
            return

        tof_start, tof_end = sorted(self.range_selection_points)
        roi = ROI(start=tof_start, end=tof_end, axis_type='tof')

        # Get detection parameters from config
        params = PeakDetectionParams(
            min_height=self.config.peak_min_height,
            min_distance=self.config.peak_min_distance,
            prominence=self.config.peak_prominence,
            smoothing_sigma=self.config.peak_smoothing_sigma
        )

        try:
            detected_peaks = detect_and_fit_peaks(self.spectrum, roi, params)

            if not detected_peaks:
                messagebox.showinfo("ピーク検出", "指定範囲にピークが検出されませんでした。")
                return

            # Assign m/z values if calibrated
            if self.calibration:
                for peak in detected_peaks:
                    mz = self.calibration.tof_to_mz(peak.center_tof)
                    if mz:
                        peak.center_mz = mz

            # Add to peak list
            self.peaks.extend(detected_peaks)
            self.peaks.sort(key=lambda p: p.center_tof)

            logger.info(f"Auto-detected and fitted {len(detected_peaks)} peaks")

            # Clear range selection
            self.range_selection_points = []
            self.range_lines = []

            # Update UI
            self._update_peak_table()
            self._update_info_text()
            self.update_plot()

            messagebox.showinfo("ピーク検出成功", f"{len(detected_peaks)}個のピークを検出・フィットしました。")

        except Exception as e:
            messagebox.showerror("検出エラー", f"ピーク検出に失敗しました:\n{e}")
            logger.error(f"Auto-detect error: {e}")

    def delete_selected_peak(self: 'PeakPickerGUI'):
        """Delete the currently selected peak."""
        if self.selected_peak_index == -1:
            messagebox.showwarning("削除", "削除するピークを選択してください。")
            return

        if not (0 <= self.selected_peak_index < len(self.peaks)):
            messagebox.showerror("エラー", "選択されたピークのインデックスが無効です。")
            self.selected_peak_index = -1
            return

        peak = self.peaks[self.selected_peak_index]

        # Confirm deletion
        mz_str = f"{int(round(peak.center_mz))}" if peak.center_mz else "N/A"
        if not messagebox.askyesno("削除確認",
                                   f"選択されたピークを削除しますか?\n"
                                   f"TOF: {peak.center_tof:.2f}\n"
                                   f"m/z: {mz_str}"):
            return

        # Delete peak
        del self.peaks[self.selected_peak_index]
        self.selected_peak_index = -1

        logger.info(f"Deleted peak at TOF={peak.center_tof:.2f}")

        # Update UI
        self._update_peak_table()
        self._update_info_text()
        self.update_plot()

        # Check if recalibration is needed
        if self.calibration:
            valid_peaks = [p for p in self.peaks if p.center_mz is not None and p.center_mz > 0]
            if len(valid_peaks) < 2:
                messagebox.showwarning("キャリブレーション", "有効なピークが2個未満になったため、キャリブレーションをクリアしました。")
                self.calibration = None
                self._update_button_states()

    def subtract_baseline(self: 'PeakPickerGUI'):
        """Subtract baseline from spectrum."""
        if self.spectrum is None or self.original_spectrum is None:
            messagebox.showwarning("BG減算", "スペクトルデータを読み込んでください。")
            return

        val_str = self.baseline_entry.get().strip()

        if not val_str:
            # Restore original
            if not np.array_equal(self.spectrum.intensity, self.original_spectrum.intensity):
                self.spectrum.intensity = self.original_spectrum.intensity.copy()
                logger.info("Restored original intensity")
                self.update_plot()
                self.baseline_entry.delete(0, 'end')
            return

        try:
            val = float(val_str)
            self.spectrum.intensity = (self.original_spectrum.intensity - val).clip(min=0)
            logger.info(f"Subtracted baseline: {val}")
            self.update_plot()

        except ValueError:
            messagebox.showerror("入力エラー", "有効な数値を入力してください。")

    def on_plot_click(self: 'PeakPickerGUI', event):
        """Handle mouse click on plot (range selection)."""
        if event.inaxes != self.ax or event.button != 1 or self.spectrum is None:
            return

        # Get position in TOF (always work in TOF internally)
        if self.axis_mode.get() == 'mz' and self.calibration:
            mz_pos = event.xdata
            tof_pos = self.calibration.mz_to_tof(mz_pos)
        else:
            tof_pos = event.xdata

        # Reset if starting new selection
        if len(self.range_selection_points) == 0:
            self.range_lines = []

        self.range_selection_points.append(tof_pos)

        logger.debug(f"Range point {len(self.range_selection_points)}: TOF={tof_pos:.2f}")

        # Draw marker
        self.update_plot()

        # Process range if 2 points selected
        if len(self.range_selection_points) == 2:
            self._process_range_selection()

    def _process_range_selection(self: 'PeakPickerGUI'):
        """Process the selected range based on current mode."""
        mode = self.analysis_mode.get()

        if mode == 'peak_assign':
            # Wait for user to trigger fit manually
            logger.info("Range selected. Use fit button to proceed.")

        elif mode == 'count_sum':
            # Integrate counts in the selected range
            tof_start, tof_end = sorted(self.range_selection_points)

            tof_data, intensity_data = self.spectrum.get_range(tof_start, tof_end)

            if len(tof_data) == 0:
                messagebox.showwarning("積算エラー", "選択範囲にデータがありません。")
                self.range_selection_points = []
                return

            total_counts = np.sum(intensity_data)
            max_idx = np.argmax(intensity_data)
            peak_tof = tof_data[max_idx]
            max_count = intensity_data[max_idx]

            # Calculate m/z
            calc_mz_int = None
            if self.calibration:
                mz = self.calibration.tof_to_mz(peak_tof)
                if mz and mz > 0:
                    calc_mz_int = int(round(mz))
            else:
                messagebox.showwarning("キャリブレーション未実施", "m/zキャリブレーションが未実施です。'未較正'として積算します。")
                calc_mz_int = -1  # Uncalibrated key

            if calc_mz_int is not None:
                result = {
                    'Range_Start': tof_start,
                    'Range_End': tof_end,
                    'Total_Counts': total_counts,
                    'Max_Count_TOF': peak_tof,
                    'Max_Count': max_count
                }

                mz_key_disp = f"{calc_mz_int}" if calc_mz_int != -1 else "未較正"

                if calc_mz_int in self.summation_results_dict:
                    # Add to existing
                    self.summation_results_dict[calc_mz_int]['Total_Counts'] += total_counts
                    # Update other fields to latest range
                    for k, v in result.items():
                        if k != 'Total_Counts':
                            self.summation_results_dict[calc_mz_int][k] = v
                    logger.info(f"Updated integration for m/z={mz_key_disp}: Total={self.summation_results_dict[calc_mz_int]['Total_Counts']:.1f}")
                else:
                    # New entry
                    self.summation_results_dict[calc_mz_int] = result
                    logger.info(f"New integration for m/z={mz_key_disp}: Total={total_counts:.1f}")

                self._update_info_text()

            # Clear range
            self.range_selection_points = []
            self.range_lines = []
            self.update_plot()

    def on_axis_mode_change(self: 'PeakPickerGUI'):
        """Handle axis mode change (TOF/m/z)."""
        mode = self.axis_mode.get()
        logger.info(f"Axis mode changed to: {mode}")

        # Disable m/z mode if not calibrated
        if mode == 'mz' and self.calibration is None:
            messagebox.showwarning("m/z表示", "m/z表示にはキャリブレーションが必要です。")
            self.axis_mode.set('tof')
            return

        self.update_plot()

    def on_mode_change(self: 'PeakPickerGUI'):
        """Handle analysis mode change."""
        mode = self.analysis_mode.get()
        logger.info(f"Analysis mode changed to: {mode}")

        # Clear range selection
        self.range_selection_points = []
        self.range_lines = []
        self.update_plot()
        self._update_info_text()

    def on_peak_table_select(self: 'PeakPickerGUI', event):
        """Handle peak table selection."""
        selection = self.peak_tree.selection()

        if not selection:
            self.selected_peak_index = -1
        else:
            item = selection[0]
            try:
                # Get peak ID from first column
                peak_id = int(self.peak_tree.item(item, 'values')[0])
                self.selected_peak_index = peak_id - 1  # IDs are 1-indexed
                logger.debug(f"Selected peak index: {self.selected_peak_index}")
            except (ValueError, IndexError):
                self.selected_peak_index = -1

        self.update_plot()
