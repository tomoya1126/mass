# -*- coding: utf-8 -*-
"""
Control functionality for PeakPicker GUI.

Handles user interactions: calibration, peak fitting, range selection, etc.
"""

import logging
import tkinter as tk
import numpy as np
from scipy.ndimage import gaussian_filter1d
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

    def _get_detection_params(self: 'PeakPickerGUI'):
        """Parse detection parameters from UI inputs."""
        def _parse_float(entry_val):
            val = entry_val.strip().lower()
            if val in ('', 'auto', 'none'):
                return None
            try:
                return float(val)
            except ValueError:
                return None

        min_height = _parse_float(self.min_height_entry.get())
        prominence = _parse_float(self.prominence_entry.get())
        try:
            min_distance = int(float(self.min_distance_entry.get()))
        except ValueError:
            min_distance = self.config.peak_min_distance

        try:
            smoothing_sigma = float(self.fit_smoothing_entry.get())
        except ValueError:
            smoothing_sigma = self.config.peak_smoothing_sigma

        # Persist back to config for next session
        self.config.peak_min_height = min_height
        self.config.peak_prominence = prominence
        self.config.peak_min_distance = min_distance
        self.config.peak_smoothing_sigma = smoothing_sigma

        return PeakDetectionParams(
            min_height=min_height,
            min_distance=min_distance,
            prominence=prominence,
            smoothing_sigma=smoothing_sigma
        )

    def _current_baseline_mode(self: 'PeakPickerGUI') -> str:
        mode = self.baseline_mode.get()
        if mode not in ['none', 'constant', 'linear']:
            mode = 'none'
        self.config.baseline_mode = mode
        return mode

    def _get_fit_smoothing_sigma(self: 'PeakPickerGUI') -> float:
        try:
            sigma = float(self.fit_smoothing_entry.get())
            if sigma < 0:
                sigma = 0.0
        except ValueError:
            sigma = self.config.peak_smoothing_sigma
        self.config.peak_smoothing_sigma = sigma
        return sigma

    def calibrate_mass(self: 'PeakPickerGUI'):
        """Perform mass calibration using identified peaks."""
        # Need at least 2 peaks with m/z values
        valid_peaks = [
            p for p in self.peaks
            if p.center_mz is not None and p.center_mz > 0 and getattr(p, 'status', 'proposed') == 'accepted'
        ]

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

        baseline_mode = self._current_baseline_mode()
        smoothing_sigma = self._get_fit_smoothing_sigma()

        try:
            peak = fit_single_peak(self.spectrum, roi, smoothing_sigma=smoothing_sigma, baseline_mode=baseline_mode)

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
        params = self._get_detection_params()
        baseline_mode = self._current_baseline_mode()

        try:
            detected_peaks = detect_and_fit_peaks(
                self.spectrum, roi, params, baseline_mode=baseline_mode
            )

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

        mode = self._current_baseline_mode()
        val_str = self.baseline_entry.get().strip().lower()
        smoothing_sigma = self._get_fit_smoothing_sigma()

        if mode == 'none' or val_str in ['', 'none', 'auto']:
            # Restore original and optional smoothing
            self.spectrum.intensity = self.original_spectrum.intensity.copy()
        else:
            data = self.original_spectrum.intensity.copy()
            if mode == 'constant':
                try:
                    offset = float(val_str)
                except ValueError:
                    # auto mode: mean of edges
                    offset = float(np.mean(np.concatenate([data[:5], data[-5:]])))
                data = (data - offset)
                logger.info(f"Subtracted constant baseline: {offset}")
            elif mode == 'linear':
                x_edges = np.array([self.original_spectrum.tof[0], self.original_spectrum.tof[-1]])
                y_edges = np.array([data[0], data[-1]])
                coeffs = np.polyfit(x_edges, y_edges, 1)
                baseline_line = np.polyval(coeffs, self.original_spectrum.tof)
                data = data - baseline_line
                logger.info("Subtracted linear baseline")

            self.spectrum.intensity = data

        if smoothing_sigma and smoothing_sigma > 0:
            self.spectrum.intensity = gaussian_filter1d(self.spectrum.intensity, sigma=smoothing_sigma)
            logger.info(f"Applied smoothing sigma={smoothing_sigma}")

        self.spectrum.intensity = np.clip(self.spectrum.intensity, a_min=0, a_max=None)
        self.update_plot()

    # ========================================================================
    # Canvas event wiring
    # ========================================================================
    def _connect_plot_events(self: 'PeakPickerGUI'):
        """(Re)connect matplotlib canvas events safely."""
        if not hasattr(self, 'canvas'):
            return

        bindings = [
            ('click_cid', 'button_press_event', 'on_plot_click'),
            ('motion_cid', 'motion_notify_event', 'on_plot_motion'),
            ('release_cid', 'button_release_event', 'on_plot_release'),
            ('scroll_cid', 'scroll_event', 'on_scroll'),
        ]

        for cid_attr, event_name, handler_name in bindings:
            prev_cid = getattr(self, cid_attr, None)
            if prev_cid:
                try:
                    self.canvas.mpl_disconnect(prev_cid)
                except Exception:
                    pass

            handler = getattr(self, handler_name, None)
            if handler:
                new_cid = self.canvas.mpl_connect(event_name, handler)
                setattr(self, cid_attr, new_cid)

    def on_plot_click(self: 'PeakPickerGUI', event):
        """Handle mouse clicks for selection, drag, and context menu."""
        if event.inaxes != self.ax or self.spectrum is None:
            return

        # Right click: context menu
        if event.button == 3:
            self._show_context_menu(event)
            return

        # Only handle left button beyond this point
        if event.button != 1:
            return

        # Convert to TOF for internal use
        tof_pos = self._event_to_tof(event)
        if tof_pos is None:
            return

        # Double click toggles peak status
        if getattr(event, 'dblclick', False):
            self._handle_double_click(tof_pos, event)
            return

        # Begin drag for range selection
        self.drag_start = tof_pos
        self.dragging = False
        self._clear_drag_span()

        # Store click position so single clicks can still select even if release
        # events are missed on some platforms.
        self._select_nearest_peak(tof_pos)

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

    def on_plot_release(self: 'PeakPickerGUI', event):
        """Handle mouse release to finalize drag or click selection."""
        if event.button != 1 or self.spectrum is None:
            return

        tof_pos = self._event_to_tof(event)
        if tof_pos is None:
            self.drag_start = None
            self._clear_drag_span()
            return

        # Determine if this was a drag
        moved = self.dragging or (
            self.drag_start is not None and abs(tof_pos - self.drag_start) > self._drag_threshold()
        )
        if self.drag_start is not None and moved:
            start, end = sorted([self.drag_start, tof_pos])
            self.range_selection_points = [start, end]
            self.range_lines = []
            self._process_range_selection()
        else:
            # Treat as single click selection
            self._select_nearest_peak(tof_pos)

        self.drag_start = None
        self.dragging = False
        self._clear_drag_span()

        # Ensure range markers render immediately after selection
        if self.range_selection_points:
            self.update_plot()

    def on_scroll(self: 'PeakPickerGUI', event):
        """Handle wheel scroll for zooming and vertical scaling."""
        if event.inaxes != self.ax or self.spectrum is None:
            return

        # Determine wheel direction (mouse or trackpad)
        direction = 1
        if getattr(event, 'button', None) in ('up', 'down'):
            direction = 1 if event.button == 'up' else -1
        elif getattr(event, 'step', 0) != 0:
            direction = 1 if event.step > 0 else -1

        if event.key == 'control':
            # Adjust Y scale
            ylim = self.ax.get_ylim()
            scale = 0.9 if direction > 0 else 1.1
            center_y = (ylim[0] + ylim[1]) / 2
            new_range = (ylim[1] - ylim[0]) * scale / 2
            self.ax.set_ylim(max(0, center_y - new_range), center_y + new_range)
            self.canvas.draw_idle()
            return

        # X-axis zoom
        if event.xdata is None:
            return

        self.center_pos = self._event_to_tof(event)
        if self.center_pos is None:
            return

        # Up scroll zooms in, down scroll zooms out
        zoom_in_factor = 0.8
        zoom_out_factor = 1 / zoom_in_factor
        factor = zoom_in_factor if direction > 0 else zoom_out_factor

        current_width = self.ax.get_xlim()[1] - self.ax.get_xlim()[0]

        # Calculate maximum allowable width
        if self.axis_mode.get() == 'mz' and self.calibration:
            total_width = abs(
                self.calibration.tof_to_mz(self.spectrum.tof.max()) -
                self.calibration.tof_to_mz(self.spectrum.tof.min())
            )
        else:
            total_width = self.spectrum.tof.max() - self.spectrum.tof.min()

        new_width = max(1e-3, min(total_width, current_width * factor))
        self.window_size = new_width
        self.update_plot()

    def _event_to_tof(self: 'PeakPickerGUI', event):
        """Translate event x position to TOF regardless of axis mode."""
        if event.xdata is None:
            return None

        if self.axis_mode.get() == 'mz' and self.calibration:
            return self.calibration.mz_to_tof(event.xdata)
        return event.xdata

    def _drag_threshold(self: 'PeakPickerGUI') -> float:
        """Return a small x-range threshold to distinguish drag vs click."""
        x_min, x_max = self.ax.get_xlim()
        return max((x_max - x_min) * 0.001, 1e-6)

    def _handle_double_click(self: 'PeakPickerGUI', tof_pos: float, event):
        """Toggle peak status based on double click rules."""
        idx = self._find_nearest_peak_index(tof_pos)
        if idx is None:
            return

        self.selected_peak_index = idx
        shift_pressed = event.key == 'shift'
        if shift_pressed:
            self._set_peak_status(idx, 'rejected')
        else:
            current = self.peaks[idx].status
            new_state = 'accepted' if current != 'accepted' else 'proposed'
            self._set_peak_status(idx, new_state)

    def _select_nearest_peak(self: 'PeakPickerGUI', tof_pos: float):
        """Select the nearest peak to the given TOF position."""
        idx = self._find_nearest_peak_index(tof_pos)
        if idx is None:
            return

        self.selected_peak_index = idx
        self.update_plot()
        self._update_peak_table()

    def _find_nearest_peak_index(self: 'PeakPickerGUI', tof_pos: float):
        """Find nearest peak index to a TOF position."""
        if not self.peaks:
            return None

        distances = [abs(p.center_tof - tof_pos) for p in self.peaks]
        idx = int(np.argmin(distances))
        return idx

    def _set_peak_status(self: 'PeakPickerGUI', index: int, status: str):
        """Update peak status and refresh UI."""
        if status not in ['proposed', 'accepted', 'rejected']:
            return

        self.peaks[index].status = status
        self.selected_peak_index = index
        self.update_plot()
        self._update_peak_table()

    # ====================================================================
    # Peak review mode
    # ====================================================================
    def toggle_review_mode(self: 'PeakPickerGUI'):
        """Toggle keyboard-driven peak review mode."""
        if self.review_mode:
            self._stop_review_mode()
        else:
            self._start_review_mode()

    def _start_review_mode(self: 'PeakPickerGUI'):
        if not self.peaks:
            messagebox.showinfo("レビュー", "レビューするピークがありません。検出またはフィットしてください。")
            return

        self.review_mode = True
        # Prefer proposed peaks first
        proposed_indices = [i for i, p in enumerate(self.peaks) if p.status == 'proposed']
        self.selected_peak_index = proposed_indices[0] if proposed_indices else 0
        self.center_pos = self.peaks[self.selected_peak_index].center_tof
        self.review_btn.config(text="レビュー終了")

        # Bind keys
        if self.review_binding:
            self.root.unbind('<Key>', self.review_binding)
        self.review_binding = self.root.bind('<Key>', self._on_review_key)

        self._update_peak_table()
        self._update_info_text()
        self.update_plot()
        messagebox.showinfo(
            "レビュー開始",
            "A:採用 / D:却下 / S:保留\n← →: 前後のピークに移動",
        )

    def _stop_review_mode(self: 'PeakPickerGUI'):
        self.review_mode = False
        if self.review_binding:
            self.root.unbind('<Key>', self.review_binding)
            self.review_binding = None
        self.review_btn.config(text="ピークレビュー開始")
        self._update_info_text()
        self.update_plot()

    def _advance_review(self: 'PeakPickerGUI', step: int):
        if not self.peaks:
            self.selected_peak_index = -1
            return
        if self.selected_peak_index < 0:
            self.selected_peak_index = 0
        else:
            self.selected_peak_index = (self.selected_peak_index + step) % len(self.peaks)
        self.center_pos = self.peaks[self.selected_peak_index].center_tof
        self.update_plot()
        self._update_peak_table()

    def _on_review_key(self: 'PeakPickerGUI', event):
        if not self.review_mode:
            return

        key = event.keysym.lower()
        if key == 'a':
            self._set_peak_status(self.selected_peak_index, 'accepted')
            self._advance_review(1)
        elif key == 'd':
            self._set_peak_status(self.selected_peak_index, 'rejected')
            self._advance_review(1)
        elif key == 's':
            self._set_peak_status(self.selected_peak_index, 'proposed')
            self._advance_review(1)
        elif key in ('right', 'next'):
            self._advance_review(1)
        elif key in ('left', 'prior'):
            self._advance_review(-1)

    def _show_context_menu(self: 'PeakPickerGUI', event):
        """Display context menu depending on cursor location."""
        menu = tk.Menu(self.root, tearoff=0)
        tof_pos = self._event_to_tof(event)
        idx = self._find_nearest_peak_index(tof_pos) if tof_pos is not None else None

        if idx is not None:
            menu.add_command(label="このピークを採用", command=lambda: self._set_peak_status(idx, 'accepted'))
            menu.add_command(label="このピークを却下", command=lambda: self._set_peak_status(idx, 'rejected'))
            menu.add_separator()
            menu.add_command(label="このピークを単峰フィット", command=lambda: self._refit_peak_single(idx))
            menu.add_command(label="このピークと近傍を多峰フィット", command=lambda: self._refit_peak_multi(idx))
            menu.add_separator()
            menu.add_command(label="このピークにジャンプ", command=lambda: self._jump_to_peak(idx))
        else:
            menu.add_command(label="ここを中心にズームイン", command=lambda: self._zoom_to_position(tof_pos))

        try:
            menu.tk_popup(int(event.guiEvent.x_root), int(event.guiEvent.y_root))
        finally:
            menu.grab_release()

    def _jump_to_peak(self: 'PeakPickerGUI', index: int):
        """Center view on the specified peak."""
        self.selected_peak_index = index
        self.center_pos = self.peaks[index].center_tof
        self.update_plot()
        self._update_peak_table()

    def _zoom_to_position(self: 'PeakPickerGUI', tof_pos: float):
        """Center zoom around a specific TOF position."""
        if tof_pos is None:
            return
        self.center_pos = tof_pos
        self.window_size = max(self.window_size * 0.5, 1e-3)
        self.update_plot()

    def _refit_peak_single(self: 'PeakPickerGUI', index: int):
        """Re-fit a single peak around its current center."""
        if self.spectrum is None or not (0 <= index < len(self.peaks)):
            return
        peak = self.peaks[index]
        half_width = peak.fwhm * 2 if peak.fwhm else max(self.window_size * 0.1, 1.0)
        roi = ROI(
            start=max(self.spectrum.tof.min(), peak.center_tof - half_width),
            end=min(self.spectrum.tof.max(), peak.center_tof + half_width),
            axis_type='tof'
        )
        baseline_mode = self._current_baseline_mode()
        smoothing_sigma = self._get_fit_smoothing_sigma()

        try:
            new_peak = fit_single_peak(
                self.spectrum, roi,
                smoothing_sigma=smoothing_sigma,
                baseline_mode=baseline_mode
            )
            new_peak.status = peak.status
            if self.calibration:
                mz = self.calibration.tof_to_mz(new_peak.center_tof)
                new_peak.center_mz = mz if mz else peak.center_mz
            else:
                new_peak.center_mz = peak.center_mz
            self.peaks[index] = new_peak
            self.selected_peak_index = index
            self._update_peak_table()
            self.update_plot()
            logger.info("Re-fitted peak at index %s", index)
        except Exception as exc:
            messagebox.showerror("フィット失敗", f"単峰フィットに失敗しました:\n{exc}")

    def _refit_peak_multi(self: 'PeakPickerGUI', index: int):
        """Perform multi-peak fitting around the selected peak and neighbors."""
        if self.spectrum is None or not (0 <= index < len(self.peaks)):
            return
        center = self.peaks[index].center_tof
        window_half = max(self.window_size * 0.25, self.peaks[index].fwhm * 3 if self.peaks[index].fwhm else 10)
        roi = ROI(
            start=max(self.spectrum.tof.min(), center - window_half),
            end=min(self.spectrum.tof.max(), center + window_half),
            axis_type='tof'
        )

        # pick up to 3 closest peaks as initial centers
        sorted_peaks = sorted(self.peaks, key=lambda p: abs(p.center_tof - center))
        initial_centers = [p.center_tof for p in sorted_peaks[:3]]
        baseline_mode = self._current_baseline_mode()
        smoothing_sigma = self._get_fit_smoothing_sigma()

        try:
            fitted = fit_overlapping_peaks(
                self.spectrum, roi,
                n_peaks=min(3, len(initial_centers)),
                initial_centers=initial_centers,
                smoothing_sigma=smoothing_sigma,
                baseline_mode=baseline_mode
            )
            if not fitted:
                raise RuntimeError("多峰フィット結果が空です")
            # Replace peaks that fall inside ROI with fitted ones preserving status for nearest
            keep_outside = [p for p in self.peaks if not (roi.start <= p.center_tof <= roi.end)]
            # Transfer statuses heuristically
            for fitted_peak in fitted:
                nearest_original = min(self.peaks, key=lambda p: abs(p.center_tof - fitted_peak.center_tof))
                fitted_peak.status = nearest_original.status
                if self.calibration:
                    mz = self.calibration.tof_to_mz(fitted_peak.center_tof)
                    if mz:
                        fitted_peak.center_mz = mz
            self.peaks = sorted(keep_outside + fitted, key=lambda p: p.center_tof)
            self.selected_peak_index = self._find_nearest_peak_index(center)
            self._update_peak_table()
            self.update_plot()
            messagebox.showinfo("多峰フィット", f"{len(fitted)} 本のピークを再フィットしました。")
        except Exception as exc:
            messagebox.showerror("フィット失敗", f"多峰フィットに失敗しました:\n{exc}")

    def _clear_drag_span(self: 'PeakPickerGUI'):
        """Remove any temporary drag span overlay."""
        if self.drag_span is not None and self.drag_span in self.ax.patches:
            try:
                self.drag_span.remove()
            except Exception:
                pass
        self.drag_span = None

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
                peak_id = int(self.peak_tree.item(item, 'values')[1])
                self.selected_peak_index = peak_id - 1  # IDs are 1-indexed
                logger.debug(f"Selected peak index: {self.selected_peak_index}")
            except (ValueError, IndexError):
                self.selected_peak_index = -1

        self.update_plot()
