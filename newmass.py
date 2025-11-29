# -*- coding: utf-8 -*-
import os
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from scipy.optimize import curve_fit, OptimizeWarning # Import OptimizeWarning
import tkinter as tk
from tkinter import (
    filedialog, simpledialog, Text, END, Frame, Button, Entry, Scale, Label, # Scale をインポート
    LEFT, RIGHT, BOTH, TOP, X, Y, NSEW, EW, W, HORIZONTAL, VERTICAL, BOTTOM, StringVar, Radiobutton
)
from tkinter import messagebox
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import matplotlib.font_manager as fm
import matplotlib as mpl
import traceback
import warnings # Import warnings module
from collections import OrderedDict

class PeakPicker:
    """
    GUI Tool for analyzing TOF spectral data: peak identification,
    mass calibration, and ion count integration.
    Switch between Peak Identification and Integrate Counts modes.
    Calculates integer m/z automatically after mass calibration.
    Accumulates counts for the same integer m/z in integration mode.
    Identifies only the latest peak for a given integer m/z.
    Cursor info display position adjusted. Labels use "Count".
    """
    def __init__(self):
        """ Initializes the application state and GUI """
        self.tof = None
        self.intensity = None # Internal variable name (holds Count data)
        self.original_intensity = None
        self.peak_data = [] # List storing identified peak dictionaries
        self.summation_results_dict = OrderedDict() # Holds integrated results keyed by integer m/z
        self.selected_peak_index = -1
        self.selected_line_blinking = False
        self.blink_timer = None
        self.cursor_text = None
        self.fit_done = False
        self.popt = None
        self.window_size = 5000 # Initial zoom window size
        self.center_tof = None
        self.fig, self.ax = plt.subplots(figsize=(10, 5))
        self.root = tk.Tk()
        self.root.title("TOF Spectrum Analyzer")
        self.configure_fonts()

        # --- Mode Management ---
        self.current_mode = StringVar(value='peak_assign')
        self.current_mode.trace_add('write', self.on_mode_change)

        # --- Range Selection ---
        self.range_selection_points = []
        self.range_lines = []

        # --- File Path ---
        self.file_path = None

        # --- Event Listener IDs ---
        self.click_cid = None
        self.motion_cid = None

        # --- GUI Widget Setup ---
        self.setup_gui_older_layout()

        self.ax.grid(True, linestyle=':', alpha=0.6)

    def configure_fonts(self):
        """ Configures matplotlib font settings (optional). """
        print("Font configuration setup.")
        try:
             mpl.rcParams['font.family'] = 'sans-serif'
             print("Using default sans-serif font.")
        except Exception as e:
             print(f"Could not set default font: {e}")


    # --- GUI Setup (Older Layout Structure) ---
    def setup_gui_older_layout(self):
        """ Creates and lays out widgets based on the older code structure. """

        # --- Frames ---
        top_frame = Frame(self.root)
        graph_frame = Frame(self.root, bd=1, relief="sunken")
        ops_frame_row0 = Frame(self.root)
        ops_frame_row1 = Frame(self.root)
        ops_frame_row2 = Frame(self.root)
        text_frame = Frame(self.root)
        scrollbar_frame = Frame(self.root)

        # --- Grid Frames ---
        top_frame.grid(row=0, column=0, sticky="ew", padx=5, pady=5)
        graph_frame.grid(row=1, column=0, sticky="nsew", padx=5)
        ops_frame_row0.grid(row=2, column=0, sticky="ew", padx=5, pady=(5,0))
        ops_frame_row1.grid(row=3, column=0, sticky="ew", padx=5)
        ops_frame_row2.grid(row=4, column=0, sticky="ew", padx=5)
        text_frame.grid(row=5, column=0, sticky="nsew", padx=5, pady=5)
        scrollbar_frame.grid(row=6, column=0, sticky="ew", padx=5, pady=(0,5))

        self.root.grid_rowconfigure(1, weight=4) # Graph area weight
        self.root.grid_rowconfigure(5, weight=1) # Text area weight
        self.root.grid_columnconfigure(0, weight=1)

        # --- Create Widgets ---

        # Top frame
        self.select_file_button = tk.Button(top_frame, text="Select File", width=15, command=self.select_file)
        self.save_results_button = tk.Button(top_frame, text="Export Results", width=15, command=self.save_results)
        self.quit_button = tk.Button(top_frame, text="Quit", width=10, command=self.root.quit)

        # Graph frame
        self.canvas = FigureCanvasTkAgg(self.fig, master=graph_frame)

        # Ops frame row 0
        self.zoom_in_button = tk.Button(ops_frame_row0, text="Zoom In (+)", width=12, command=self.zoom_in)
        self.zoom_out_button = tk.Button(ops_frame_row0, text="Zoom Out (-)", width=12, command=self.zoom_out)
        self.subtract_entry = tk.Entry(ops_frame_row0, width=10)
        self.subtract_button = tk.Button(ops_frame_row0, text="Subtract BG", width=12, command=self.subtract_count)
        self.full_view_button = tk.Button(ops_frame_row0, text="Full Spectrum", width=12, command=self.full_view)

        # Ops frame row 1
        self.fit_button = tk.Button(ops_frame_row1, text="Calibrate m/z", width=15, command=self.fit_and_calculate)
        self.select_button = tk.Button(ops_frame_row1, text="Select Peak Mode", width=15, command=self.select_peak_visually)
        self.delete_button = tk.Button(ops_frame_row1, text="Delete Selected Peak", width=18, command=self.delete_selected_peak)

        # Ops frame row 2
        self.mode_label = tk.Label(ops_frame_row2, text="Analysis Mode:")
        self.peak_assign_rb = Radiobutton(ops_frame_row2, text="Peak Identification", variable=self.current_mode, value='peak_assign')
        self.count_sum_rb = Radiobutton(ops_frame_row2, text="Integrate Counts", variable=self.current_mode, value='count_sum')

        # Text frame
        self.text_widget = Text(text_frame, height=8, width=60)

        # Scrollbar frame
        self.scrollbar = tk.Scale(scrollbar_frame, from_=0, to=100, orient=tk.HORIZONTAL, command=self.scroll, length=400)

        # --- Pack Widgets ---

        # Top frame
        self.select_file_button.pack(side=tk.LEFT, padx=(0, 5))
        self.save_results_button.pack(side=tk.LEFT, padx=(0, 5))
        self.quit_button.pack(side=tk.RIGHT)

        # Graph frame
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

        # Ops frame row 0
        self.zoom_in_button.pack(side=tk.LEFT, padx=(0, 5))
        self.zoom_out_button.pack(side=tk.LEFT, padx=(0, 5))
        self.subtract_entry.pack(side=tk.LEFT, padx=(10, 2))
        self.subtract_button.pack(side=tk.LEFT, padx=(0, 5))
        self.full_view_button.pack(side=tk.RIGHT, padx=(5, 0))

        # Ops frame row 1
        self.fit_button.pack(side=tk.LEFT, padx=(0, 5))
        self.delete_button.pack(side=tk.RIGHT, padx=(0,0))
        self.select_button.pack(side=tk.RIGHT, padx=(0, 5))

        # Ops frame row 2
        self.mode_label.pack(side=tk.LEFT, padx=(0, 5))
        self.peak_assign_rb.pack(side=tk.LEFT, padx=(0, 10))
        self.count_sum_rb.pack(side=tk.LEFT)

        # Text frame
        self.text_widget.pack(fill=tk.BOTH, expand=True)

        # Scrollbar frame
        self.scrollbar.pack(fill=tk.X, expand=True)


    def select_file(self):
        """ Opens a file dialog, loads and processes the spectrum data. """
        file_path = filedialog.askopenfilename(title="Select Spectrum Data File")
        if file_path:
            self.file_path = file_path
            self.reset_data()
            try:
                self.load_data(file_path)
                if self.tof is not None and not self.tof.empty:
                    self.center_tof = self.tof.iloc[len(self.tof) // 2] if len(self.tof) > 0 else 0
                    self.full_view()
                    # Connect events
                    if self.click_cid: self.canvas.mpl_disconnect(self.click_cid)
                    self.click_cid = self.canvas.mpl_connect('button_press_event', self.on_click)
                    if self.motion_cid: self.canvas.mpl_disconnect(self.motion_cid)
                    self.motion_cid = self.canvas.mpl_connect('motion_notify_event', self.on_motion)
                    self.root.title(f"Spectrum Analysis - {os.path.basename(file_path)}")
                    self.on_mode_change()
                else:
                    messagebox.showerror("Load Error", "Failed to load spectrum data.")
                    self.root.title("TOF Spectrum Analyzer")
            except Exception as e:
                messagebox.showerror("Processing Error", f"Error loading or processing data:\n{e}")
                traceback.print_exc()
                self.root.title("TOF Spectrum Analyzer")

    def reset_data(self):
        """ Resets all data and plot elements to the initial state. """
        # Disconnect listeners
        if self.click_cid:
            try: self.canvas.mpl_disconnect(self.click_cid)
            except TypeError: pass
            self.click_cid = None
        if self.motion_cid:
            try: self.canvas.mpl_disconnect(self.motion_cid)
            except TypeError: pass
            self.motion_cid = None
        if self.blink_timer:
            self.root.after_cancel(self.blink_timer)
            self.blink_timer = None

        # Clear data
        self.tof = None
        self.intensity = None
        self.original_intensity = None
        self.summation_results_dict = OrderedDict()
        # Clear peaks and their graphics before resetting list
        self._clear_peak_graphics()
        self.peak_data = []
        self.selected_peak_index = -1
        self.selected_line_blinking = False
        self.fit_done = False
        self.popt = None
        self.window_size = 5000
        self.center_tof = None
        self.file_path = None

        # Clear range lines
        self.clear_range_lines()
        self.range_selection_points = []

        # Clear cursor text
        if self.cursor_text and self.cursor_text in self.ax.texts:
            try: self.cursor_text.remove()
            except ValueError: pass
            self.cursor_text = None

        # Clear plot, text, scrollbar, title
        self.ax.cla()
        self.ax.grid(True, linestyle=':', alpha=0.6)
        self.text_widget.delete(1.0, END)
        self.scrollbar.config(to=100)
        self.root.title("TOF Spectrum Analyzer")
        print("Application state reset.")

    # Helper to remove graphics associated with peaks
    def _clear_peak_graphics(self):
         for peak_info in self.peak_data:
            line, text = peak_info.get('line'), peak_info.get('text')
            if line and line in self.ax.lines:
                try: line.remove()
                except ValueError: pass
            if text and text in self.ax.texts:
                try: text.remove()
                except ValueError: pass
            # Clear references in dictionary to avoid dangling references
            peak_info['line'], peak_info['text'] = None, None

    def load_data(self, file_path):
        """ Loads TOF and Count data, configures scrollbar. """
        print(f"Attempting to load data from: {file_path}")
        data = None
        names_to_use = ['TOF', 'Count']
        try:
            file_ext = os.path.splitext(file_path)[1].lower()
            if file_ext == '.mpa':
                data = self.read_mpa_file(file_path, names=names_to_use)
            elif file_ext in ['.csv', '.txt']:
                encodings_to_try = ['utf-8', 'shift-jis', 'cp932', 'latin-1']
                separators_to_try = [',', r'\s+']
                read_success = False
                for enc in encodings_to_try:
                    for sep in separators_to_try:
                        try:
                            data = pd.read_csv(file_path, skiprows=0, sep=sep, names=names_to_use, engine='python', on_bad_lines='warn', encoding=enc, comment='#')
                            if 'TOF' in data.columns and 'Count' in data.columns and \
                               pd.api.types.is_numeric_dtype(data['TOF']) and \
                               pd.api.types.is_numeric_dtype(data['Count']) and \
                               len(data)>10:
                                print(f"Read success: Separator='{sep}', Encoding='{enc}'")
                                read_success = True
                                if not pd.api.types.is_numeric_dtype(data.iloc[0]['TOF']) or not pd.api.types.is_numeric_dtype(data.iloc[0]['Count']):
                                    print("Header row detected, attempting reload with skiprows=1")
                                    data = pd.read_csv(file_path, skiprows=1, sep=sep, names=names_to_use, engine='python', on_bad_lines='warn', encoding=enc, comment='#')
                                    if not (pd.api.types.is_numeric_dtype(data['TOF']) and pd.api.types.is_numeric_dtype(data['Count'])):
                                        print("Reload with skiprows=1 failed numeric check.")
                                        data, read_success = None, False
                                break
                            else: data = None
                        except Exception: data = None
                    if read_success: break
                if not read_success:
                     print("Initial read attempts failed, trying fallback with skiprows=158...")
                     try:
                          data = pd.read_csv(file_path, skiprows=158, sep=r'\s+', names=names_to_use, engine='python', on_bad_lines='skip', encoding='utf-8')
                          if not (pd.api.types.is_numeric_dtype(data['TOF']) and pd.api.types.is_numeric_dtype(data['Count'])): data=None
                     except Exception: data=None
                     if data is None: raise ValueError("Could not determine appropriate file format/encoding.")
            else:
                messagebox.showwarning("Unsupported Format", f"Direct support for '{file_ext}' is not available. Attempting to read as generic CSV/TSV.")
                raise ValueError(f"File format '{file_ext}' not explicitly supported.")

            if data is None or data.empty: raise ValueError("Data is empty or loading failed.")
            if 'TOF' not in data.columns or 'Count' not in data.columns: raise ValueError("Required columns (TOF, Count) not found.")

            # --- Data Cleaning ---
            data['TOF'] = pd.to_numeric(data['TOF'], errors='coerce')
            data['Count'] = pd.to_numeric(data['Count'], errors='coerce')
            initial_rows = len(data)
            data.dropna(subset=['TOF', 'Count'], inplace=True)
            dropped_rows = initial_rows - len(data)
            if dropped_rows > 0: print(f"Removed {dropped_rows} rows with invalid data.")
            if data.empty: raise ValueError("No valid numeric data found after cleaning.")
            data = data.sort_values(by='TOF').reset_index(drop=True)

            self.tof = data['TOF']
            self.intensity = data['Count']
            self.original_intensity = self.intensity.copy()
            print(f"Data loaded successfully: {len(self.tof)} points.")

            # --- Configure Scrollbar ---
            if self.tof is not None and not self.tof.empty: self.scrollbar.config(to=len(self.tof)-1)
            else: self.scrollbar.config(to=100)

        except Exception as e:
            self.tof, self.intensity, self.original_intensity = None, None, None
            self.scrollbar.config(to=100)
            messagebox.showerror("Data Load Error", f"Failed to load or process data:\n{e}")
            traceback.print_exc()

    def read_mpa_file(self, file_path, names=['TOF', 'Count']):
        """ Reads data specifically from an MPA file format. """
        print(f"Reading MPA file: {file_path}")
        try:
            encodings_to_try = ['utf-8', 'shift-jis', 'cp932', 'latin-1']
            lines = None
            for enc in encodings_to_try:
                try:
                    with open(file_path, 'r', encoding=enc) as file: lines = file.readlines()
                    print(f"Read MPA success (Encoding: {enc})")
                    break
                except UnicodeDecodeError: print(f"Read MPA failed (Encoding: {enc})")
                except Exception as e: print(f"Error reading with encoding {enc}: {e}")
            if lines is None: raise ValueError("Could not read MPA file with tried encodings.")

            data_start_line = 158
            print(f"Info: Assuming MPA data starts around line {data_start_line+1}.")
            data_lines = lines[data_start_line:]
            if not data_lines: raise ValueError(f"No data found after line {data_start_line}.")

            data = [line.strip().split() for line in data_lines if len(line.strip().split()) == 2]
            if not data: raise ValueError("No valid data pairs (TOF Count) found.")

            df = pd.DataFrame(data, columns=names)
            df[names[0]] = pd.to_numeric(df[names[0]], errors='coerce')
            df[names[1]] = pd.to_numeric(df[names[1]], errors='coerce')
            df.dropna(inplace=True)
            if df.empty: raise ValueError("No valid numeric data in MPA file.")

            print(f"MPA data read successfully: {len(df)} points.")
            return df
        except Exception as e:
            print(f"Error reading MPA file {file_path}: {e}")
            raise

    def save_results(self):
        """ Saves identified peaks and/or integrated counts to separate CSV files. """
        has_peaks = bool(self.peak_data)
        has_sums = bool(self.summation_results_dict)
        if not has_peaks and not has_sums:
            messagebox.showinfo("Export Results", "No analysis results available to save.")
            return

        base_filename = "analysis_result" # Default if no file loaded
        if self.file_path:
            # Default name: originalfilename_result
            base_filename = os.path.splitext(os.path.basename(self.file_path))[0] + "_result"
        peak_file_saved_path = None
        sum_file_saved_path = None

        # Save Identified Peaks
        if has_peaks:
            try:
                # Append _peaks to the base name for the default
                initial_peak_file = f"{base_filename}_peaks.csv"
                file_path_peaks = filedialog.asksaveasfilename(title="Save Identified Peak List", initialfile=initial_peak_file, defaultextension=".csv", filetypes=[("CSV", "*.csv"),("All Files", "*.*")])
                if file_path_peaks:
                    save_data = []
                    for p in self.peak_data:
                        mz_val = p.get('mz', np.nan)
                        mz_int = int(round(mz_val)) if pd.notna(mz_val) else np.nan
                        save_data.append({
                            'Assigned_TOF': p.get('tof', np.nan),
                            'Assigned_MZ': mz_int,
                            'Range_Start_TOF': p.get('range_start', np.nan),
                            'Range_End_TOF': p.get('range_end', np.nan),
                            'PeakTop_Count': p.get('max_intensity', np.nan)
                        })
                    peak_cols = ['Assigned_TOF','Assigned_MZ','Range_Start_TOF','Range_End_TOF','PeakTop_Count']
                    df = pd.DataFrame(save_data).reindex(columns=peak_cols)
                    if 'Assigned_MZ' in df.columns: df['Assigned_MZ'] = df['Assigned_MZ'].astype('Int64')
                    df.to_csv(file_path_peaks, index=False, float_format='%.4f', encoding='utf-8-sig')
                    print(f"Identified peak list saved to: {file_path_peaks}")
                    peak_file_saved_path = file_path_peaks
            except Exception as e:
                messagebox.showerror("Peak Export Error", f"Error saving peak list:\n{e}")
                traceback.print_exc()
        else:
            print("No identified peaks to export.")

        # Save Integrated Counts
        if has_sums:
            try:
                # Append _counts to the base name for the default
                initial_sum_file = f"{base_filename}_counts.csv"
                file_path_sums = filedialog.asksaveasfilename(title="Save Integrated Count List", initialfile=initial_sum_file, defaultextension=".csv", filetypes=[("CSV", "*.csv"),("All Files", "*.*")])
                if file_path_sums:
                    save_data_sums = []
                    for mz_key, data in self.summation_results_dict.items():
                         row = {'Calculated_MZ': mz_key}
                         row['Total_Integrated_Counts'] = data.get('Total_Counts')
                         row['Last_Range_Start_TOF'] = data.get('Range_Start')
                         row['Last_Range_End_TOF'] = data.get('Range_End')
                         row['Last_PeakTop_TOF'] = data.get('Max_Count_TOF')
                         row['Last_PeakTop_Count'] = data.get('Max_Count')
                         save_data_sums.append(row)

                    df = pd.DataFrame(save_data_sums)
                    cols = ['Calculated_MZ', 'Total_Integrated_Counts', 'Last_Range_Start_TOF', 'Last_Range_End_TOF', 'Last_PeakTop_TOF', 'Last_PeakTop_Count']
                    for c in cols:
                        if c not in df.columns: df[c] = np.nan
                    df = df.reindex(columns=cols)

                    if 'Calculated_MZ' in df.columns: df['Calculated_MZ'] = df['Calculated_MZ'].astype('Int64')

                    df.to_csv(file_path_sums, index=False, float_format='%.4f', encoding='utf-8-sig')
                    print(f"Integrated count list saved to: {file_path_sums}")
                    sum_file_saved_path = file_path_sums
            except Exception as e:
                messagebox.showerror("Integration Export Error", f"Error saving integrated counts:\n{e}")
                traceback.print_exc()
        else:
            print("No integrated counts to export.")

        # Consolidated save message
        saved_files = []
        if peak_file_saved_path: saved_files.append(f"Identified Peaks: {os.path.basename(peak_file_saved_path)}")
        if sum_file_saved_path: saved_files.append(f"Integrated Counts: {os.path.basename(sum_file_saved_path)}")

        if saved_files:
             messagebox.showinfo("Export Complete", "Results saved to:\n" + "\n".join(saved_files))


    def subtract_count(self):
        """ Subtracts a constant value from the count data (Baseline Correction). """
        if self.intensity is None or self.original_intensity is None:
            messagebox.showwarning("Baseline Correction", "Load spectrum data first.")
            return
        try:
            val_str = self.subtract_entry.get()
            if not val_str:
                if not self.intensity.equals(self.original_intensity):
                    self.intensity = self.original_intensity.copy()
                    print("Restored original count data.")
                    self.update_plot()
                    self.subtract_entry.delete(0, END)
                else:
                    print("Data is already original. No subtraction value entered.")
            else:
                val = float(val_str)
                self.intensity = (self.original_intensity - val).clip(lower=0)
                print(f"Baseline Correction: Subtracted {val} from all points.")
                self.update_plot()
        except ValueError:
            messagebox.showerror("Input Error", "Please enter a valid number for subtraction.")


    def on_mode_change(self, *args):
        """ Called when the analysis mode radio button changes. """
        mode = self.current_mode.get()
        mode_map = {'peak_assign': 'Peak Identification', 'count_sum': 'Integrate Counts'}
        print(f"Analysis Mode changed to: {mode_map.get(mode, mode)}")
        self.clear_range_lines()
        self.range_selection_points = []
        self.update_text_widget()
        self.selected_peak_index = -1
        self.update_plot()


    def clear_range_lines(self):
        """ Removes the green range selection lines from the plot. """
        cleared = 0
        for i in range(len(self.range_lines)-1, -1, -1):
             line = self.range_lines.pop(i)
             if line and line in self.ax.lines:
                 try: line.remove(); cleared+=1
                 except ValueError: pass
        # Avoid redraw if nothing removed, handled by subsequent plot updates
        # if cleared > 0 and self.canvas: self.canvas.draw_idle()


    def on_click(self, event):
        """ Handles mouse clicks on the plot area for range selection. """
        if not (event.inaxes == self.ax and event.button == 1 and self.tof is not None):
            return
        tof = event.xdata
        if len(self.range_selection_points) == 0: self.clear_range_lines()
        self.range_selection_points.append(tof)
        try:
            line = self.ax.axvline(x=tof, color='lime', ls='-.', lw=1.0, label='_range')
            self.range_lines.append(line)
            self.canvas.draw_idle()
            print(f"Range point {len(self.range_selection_points)} @ TOF={tof:.2f}")
        except Exception as e: print(f"Error drawing range line: {e}")
        if len(self.range_selection_points) == 2:
            self.process_range_selection(*sorted(self.range_selection_points))
            # Keep lines visible for context until next click


    def process_range_selection(self, tof_start, tof_end):
        """ Processes the selected TOF range based on the current mode. """
        if self.tof is None: return
        mask = (self.tof >= tof_start) & (self.tof <= tof_end)
        if not mask.any():
            messagebox.showwarning("Range Error", "No data points in the selected range.")
            self.range_selection_points = []
            return
        intens = self.intensity[mask]
        if intens.empty:
            messagebox.showwarning("Range Error", "Count data is empty in the selected range.")
            self.range_selection_points = []
            return

        try:
            max_idx = intens.idxmax()
            peak_tof = self.tof.loc[max_idx]
            max_int = self.intensity.loc[max_idx]
        except ValueError:
            messagebox.showerror("Range Processing Error", "Cannot find maximum count value in range.")
            self.range_selection_points = []
            return

        print(f"Selected Range: {tof_start:.2f} - {tof_end:.2f}, Peak Top @ TOF={peak_tof:.2f} (Count={max_int:.1f})")
        mode = self.current_mode.get()

        if mode == 'peak_assign': # --- Peak Identification Mode ---
            mz_float, mz_int, success = None, None, False
            calibrated = self.fit_done and self.popt is not None and len(self.popt)==2

            if calibrated: # Auto-calculate M/Z
                A, B = self.popt
                calc_mz_float = np.nan
                if A != 0 and peak_tof > B:
                    try:
                        calc_mz_float = ((peak_tof - B) / A)**2
                        if calc_mz_float > 0:
                            mz_float, mz_int = calc_mz_float, int(round(calc_mz_float))
                            if mz_int <= 0: messagebox.showwarning("Calculation Warning", f"Calculated integer M/Z is not positive: {mz_int}")
                            else: print(f"Auto-calculated M/Z (integer): {mz_int} (from: {mz_float:.4f})"); success = True
                        else: messagebox.showwarning("Calculation Warning", f"Calculated M/Z is not positive: {calc_mz_float:.4f}")
                    except Exception as e: messagebox.showerror("Calculation Error", f"Error during M/Z auto-calculation: {e}")
                else: messagebox.showwarning("Calculation Warning", f"Cannot auto-calculate M/Z for TOF {peak_tof:.2f} (A=0 or TOF<=B)")
                if not success: print("Auto-assignment of M/Z failed.")
            else: # Manual M/Z Input
                mz_str = simpledialog.askstring("Manual M/Z Input", f"Peak Top @ TOF {peak_tof:.2f}\nEnter integer M/Z for identification:", parent=self.root)
                if mz_str is not None:
                    try:
                        mz_int_input = int(mz_str)
                        if mz_int_input <= 0: raise ValueError("M/Z must be a positive integer")
                        mz_int = mz_int_input
                        mz_float = float(mz_int) # Keep float representation if needed
                        success = True
                    except ValueError as e: messagebox.showerror("Invalid Input", f"Invalid integer M/Z: '{mz_str}'.\nError: {e}")
                else: print("Manual M/Z input cancelled.")

            if success and mz_int is not None:
                # <<< MODIFIED START: Check/Remove existing peak before adding new >>>
                existing_peak_index = -1
                for i, existing_peak in enumerate(self.peak_data):
                    if existing_peak.get('mz') == mz_int:
                        existing_peak_index = i
                        break

                removed_selection_flag = False # Track if current selection was removed
                if existing_peak_index != -1:
                    print(f"M/Z {mz_int} already identified. Updating peak information.")
                    old_peak_info = self.peak_data.pop(existing_peak_index)
                    # Remove old graphical elements
                    old_line, old_text = old_peak_info.get('line'), old_peak_info.get('text')
                    if old_line and old_line in self.ax.lines:
                        try: old_line.remove()
                        except ValueError: pass # Ignore if already gone
                    if old_text and old_text in self.ax.texts:
                        try: old_text.remove()
                        except ValueError: pass # Ignore if already gone

                    # Adjust selected index if it was affected by removal
                    if self.selected_peak_index == existing_peak_index:
                         self.selected_peak_index = -1 # Deselect if the removed one was selected
                         removed_selection_flag = True
                    elif self.selected_peak_index > existing_peak_index:
                         self.selected_peak_index -= 1 # Shift index back
                # <<< MODIFIED END: Check/Remove existing peak >>>

                # Add the new peak information
                try:
                    y_max = self.ax.get_ylim()[1]
                    txt_y = max_int * 1.05 if max_int * 1.05 < y_max * 0.98 else y_max * 0.95
                    # New/updated peak starts blue, unless it replaced the selection
                    clr = 'blue'
                    mz_disp = f"{mz_int}"
                    line = self.ax.axvline(x=peak_tof, color=clr, ls='--', lw=0.8, label='_peak_line')
                    txt = self.ax.text(peak_tof, txt_y, mz_disp, color=clr, ha='center', va='bottom', picker=5, label='_peak_text')
                    info = {'tof':peak_tof, 'mz':mz_int, 'line':line, 'text':txt, 'range_start':tof_start, 'range_end':tof_end, 'max_intensity':max_int}

                    self.peak_data.append(info) # Add the new/updated peak data
                    self.peak_data.sort(key=lambda x:x['tof']) # Keep sorted by TOF
                    # Find index of the newly added/updated peak
                    new_index = next((i for i, p in enumerate(self.peak_data) if p['tof'] == peak_tof and p['mz'] == mz_int), -1)

                    # Select the new/updated peak only if the previous selection wasn't the one removed
                    if not removed_selection_flag:
                         self.selected_peak_index = new_index
                         if new_index != -1: # Highlight immediately if selection occurred
                              if info.get('line'): info['line'].set_color('red')
                              if info.get('text'): info['text'].set_color('red')

                    print(f"Peak identified/updated: TOF={peak_tof:.2f}, M/Z={mz_int}")
                    # Full redraw needed to reflect changes correctly
                    self.update_plot()
                    self.update_text_widget()
                except Exception as e:
                    messagebox.showerror("Peak Add Error", f"Error adding/updating identified peak:\n{e}")
                    traceback.print_exc()

            # Reset range points after processing peak assignment
            self.range_selection_points = []


        elif mode == 'count_sum': # --- Integrate Counts Mode ---
            total_counts = np.sum(intens)
            calc_mz_float, calc_mz_int = np.nan, None
            calibrated = self.fit_done and self.popt is not None and len(self.popt)==2

            if calibrated:
                A, B = self.popt
                if A != 0 and peak_tof > B:
                    try:
                        calc_mz_float = ((peak_tof - B) / A)**2
                        if calc_mz_float > 0: calc_mz_int = int(round(calc_mz_float))
                        if calc_mz_int is not None and calc_mz_int <= 0: calc_mz_int = None
                    except Exception as e: print(f"M/Z calculation error during integration: {e}"); calc_mz_int = None
            else:
                 messagebox.showwarning("Calibration Missing", "Mass calibration not performed. Integrating counts under M/Z key 'Uncalibrated'.")
                 calc_mz_int = -1 # Key for uncalibrated

            current_result = {
                'Range_Start': tof_start, 'Range_End': tof_end,
                'Total_Counts': total_counts,
                'Max_Count_TOF': peak_tof, 'Max_Count': max_int
            }

            if calc_mz_int is not None:
                mz_key_disp = f"{calc_mz_int}" if calc_mz_int != -1 else "Uncalibrated"
                if calc_mz_int in self.summation_results_dict:
                    existing_entry = self.summation_results_dict[calc_mz_int]
                    existing_entry['Total_Counts'] += total_counts
                    # Update other fields to reflect the latest range used for this M/Z
                    existing_entry.update({k:v for k,v in current_result.items() if k != 'Total_Counts'})
                    print(f"Count integration update M/Z={mz_key_disp}: Added={total_counts:.1f}, New Total={existing_entry['Total_Counts']:.1f}")
                else:
                    self.summation_results_dict[calc_mz_int] = current_result
                    print(f"New count integration M/Z={mz_key_disp}: Total={total_counts:.1f}")

                self.update_text_widget(last_sum_mz_key=calc_mz_int)
            else:
                 messagebox.showerror("Integration Error", "Could not generate a valid M/Z key for integration.")
                 self.update_text_widget()
            self.range_selection_points = [] # Reset points


    def on_motion(self, event):
        """ Handles mouse motion over the plot area to display coordinates. """
        if not (event.inaxes == self.ax and self.tof is not None):
            if self.cursor_text and self.cursor_text in self.ax.texts:
                try: self.cursor_text.remove()
                except ValueError: pass
                self.cursor_text = None
                if self.canvas: self.canvas.draw_idle()
            return

        tof = event.xdata
        count_val = np.interp(tof, self.tof.values, self.intensity.values)

        txt = f"TOF: {tof:.2f}\nCount: {count_val:.1f}"

        if self.fit_done and self.popt is not None and len(self.popt) == 2:
            A, B = self.popt
            if A != 0 and tof > B:
                try:
                    mz_float = ((tof - B) / A)**2
                    mz_int = int(round(mz_float))
                    if mz_int > 0 : txt += f"\nm/z: {mz_int}"
                    else: txt += "\nm/z: N/A"
                except Exception: txt += "\nm/z: Error"
            else: txt += "\nm/z: N/A"

        # --- Adjust Text Position ---
        x_offset = (self.ax.get_xlim()[1] - self.ax.get_xlim()[0]) * 0.02 # 2% right
        y_offset = (self.ax.get_ylim()[1] - self.ax.get_ylim()[0]) * 0.02 # 2% down

        text_x = tof + x_offset
        text_y = count_val - y_offset

        if self.cursor_text and self.cursor_text in self.ax.texts:
            self.cursor_text.set_position((text_x, text_y))
            self.cursor_text.set_text(txt)
            self.cursor_text.set_va('top')
            self.cursor_text.set_ha('left')
        else:
            self.cursor_text = self.ax.text(text_x, text_y, txt, color='k',
                                           ha='left', va='top',
                                           bbox=dict(boxstyle='round,pad=0.3', fc='lightyellow', alpha=0.8))

        if self.canvas: self.canvas.draw_idle()


    def zoom_plot(self):
        """ Updates the plot view based on center_tof and window_size. """
        if self.tof is None or self.center_tof is None: return
        min_t = self.center_tof - self.window_size / 2
        max_t = self.center_tof + self.window_size / 2
        min_d, max_d = self.tof.min(), self.tof.max()
        min_t = max(min_t, min_d); max_t = min(max_t, max_d)
        if max_t <= min_t: max_t = min_t + 10

        mask = (self.tof >= min_t) & (self.tof <= max_t)
        tof_v, int_v = self.tof[mask], self.intensity[mask]
        current_xlim = self.ax.get_xlim() # Store current limits before clear
        current_ylim = self.ax.get_ylim()

        self.ax.cla() # Clear axes

        # Main data plot
        if not tof_v.empty:
            self.ax.plot(tof_v, int_v, label='Spectrum', color='navy', lw=1.0)
            # Set Y limits based on visible data, add padding
            y_min_data = 0 # Assuming counts start at 0
            y_max_data = int_v.max()
            y_range = y_max_data - y_min_data
            # Add padding, handle flat data case
            y_pad = y_range * 0.05 if y_range > 0 else 1.0
            self.ax.set_ylim(max(0, y_min_data - y_pad), y_max_data + y_pad)
        else:
            self.ax.plot([], [], label='Spectrum', color='navy', lw=1.0)
            self.ax.set_ylim(current_ylim) # Restore old Y limit if no data

        # Set X limits
        self.ax.set_xlim(min_t, max_t)
        y_min_view, y_max_view = self.ax.get_ylim()
        txt_y_def = y_max_view * 0.95 # Default text Y pos relative to current view

        # Redraw identified peaks - important to recreate graphics after cla()
        # First, clear any potentially lingering references in self.peak_data
        for info in self.peak_data:
             info['line'], info['text'] = None, None

        # Now, recreate graphics for peaks within the current view
        for i, info in enumerate(self.peak_data):
            t = info['tof']
            mz_int = info.get('mz', None)
            # Check if the peak's TOF is within the current X view
            if mz_int is not None and min_t <= t <= max_t:
                is_selected = (i == self.selected_peak_index)
                clr = 'red' if is_selected else 'blue'
                peak_count = info.get('max_intensity', np.interp(t, self.tof.values, self.intensity.values))
                # Position text relative to the *current* Y axis view
                txt_y = peak_count * 1.05 if peak_count * 1.05 < txt_y_def and peak_count >= y_min_view else txt_y_def
                mz_s = f"{mz_int}"
                # Create new graphical elements and store their references
                line = self.ax.axvline(x=t, color=clr, ls='--', lw=0.8, label='_peak_line')
                txt = self.ax.text(t, txt_y, mz_s, color=clr, ha='center', va='bottom', picker=5, label='_peak_text')
                info['line'] = line
                info['text'] = txt
            # else: line/text remain None if peak is out of view

        # Redraw range lines
        new_range_refs = []
        for line in self.range_lines:
             if line:
                 try:
                     t = line.get_xdata()[0]
                     if min_t <= t <= max_t:
                         r_line = self.ax.axvline(x=t, color='lime', ls='-.', lw=1.0, label='_range')
                         new_range_refs.append(r_line)
                 except (AttributeError, IndexError, TypeError): pass # Handle stale references
        self.range_lines = new_range_refs # Update list with active lines

        # Labels and Title
        self.ax.set_xlabel('Time of Flight (TOF)')
        self.ax.set_ylabel('Ion Count')
        self.ax.set_title(f'TOF Spectrum (Center TOF:{self.center_tof:.2f}, Width:{max_t-min_t:.2f})')

        # Legend
        handles, labels = self.ax.get_legend_handles_labels()
        h_f = [h for h, l in zip(handles, labels) if not l.startswith('_')]
        l_f = [l for l in labels if not l.startswith('_')]
        leg = self.ax.get_legend()
        if leg: leg.remove()
        if h_f: self.ax.legend(h_f, l_f, loc='upper right')

        self.ax.grid(True, ls=':', alpha=0.6)
        if self.fit_done: self.plot_fit_curve() # Replot fit points if calibration exists
        if self.canvas: self.canvas.draw_idle()


    def full_view(self):
        """ Displays the full range of the loaded TOF data. """
        if self.tof is None or self.tof.empty:
            messagebox.showwarning("Full Spectrum View", "No spectrum data loaded.")
            return
        min_d, max_d = self.tof.min(), self.tof.max()
        self.center_tof=(min_d+max_d)/2
        self.window_size = max_d - min_d
        if self.window_size <= 0: self.window_size = 100
        self.zoom_plot()
        self.ax.set_title('TOF Spectrum (Full Range)')
        if self.canvas: self.canvas.draw_idle()


    def update_text_widget(self, last_sum_result=None, last_sum_mz_key=None):
        """ Updates the text widget based on the current mode and data. """
        self.text_widget.delete(1.0, END)
        mode = self.current_mode.get()
        if self.tof is None:
            self.text_widget.insert(END, "Load spectrum data to begin analysis.\n")
            return

        calibrated = self.fit_done and self.popt is not None and len(self.popt)==2
        if calibrated:
            self.text_widget.insert(END, f"Mass Calibration Coefficients: A={self.popt[0]:.4f}, B={self.popt[1]:.4f}\n")
        else:
            self.text_widget.insert(END, "Mass calibration has not been performed.\n")
        self.text_widget.insert(END, "="*40+"\n")

        if mode == 'peak_assign':
            rb_text = "Peak ID (Auto m/z)" if calibrated else "Peak ID (Manual m/z)"
            mode_desc = f"Mode: {rb_text}\n"
            instr = "Click twice on plot for range (m/z auto-calculated).\n" if calibrated else "Click twice for range & enter m/z (Calibration needed first).\n"
            self.peak_assign_rb.config(text="Peak Identification")
            self.text_widget.insert(END, mode_desc)
            self.text_widget.insert(END, instr)
            self.text_widget.insert(END, "Select/Delete: Use 'Select Peak Mode' -> Click label.\n")
            self.text_widget.insert(END, "--- Identified Peak List ---\n")
            if not self.peak_data:
                self.text_widget.insert(END, "(No peaks identified yet)\n")
            else:
                self.peak_data.sort(key=lambda x:x['tof'])
                for i, p in enumerate(self.peak_data):
                    mark = "->" if i == self.selected_peak_index else "  "
                    mz_int = p.get('mz', None)
                    mz_s = f"{mz_int}" if mz_int is not None else "N/A"
                    p_str=f"{mark} TOF:{p.get('tof',0):.2f}, m/z:{mz_s}, PeakTop Count:{p.get('max_intensity',0):.1f} (R:{p.get('range_start',0):.1f}-{p.get('range_end',0):.1f})\n"
                    self.text_widget.insert(END, p_str)

        elif mode == 'count_sum':
                self.count_sum_rb.config(text="Integrate Counts")
                self.text_widget.insert(END, "Mode: Integrate Ion Counts\n")
                self.text_widget.insert(END, "Click twice on plot for range to integrate (sums by integer m/z).\n")
                self.text_widget.insert(END, "--- Integrated Count List (by m/z) ---\n")

                if not self.summation_results_dict:
                     self.text_widget.insert(END, "(No counts integrated yet)\n")
                else:
                    if last_sum_mz_key is not None and last_sum_mz_key in self.summation_results_dict:
                         res = self.summation_results_dict[last_sum_mz_key]
                         mz_key_disp = f"{last_sum_mz_key}" if last_sum_mz_key != -1 else "Uncalibrated"
                         self.text_widget.insert(END, f"**Last Processed m/z: {mz_key_disp}**\n")
                         self.text_widget.insert(END, f"  Last Selected Range: {res.get('Range_Start',0):.2f} - {res.get('Range_End',0):.2f}\n")
                         self.text_widget.insert(END, f"  Total Integrated Counts: {res.get('Total_Counts',0):.1f}\n")
                         self.text_widget.insert(END, f"  Last Peak Top TOF: {res.get('Max_Count_TOF',0):.2f}\n")
                         self.text_widget.insert(END, f"  Last Peak Top Count: {res.get('Max_Count',0):.1f}\n")
                         self.text_widget.insert(END, "-"*25 + "\n")

                self.text_widget.insert(END, f"\n(Holding integration results for {len(self.summation_results_dict)} m/z values)\n")


    def update_plot(self):
        """ Convenience function to redraw the plot. """
        self.zoom_plot()

    def fit_and_calculate(self):
        """ Performs mass calibration (t = A*sqrt(mz) + B) using identified peaks. """
        valid_peaks = [p for p in self.peak_data if p.get('mz') is not None and p['mz'] > 0]
        if len(valid_peaks) < 2:
            messagebox.showwarning("Calibration Error", "At least 2 valid peaks (with positive integer M/Z) are needed for calibration.")
            return
        try:
            tof_v = np.array([p['tof'] for p in valid_peaks])
            mz_v_float = np.array([float(p['mz']) for p in valid_peaks])

            if np.any(mz_v_float <= 0) or np.any(pd.isna(mz_v_float)):
                messagebox.showerror("Calibration Data Error", "Invalid M/Z values (non-positive or NaN) found in peak data.")
                return

            p0 = None # Initial guess
            try:
                if len(mz_v_float) >= 2 and mz_v_float.max() > mz_v_float.min():
                    min_idx, max_idx = np.argmin(mz_v_float), np.argmax(mz_v_float)
                    tof_min, tof_max = tof_v[min_idx], tof_v[max_idx]
                    mz_min_sqrt, mz_max_sqrt = np.sqrt(mz_v_float[min_idx]), np.sqrt(mz_v_float[max_idx])
                    if mz_max_sqrt > mz_min_sqrt:
                        guess_A = (tof_max - tof_min) / (mz_max_sqrt - mz_min_sqrt)
                        guess_B = tof_min - guess_A * mz_min_sqrt
                        p0 = [guess_A, guess_B]; print(f"Calibration Initial Guess: A={guess_A:.2f}, B={guess_B:.2f}")
                    else: print("Cannot calculate initial guess, M/Z range too narrow.")
            except Exception as e: print(f"Failed to calculate initial guess: {e}")

            with warnings.catch_warnings():
                warnings.simplefilter("ignore", OptimizeWarning)
                self.popt, pcov = curve_fit(self.tof_to_mz_func, mz_v_float, tof_v, p0=p0, maxfev=5000, check_finite=True)

            A, B = self.popt
            perr, warn_cov = np.array([np.inf, np.inf]), False
            if pcov is not None and np.all(np.isfinite(pcov)):
                try:
                    diag_pcov = np.diag(pcov)
                    if np.any(diag_pcov < 0): warn_cov = True
                    else:
                        perr = np.sqrt(diag_pcov)
                        if np.any(np.isinf(perr)) or np.any(np.isnan(perr)): warn_cov = True
                except Exception: warn_cov = True
            else: warn_cov = True

            A_e, B_e = ("N/A", "N/A") if warn_cov else (f"{perr[0]:.4f}", f"{perr[1]:.4f}")

            residuals = tof_v - self.tof_to_mz_func(mz_v_float, *self.popt)
            ss_res, ss_tot = np.sum(residuals**2), np.sum((tof_v - np.mean(tof_v))**2)
            r_squared = 1 - (ss_res / ss_tot) if ss_tot > 1e-9 else 1.0

            print(f"Mass Calibration Complete: A={A:.4f} ± {A_e}, B={B:.4f} ± {B_e}, R²={r_squared:.4f}")
            self.fit_done = True
            msg = f"Mass Calibration Complete\n  A = {A:.4f} ± {A_e}\n  B = {B:.4f} ± {B_e}\n  R² = {r_squared:.4f}"
            if warn_cov: msg += "\n\n(Warning: Issue estimating parameter uncertainties)"
            messagebox.showinfo("Mass Calibration Result", msg)

        except RuntimeError as e:
            messagebox.showerror("Calibration Error", f"Fitting failed (RuntimeError):\n{e}\nCheck peak selection or data.")
            traceback.print_exc(); self.fit_done, self.popt = False, None
        except Exception as e:
            messagebox.showerror("Calibration Error", f"An unexpected error occurred during calibration:\n{e}")
            traceback.print_exc(); self.fit_done, self.popt = False, None
        finally:
            try: self.update_plot(); self.update_text_widget()
            except Exception as e_update: print(f"Error during UI update: {e_update}")


    def plot_fit_curve(self):
        """ Adds the points used for fitting to the plot for visual confirmation. """
        [c.remove() for c in self.ax.collections if c.get_label() == '_fit_points']
        if not (self.fit_done and self.popt is not None and self.peak_data): return
        try:
            valid_peaks = [p for p in self.peak_data if p.get('mz') is not None and p['mz'] > 0]
            if not valid_peaks: return
            tof_p = np.array([p['tof'] for p in valid_peaks])
            count_p = np.array([p.get('max_intensity', np.interp(p['tof'], self.tof.values, self.intensity.values)) for p in valid_peaks])
            self.ax.scatter(tof_p, count_p, color='lime', marker='x', s=60, label='_fit_points', zorder=10)
        except Exception as e: print(f"Error plotting fit points: {e}")


    def tof_to_mz_func(self, mz, A, B):
        """ Calibration function: t = A * sqrt(mz) + B. """
        safe_mz = np.maximum(np.array(mz), 1e-9)
        return A * np.sqrt(safe_mz) + B

    # --- Scroll Method ---
    def scroll(self, value):
        """ Handles the scrollbar movement. """
        if self.tof is not None and not self.tof.empty:
            try:
                index = int(float(value))
                index = max(0, min(index, len(self.tof) - 1))
                self.center_tof = self.tof.iloc[index]
                self.zoom_plot()
            except (ValueError, IndexError) as e: print(f"Scroll error: {e}")
            except Exception as e: print(f"Unexpected scroll error: {e}")

    def zoom_in(self):
        """ Zooms in the plot view. """
        if self.tof is None: return
        try:
            current_min, current_max = self.ax.get_xlim()
            current_width = current_max - current_min
            min_step = np.min(np.diff(self.tof.values)) if len(self.tof) > 1 else 1.0
            min_w = max(10 * min_step, 10)
            self.window_size = max(min_w, current_width / 1.5)
            print(f"Zoom In: Window Width={self.window_size:.2f}")
            self.zoom_plot()
        except Exception as e: print(f"Zoom In Error: {e}")

    def zoom_out(self):
        """ Zooms out the plot view. """
        if self.tof is None or self.tof.empty: return
        try:
            current_min, current_max = self.ax.get_xlim()
            current_width = current_max - current_min
            total_width = self.tof.max() - self.tof.min()
            if total_width <=0 : total_width = self.window_size * 1.5
            self.window_size = min(total_width, current_width * 1.5)
            print(f"Zoom Out: Window Width={self.window_size:.2f}")
            self.zoom_plot()
        except Exception as e: print(f"Zoom Out Error: {e}")


    # --- Peak Selection and Deletion ---
    def select_peak_visually(self):
        """ Enables 'pick mode' to select a peak by clicking its M/Z label. """
        if not self.peak_data:
            messagebox.showinfo("Select Peak", "No peaks have been identified yet.")
            return
        messagebox.showinfo("Select Peak Mode", "Click on the M/Z label of the peak you want to select.\nClick again to deselect.")
        print("Entering Select Peak Mode.")

        if self.click_cid: # Pause range selection listener
            try: self.canvas.mpl_disconnect(self.click_cid); self.click_cid = None
            except TypeError: pass
            print("Range selection listener paused.")

        if not hasattr(self, 'pick_cid') or self.pick_cid is None: # Connect pick listener
            self.pick_cid = self.canvas.mpl_connect('pick_event', self.on_pick)
            print("Peak pick listener connected.")


    def on_pick(self, event):
        """ Handles clicking on a pickable artist (peak text labels). """
        artist = event.artist
        found_idx = -1

        if isinstance(artist, mpl.text.Text) and artist.get_label() == '_peak_text':
            found_idx = next((i for i, p in enumerate(self.peak_data) if p.get('text') == artist), -1)

        if found_idx != -1:
             if self.selected_peak_index == found_idx: # Deselect if already selected
                 self.selected_peak_index = -1
                 print(f"Peak deselected: Index={found_idx}")
             else: # Select the new peak
                 self.selected_peak_index = found_idx
                 print(f"Peak selected: Index={found_idx}, M/Z={self.peak_data[found_idx].get('mz')}")
             self.update_plot(); self.update_text_widget()
        else:
            print("Clicked item is not a peak label.")

        # --- Revert Listeners ---
        if hasattr(self, 'pick_cid') and self.pick_cid: # Disconnect pick listener
            try: self.canvas.mpl_disconnect(self.pick_cid); self.pick_cid = None
            except TypeError: pass
            print("Peak pick listener disconnected.")

        if self.click_cid is None: # Reconnect range listener
            self.click_cid = self.canvas.mpl_connect('button_press_event', self.on_click)
            print("Range selection listener resumed.")

        print("Exited Select Peak Mode.")


    def delete_selected_peak(self):
        """ Deletes the currently selected identified peak. """
        if self.selected_peak_index == -1:
            messagebox.showwarning("Delete Peak", "No peak is currently selected.")
            return
        if not (0 <= self.selected_peak_index < len(self.peak_data)):
            messagebox.showerror("Delete Error", f"Selected peak index is invalid: {self.selected_peak_index}")
            self.selected_peak_index = -1; return

        peak_to_delete = self.peak_data[self.selected_peak_index]
        tof_del, mz_del = peak_to_delete.get('tof', 'N/A'), peak_to_delete.get('mz', 'N/A')
        if not messagebox.askyesno("Confirm Deletion", f"Delete selected peak (TOF={tof_del:.2f}, m/z={mz_del})?"):
            return

        try:
            peak_del_data = self.peak_data.pop(self.selected_peak_index)
            line, text = peak_del_data.get('line'), peak_del_data.get('text')
            if line and line in self.ax.lines: line.remove()
            if text and text in self.ax.texts: text.remove()

            print(f"Peak deleted: TOF={tof_del}, M/Z={mz_del}")
            self.selected_peak_index = -1
            self.update_plot(); self.update_text_widget()

            # Handle calibration check
            if self.fit_done:
                valid_peaks_after_delete = [p for p in self.peak_data if p.get('mz') is not None and p['mz'] > 0]
                if len(valid_peaks_after_delete) < 2:
                    print("Calibration cleared: Fewer than 2 valid peaks remaining.")
                    self.fit_done, self.popt = False, None
                    self.update_plot(); self.update_text_widget()
                else:
                    if messagebox.askyesno("Update Calibration?", "Peak deleted. Recalculate mass calibration?"):
                        print("Recalculating mass calibration...")
                        self.fit_and_calculate()
                    else:
                        print("Keeping previous calibration (accuracy may be reduced).")
                        self.update_plot()

        except Exception as e:
            messagebox.showerror("Delete Error", f"Error deleting peak: {e}")
            traceback.print_exc()
            self.selected_peak_index = -1
            self.update_plot(); self.update_text_widget()


# --- Main execution block ---
if __name__ == "__main__":
    warnings.simplefilter("always", OptimizeWarning)
    def custom_warning_format(message, category, filename, lineno, file=None, line=None):
        return f'\n{os.path.basename(filename)}:{lineno}: {category.__name__}: {message}\n'
    warnings.formatwarning = custom_warning_format

    print("Starting TOF Spectrum Analyzer...")
    app = PeakPicker()
    app.root.mainloop()
    print("Application closed.")