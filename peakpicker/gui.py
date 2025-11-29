# -*- coding: utf-8 -*-
"""
Main GUI module for PeakPicker application.
"""

import os
import logging
import traceback
from collections import OrderedDict
from typing import List, Optional

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import matplotlib as mpl

import tkinter as tk
from tkinter import (
    filedialog, simpledialog, messagebox,
    Frame, Button, Label, Entry, Scale, Text, StringVar, Radiobutton,
    ttk, LEFT, RIGHT, BOTH, TOP, BOTTOM, X, Y, END, HORIZONTAL
)

from .data_models import Spectrum, Peak, ROI, CalibrationResult
from .file_io import read_spectrum_file, save_peaks_to_csv, FileReadError
from .calibration import calibrate_mass
from .peak_fitting import (
    fit_single_peak,
    detect_and_fit_peaks,
    fit_overlapping_peaks,
    PeakDetectionParams
)
from .config import AppConfig
from .gui_plotting import PlottingMixin
from .gui_controls import ControlsMixin


logger = logging.getLogger(__name__)


class PeakPickerGUI(PlottingMixin, ControlsMixin):
    """Main GUI application for TOF-SIMS spectrum analysis."""

    def __init__(self, config: AppConfig):
        """Initialize the GUI application."""
        self.config = config

        # Create main window FIRST (required for StringVar)
        self.root = tk.Tk()
        self.root.title("PeakPicker - TOF-SIMS Spectrum Analyzer")
        self.root.geometry(f"{config.window_width}x{config.window_height}")

        # Data
        self.spectrum: Optional[Spectrum] = None
        self.original_spectrum: Optional[Spectrum] = None
        self.peaks: List[Peak] = []
        self.calibration: Optional[CalibrationResult] = None

        # UI state (StringVar requires root window to exist)
        self.selected_peak_index = -1
        self.range_selection_points = []
        self.range_lines = []
        self.axis_mode = StringVar(value='tof')  # 'tof' or 'mz'
        self.analysis_mode = StringVar(value='peak_assign')  # 'peak_assign' or 'count_sum'
        self.summation_results_dict = OrderedDict()

        # Visualization
        self.window_size = config.default_zoom_window
        self.center_pos = None
        self.cursor_text = None

        # Setup matplotlib
        self.fig, self.ax = plt.subplots(figsize=(10, 5))
        self.ax.grid(True, linestyle=':', alpha=0.6)

        # Event listener IDs
        self.click_cid = None
        self.motion_cid = None

        # Build GUI
        self._setup_gui()

        # Update button states
        self._update_button_states()

        logger.info("GUI initialized")

    def _setup_gui(self):
        """Create and layout all GUI widgets."""
        # Top frame - File operations
        top_frame = Frame(self.root)
        top_frame.grid(row=0, column=0, sticky="ew", padx=5, pady=5)

        Button(top_frame, text="ファイルを開く", width=15, command=self.load_file).pack(side=LEFT, padx=2)
        Button(top_frame, text="結果をエクスポート", width=15, command=self.export_results).pack(side=LEFT, padx=2)
        Button(top_frame, text="終了", width=10, command=self.root.quit).pack(side=RIGHT, padx=2)

        # Graph frame
        graph_frame = Frame(self.root, bd=1, relief="sunken")
        graph_frame.grid(row=1, column=0, sticky="nsew", padx=5)
        self.canvas = FigureCanvasTkAgg(self.fig, master=graph_frame)
        self.canvas.get_tk_widget().pack(fill=BOTH, expand=True)

        # Control frame row 0 - View controls
        ctrl_frame_0 = Frame(self.root)
        ctrl_frame_0.grid(row=2, column=0, sticky="ew", padx=5, pady=(5, 0))

        self.zoom_in_btn = Button(ctrl_frame_0, text="ズームイン (+)", width=12, command=self.zoom_in)
        self.zoom_in_btn.pack(side=LEFT, padx=2)

        self.zoom_out_btn = Button(ctrl_frame_0, text="ズームアウト (-)", width=12, command=self.zoom_out)
        self.zoom_out_btn.pack(side=LEFT, padx=2)

        self.full_view_btn = Button(ctrl_frame_0, text="全体表示", width=12, command=self.full_view)
        self.full_view_btn.pack(side=LEFT, padx=2)

        # Axis mode selection
        Label(ctrl_frame_0, text="X軸:").pack(side=LEFT, padx=(20, 2))
        self.tof_axis_rb = Radiobutton(ctrl_frame_0, text="TOF", variable=self.axis_mode, value='tof',
                                       command=self.on_axis_mode_change)
        self.tof_axis_rb.pack(side=LEFT, padx=2)
        self.mz_axis_rb = Radiobutton(ctrl_frame_0, text="m/z", variable=self.axis_mode, value='mz',
                                      command=self.on_axis_mode_change)
        self.mz_axis_rb.pack(side=LEFT, padx=2)

        # Baseline subtraction
        Label(ctrl_frame_0, text="BG減算:").pack(side=LEFT, padx=(20, 2))
        self.baseline_entry = Entry(ctrl_frame_0, width=8)
        self.baseline_entry.pack(side=LEFT, padx=2)
        self.baseline_btn = Button(ctrl_frame_0, text="実行", width=8, command=self.subtract_baseline)
        self.baseline_btn.pack(side=LEFT, padx=2)

        # Control frame row 1 - Analysis controls
        ctrl_frame_1 = Frame(self.root)
        ctrl_frame_1.grid(row=3, column=0, sticky="ew", padx=5, pady=2)

        self.calibrate_btn = Button(ctrl_frame_1, text="m/z キャリブレーション", width=18,
                                     command=self.calibrate_mass)
        self.calibrate_btn.pack(side=LEFT, padx=2)

        self.fit_single_btn = Button(ctrl_frame_1, text="選択範囲を自動フィット", width=18,
                                      command=self.fit_selected_range)
        self.fit_single_btn.pack(side=LEFT, padx=2)

        self.fit_multi_btn = Button(ctrl_frame_1, text="範囲内ピーク自動検出＋フィット", width=22,
                                     command=self.auto_detect_and_fit)
        self.fit_multi_btn.pack(side=LEFT, padx=2)

        self.delete_peak_btn = Button(ctrl_frame_1, text="選択ピーク削除", width=12,
                                       command=self.delete_selected_peak)
        self.delete_peak_btn.pack(side=RIGHT, padx=2)

        # Control frame row 2 - Mode selection
        ctrl_frame_2 = Frame(self.root)
        ctrl_frame_2.grid(row=4, column=0, sticky="ew", padx=5, pady=2)

        Label(ctrl_frame_2, text="解析モード:").pack(side=LEFT, padx=2)
        Radiobutton(ctrl_frame_2, text="ピーク同定", variable=self.analysis_mode,
                   value='peak_assign', command=self.on_mode_change).pack(side=LEFT, padx=2)
        Radiobutton(ctrl_frame_2, text="積算", variable=self.analysis_mode,
                   value='count_sum', command=self.on_mode_change).pack(side=LEFT, padx=2)

        # Peak table frame
        table_frame = Frame(self.root)
        table_frame.grid(row=5, column=0, sticky="nsew", padx=5, pady=5)

        # Create Treeview for peak display
        columns = ('ID', 'TOF', 'm/z', 'Height', 'FWHM', 'Area(Fit)', 'Area(Int)')
        self.peak_tree = ttk.Treeview(table_frame, columns=columns, show='headings', height=8)

        for col in columns:
            self.peak_tree.heading(col, text=col)
            width = 60 if col == 'ID' else 100
            self.peak_tree.column(col, width=width, anchor='center')

        self.peak_tree.pack(side=LEFT, fill=BOTH, expand=True)

        # Scrollbar for tree
        tree_scroll = ttk.Scrollbar(table_frame, orient="vertical", command=self.peak_tree.yview)
        tree_scroll.pack(side=RIGHT, fill=Y)
        self.peak_tree.configure(yscrollcommand=tree_scroll.set)

        # Bind selection event
        self.peak_tree.bind('<<TreeviewSelect>>', self.on_peak_table_select)

        # Info text frame
        info_frame = Frame(self.root)
        info_frame.grid(row=6, column=0, sticky="nsew", padx=5, pady=5)

        self.info_text = Text(info_frame, height=6, width=60)
        self.info_text.pack(fill=BOTH, expand=True)

        # Scrollbar frame (horizontal slider for navigation)
        scroll_frame = Frame(self.root)
        scroll_frame.grid(row=7, column=0, sticky="ew", padx=5, pady=(0, 5))

        self.position_slider = Scale(scroll_frame, from_=0, to=100, orient=HORIZONTAL,
                                     command=self.on_slider_move, length=400)
        self.position_slider.pack(fill=X, expand=True)

        # Configure grid weights
        self.root.grid_rowconfigure(1, weight=4)  # Graph
        self.root.grid_rowconfigure(5, weight=2)  # Table
        self.root.grid_rowconfigure(6, weight=1)  # Info
        self.root.grid_columnconfigure(0, weight=1)

    # ========================================================================
    # File Operations
    # ========================================================================

    def load_file(self):
        """Load spectrum data from file."""
        file_path = filedialog.askopenfilename(
            title="スペクトルファイルを選択",
            initialdir=self.config.last_directory,
            filetypes=[
                ("MPA files", "*.mpa"),
                ("CSV files", "*.csv"),
                ("Text files", "*.txt"),
                ("All files", "*.*")
            ]
        )

        if not file_path:
            return

        try:
            # Update last directory
            self.config.last_directory = os.path.dirname(file_path)

            # Reset data
            self._reset_data()

            # Load spectrum
            self.spectrum = read_spectrum_file(file_path)
            self.original_spectrum = self.spectrum.copy()

            logger.info(f"Loaded spectrum: {file_path}")
            logger.info(f"Data points: {len(self.spectrum.tof)}")

            # Update UI
            self.root.title(f"PeakPicker - {os.path.basename(file_path)}")
            self.center_pos = self.spectrum.tof[len(self.spectrum.tof) // 2]

            # Setup slider
            self.position_slider.config(to=len(self.spectrum.tof) - 1)

            # Connect events
            if self.click_cid:
                self.canvas.mpl_disconnect(self.click_cid)
            self.click_cid = self.canvas.mpl_connect('button_press_event', self.on_plot_click)

            if self.motion_cid:
                self.canvas.mpl_disconnect(self.motion_cid)
            self.motion_cid = self.canvas.mpl_connect('motion_notify_event', self.on_plot_motion)

            # Display
            self.full_view()
            self._update_button_states()
            self._update_info_text()

            messagebox.showinfo("ファイル読み込み", "データを正常に読み込みました。")

        except FileReadError as e:
            messagebox.showerror("読み込みエラー", str(e))
            logger.error(f"File read error: {e}")
        except Exception as e:
            messagebox.showerror("エラー", f"ファイルの読み込み中にエラーが発生しました:\n{e}")
            logger.error(f"Error loading file: {e}")
            traceback.print_exc()

    def export_results(self):
        """Export analysis results to CSV."""
        if not self.peaks and not self.summation_results_dict:
            messagebox.showinfo("エクスポート", "エクスポートするデータがありません。")
            return

        base_name = "analysis_result"
        if self.spectrum and 'filename' in self.spectrum.metadata:
            base_name = os.path.splitext(self.spectrum.metadata['filename'])[0]

        # Export peaks
        if self.peaks:
            try:
                file_path = filedialog.asksaveasfilename(
                    title="ピークリストを保存",
                    initialfile=f"{base_name}_peaks.csv",
                    defaultextension=".csv",
                    filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
                )

                if file_path:
                    save_peaks_to_csv(self.peaks, file_path, include_fit_results=True)
                    messagebox.showinfo("エクスポート完了", f"ピークリストを保存しました:\n{os.path.basename(file_path)}")

            except Exception as e:
                messagebox.showerror("エクスポートエラー", f"ピークリストの保存に失敗しました:\n{e}")
                logger.error(f"Export error: {e}")

        # Export summation results if in count_sum mode
        if self.summation_results_dict:
            try:
                file_path = filedialog.asksaveasfilename(
                    title="積算結果を保存",
                    initialfile=f"{base_name}_counts.csv",
                    defaultextension=".csv",
                    filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
                )

                if file_path:
                    data = []
                    for mz_key, result in self.summation_results_dict.items():
                        data.append({
                            'MZ': mz_key,
                            'Total_Counts': result['Total_Counts'],
                            'Range_Start': result['Range_Start'],
                            'Range_End': result['Range_End']
                        })

                    df = pd.DataFrame(data)
                    df.to_csv(file_path, index=False, encoding='utf-8-sig')
                    messagebox.showinfo("エクスポート完了", f"積算結果を保存しました:\n{os.path.basename(file_path)}")

            except Exception as e:
                messagebox.showerror("エクスポートエラー", f"積算結果の保存に失敗しました:\n{e}")
                logger.error(f"Export error: {e}")

    # ========================================================================
    # UI Update Methods
    # ========================================================================

    def _reset_data(self):
        """Reset all data and UI state."""
        logger.info("Resetting application state")

        # Disconnect event listeners
        if self.click_cid:
            try:
                self.canvas.mpl_disconnect(self.click_cid)
            except:
                pass
            self.click_cid = None

        if self.motion_cid:
            try:
                self.canvas.mpl_disconnect(self.motion_cid)
            except:
                pass
            self.motion_cid = None

        # Clear data
        self.spectrum = None
        self.original_spectrum = None
        self.peaks = []
        self.calibration = None
        self.summation_results_dict = OrderedDict()

        # Reset UI state
        self.selected_peak_index = -1
        self.range_selection_points = []
        self.range_lines = []
        self.center_pos = None
        self.cursor_text = None

        # Clear plot
        self.ax.cla()
        self.ax.grid(True, linestyle=':', alpha=0.6)
        self.canvas.draw_idle()

        # Clear table
        for item in self.peak_tree.get_children():
            self.peak_tree.delete(item)

        # Clear info text
        self.info_text.delete(1.0, END)

        # Reset slider
        self.position_slider.config(to=100)

        # Reset title
        self.root.title("PeakPicker - TOF-SIMS Spectrum Analyzer")

    def _update_button_states(self):
        """Update button enabled/disabled states based on current state."""
        has_data = self.spectrum is not None
        is_calibrated = self.calibration is not None
        has_peaks = len(self.peaks) > 0
        has_selection = self.selected_peak_index >= 0

        # File operations - always enabled
        # (kept enabled)

        # View controls
        state_data = 'normal' if has_data else 'disabled'
        self.zoom_in_btn.config(state=state_data)
        self.zoom_out_btn.config(state=state_data)
        self.full_view_btn.config(state=state_data)
        self.baseline_btn.config(state=state_data)

        # Axis mode - m/z only if calibrated
        self.tof_axis_rb.config(state=state_data)
        self.mz_axis_rb.config(state='normal' if (has_data and is_calibrated) else 'disabled')

        # Analysis controls
        self.calibrate_btn.config(state='normal' if (has_data and has_peaks) else 'disabled')
        self.fit_single_btn.config(state=state_data)
        self.fit_multi_btn.config(state=state_data)
        self.delete_peak_btn.config(state='normal' if has_selection else 'disabled')

    def _update_peak_table(self):
        """Update the peak table display."""
        # Clear existing items
        for item in self.peak_tree.get_children():
            self.peak_tree.delete(item)

        # Add peaks
        for i, peak in enumerate(self.peaks):
            peak_id = i + 1

            mz_str = f"{int(round(peak.center_mz))}" if peak.center_mz else "N/A"
            fwhm_str = f"{peak.fwhm:.2f}" if peak.fwhm else "N/A"
            area_fit_str = f"{peak.area_fit:.1f}" if peak.area_fit else "N/A"
            area_int_str = f"{peak.area_integrated:.1f}" if peak.area_integrated else "N/A"

            values = (
                peak_id,
                f"{peak.center_tof:.2f}",
                mz_str,
                f"{peak.height:.1f}",
                fwhm_str,
                area_fit_str,
                area_int_str
            )

            # Insert item
            item_id = self.peak_tree.insert('', 'end', values=values)

            # Highlight selected peak
            if i == self.selected_peak_index:
                self.peak_tree.selection_set(item_id)
                self.peak_tree.see(item_id)

    def _update_info_text(self):
        """Update the info text widget."""
        self.info_text.delete(1.0, END)

        # Show calibration status
        if self.calibration:
            self.info_text.insert(END, f"キャリブレーション: A={self.calibration.A:.4f}, "
                                      f"B={self.calibration.B:.4f}, R²={self.calibration.r_squared:.4f}\n")
        else:
            self.info_text.insert(END, "キャリブレーション: 未実施\n")

        self.info_text.insert(END, "=" * 60 + "\n")

        # Show mode-specific info
        mode = self.analysis_mode.get()

        if mode == 'peak_assign':
            self.info_text.insert(END, "モード: ピーク同定\n")
            if self.calibration:
                self.info_text.insert(END, "操作: プロット上で範囲を選択（2点クリック）→ 自動フィットボタンを押す\n")
            else:
                self.info_text.insert(END, "操作: プロット上で範囲を選択（2点クリック）→ 自動フィットボタンを押す → m/z を入力\n")

            self.info_text.insert(END, f"\n識別済みピーク数: {len(self.peaks)}\n")

            if self.peaks:
                self.info_text.insert(END, "\nピーク一覧は上のテーブルを参照してください。\n")

        elif mode == 'count_sum':
            self.info_text.insert(END, "モード: 積算\n")
            self.info_text.insert(END, "操作: プロット上で範囲を選択（2点クリック）すると自動的に積算されます\n")

            if self.summation_results_dict:
                self.info_text.insert(END, f"\n積算済み m/z 数: {len(self.summation_results_dict)}\n")
                self.info_text.insert(END, "\n--- 積算結果 ---\n")

                for mz_key, result in self.summation_results_dict.items():
                    mz_disp = f"{mz_key}" if mz_key != -1 else "未較正"
                    self.info_text.insert(END, f"m/z {mz_disp}: 合計={result['Total_Counts']:.1f}, "
                                              f"範囲={result['Range_Start']:.1f}-{result['Range_End']:.1f}\n")

    def run(self):
        """Start the GUI main loop."""
        logger.info("Starting GUI")
        self.root.mainloop()
        logger.info("GUI closed")
