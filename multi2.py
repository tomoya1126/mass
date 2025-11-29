import os
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from scipy.optimize import curve_fit
import tkinter as tk
from tkinter import filedialog, simpledialog, Text, END
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

class PeakPicker:
    def __init__(self, master=None):
        self.master = master or tk.Tk()
        self.initialize_variables()
        self.fig, self.ax = plt.subplots(figsize=(10, 5))
        self.create_widgets()
        self.configure_fonts()
        self.shift_active = False
        self.shift_direction = None
        self.shift_index = None
        self.undo_stack = []
        self.redo_stack = []
        self.master.bind('<Left>', self.scroll_left)
        self.master.bind('<Right>', self.scroll_right)
        self.master.bind('<Control-z>', self.undo)
        self.master.bind('<Control-y>', self.redo)

    def initialize_variables(self):
        self.tof = [None] * 10
        self.intensity = [None] * 10
        self.original_tof = [None] * 10
        self.original_intensity = [None] * 10
        self.base_intensity = [None] * 10  # 積算モード変更時の初期値を保存
        self.offsets = [0] * 10
        self.shift_amount = 10  # 移動幅の初期値を10に設定
        self.selected_peaks = []
        self.mz_values = []
        self.peak_data = []
        self.calculated_tof_mz = []
        self.selected_line_index = 0
        self.selected_line_blinking = False
        self.cursor_text = None
        self.fit_done = False
        self.window_size = 5000
        self.center_tof = None
        self.add_lines_mode = True
        self.vertical_lines = []
        self.previous_lines = []
        self.file_paths = [None] * 10
        self.latest_results = {}
        self.plot_type = "TOF"  # 初期状態は TOF
        self.saved_intensities = [None] * 10  # end_add_linesで保存される演算結果
        self.last_saved_intensities = [None] * 10  # end_add_lines前に保存された演算結果
        self.input_mode = True  # 初期状態はインプットモード

    def configure_fonts(self):
        import matplotlib.font_manager as fm
        import matplotlib as mpl

        path = 'C:\\Windows\\Fonts\\msgothic.ttc'
        prop = fm.FontProperties(fname=path)
        mpl.rcParams['font.family'] = prop.get_name()

    def create_widgets(self):
        self.canvas = FigureCanvasTkAgg(self.fig, master=self.master)
        self.canvas.get_tk_widget().grid(row=1, column=0, columnspan=10, rowspan=10, sticky="nsew")

        # 新しいウィンドウを開くボタン
        self.new_window_button = tk.Button(self.master, text="New Window", width=15, height=2, command=self.open_new_window)
        self.new_window_button.grid(row=0, column=0, sticky="nw")

        # ファイル選択ボタン
        self.select_files_button = tk.Button(self.master, text="Select Files", width=15, height=2, command=self.select_files)
        self.select_files_button.grid(row=0, column=1, sticky="nw")

        # 計算結果保存ボタン
        self.save_results_button = tk.Button(self.master, text="Save Results", width=15, height=2, command=self.save_results)
        self.save_results_button.grid(row=0, column=2, sticky="nw")

        # プログラム終了ボタン
        self.quit_button = tk.Button(self.master, text="Quit", width=15, height=2, command=self.master.quit)
        self.quit_button.grid(row=0, column=9, sticky="ne")

        # 平行移動ボタンと操作ボタン
        self.shift_buttons = []
        self.operation_entries = []
        self.apply_buttons = []
        self.subtract_entries = []
        self.subtract_buttons = []

        for i in range(10):
            shift_left_button = tk.Button(self.master, text=f"← {i+1}", width=5, height=1)
            shift_left_button.grid(row=1+i, column=10, sticky="e")
            shift_left_button.bind('<ButtonPress-1>', lambda event, i=i: self.start_shift(event, i, direction='left'))
            shift_left_button.bind('<ButtonRelease-1>', self.stop_shift)
            self.shift_buttons.append(shift_left_button)
            
            shift_right_button = tk.Button(self.master, text=f"{i+1} →", width=5, height=1)
            shift_right_button.grid(row=1+i, column=11, sticky="w")
            shift_right_button.bind('<ButtonPress-1>', lambda event, i=i: self.start_shift(event, i, direction='right'))
            shift_right_button.bind('<ButtonRelease-1>', self.stop_shift)
            self.shift_buttons.append(shift_right_button)

            operation_entry = tk.Entry(self.master, width=10)
            operation_entry.grid(row=1+i, column=12, sticky="e")
            self.operation_entries.append(operation_entry)

            apply_button = tk.Button(self.master, text="Apply", width=5, height=1, command=lambda i=i, operation_entry=operation_entry: self.apply_operation(i, operation_entry))
            apply_button.grid(row=1+i, column=13, sticky="w")
            self.apply_buttons.append(apply_button)

            sub_entry = tk.Entry(self.master, width=5)
            sub_entry.grid(row=1+i, column=14, sticky="e")
            self.subtract_entries.append(sub_entry)

            subtract_button = tk.Button(self.master, text="Subtract", width=5, height=1, command=lambda i=i, sub_entry=sub_entry: self.subtract_intensity(i, sub_entry))
            subtract_button.grid(row=1+i, column=15, sticky="w")
            self.subtract_buttons.append(subtract_button)

        # その他の操作ボタン
        self.zoom_in_button = tk.Button(self.master, text="Zoom In", width=15, height=2, command=self.zoom_in)
        self.zoom_in_button.grid(row=11, column=0, sticky="ew")

        self.zoom_out_button = tk.Button(self.master, text="Zoom Out", width=15, height=2, command=self.zoom_out)
        self.zoom_out_button.grid(row=11, column=1, sticky="ew")

        self.full_view_button = tk.Button(self.master, text="Full View", width=15, height=2, command=self.full_view)
        self.full_view_button.grid(row=11, column=2, sticky="ew")

        self.select_button = tk.Button(self.master, text="Select Line", width=15, height=2, command=self.select_line)
        self.select_button.grid(row=11, column=3, sticky="ew")

        self.delete_button = tk.Button(self.master, text="Delete Line", width=15, height=2, command=self.delete_selected_line)
        self.delete_button.grid(row=11, column=4, sticky="ew")

        self.next_button = tk.Button(self.master, text="Next Line", width=15, height=2, command=self.select_next_line)
        self.next_button.grid(row=11, column=5, sticky="ew")

        self.stop_button = tk.Button(self.master, text="Stop Moving", width=15, height=2, command=self.stop_moving_mode)
        self.stop_button.grid(row=11, column=6, sticky="ew")

        self.fit_button = tk.Button(self.master, text="Fit and Calculate", width=15, height=2, command=self.fit_and_calculate)
        self.fit_button.grid(row=11, column=7, sticky="ew")

        self.end_add_lines_button = tk.Button(self.master, text="End Input", width=15, height=2, command=self.end_add_lines)
        self.end_add_lines_button.grid(row=11, column=8, sticky="ew")

        # モード切り替えボタン
        self.toggle_mode_button = tk.Button(self.master, text="Toggle Mode (Input/Calculation)", width=20, height=2, command=self.toggle_mode)
        self.toggle_mode_button.grid(row=12, column=2, sticky="ew")

        # 移動の幅調整ボタン
        self.increase_shift_button = tk.Button(self.master, text="Increase Shift", width=15, height=2, command=self.increase_shift)
        self.increase_shift_button.grid(row=12, column=0, sticky="ew")
        self.decrease_shift_button = tk.Button(self.master, text="Decrease Shift", width=15, height=2, command=self.decrease_shift)
        self.decrease_shift_button.grid(row=12, column=1, sticky="ew")

        # 入力値リスト表示ウィジェット
        self.text_widget = Text(self.master, height=10, width=50)
        self.text_widget.grid(row=13, column=0, columnspan=10, sticky="nsew")

        # 移動用スクロールバー
        self.scrollbar = tk.Scale(self.master, from_=0, to=100, orient=tk.HORIZONTAL, command=self.scroll)
        self.scrollbar.grid(row=14, column=0, columnspan=10, sticky="ew")

        # プロットタイプ変更ボタン
        self.toggle_plot_button = tk.Button(self.master, text="Toggle Plot (TOF/MZ)", width=15, height=2, command=self.toggle_plot)
        self.toggle_plot_button.grid(row=14, column=10, columnspan=2, sticky="ew")

        # ウィジェットの配置を調整
        self.master.grid_rowconfigure(1, weight=1)
        self.master.grid_rowconfigure(13, weight=1)
        self.master.grid_columnconfigure(0, weight=1)
        for i in range(1, 10):
            self.master.grid_columnconfigure(i, weight=1)

    def start_shift(self, event, index, direction):
        self.shift_active = True
        self.shift_direction = direction
        self.shift_index = index
        self.perform_shift()

    def stop_shift(self, event):
        self.shift_active = False

    def perform_shift(self):
        if self.shift_active:
            if self.shift_direction == 'left':
                self.offsets[self.shift_index] -= self.shift_amount
            elif self.shift_direction == 'right':
                self.offsets[self.shift_index] += self.shift_amount
            self.tof[self.shift_index] = self.original_tof[self.shift_index] + self.offsets[self.shift_index]
            self.zoom_plot()
            self.master.after(100, self.perform_shift)

    def select_files(self):
        file_paths = filedialog.askopenfilenames()
        if file_paths:
            self.initialize_variables()
            self.file_paths = list(file_paths)[:10]  # 最大10ファイルまで
            for i, file_path in enumerate(self.file_paths):
                self.reset_data(i)
                self.load_data(file_path, i)
            self.zoom_plot()
            self.canvas.mpl_connect('button_press_event', self.on_click)
            self.canvas.mpl_connect('motion_notify_event', self.on_motion)

    def reset_data(self, index):
        self.tof[index] = None
        self.intensity[index] = None
        self.original_tof[index] = None
        self.original_intensity[index] = None
        self.base_intensity[index] = None  # 積算モードの初期値をリセット
        self.saved_intensities[index] = None  # 保存された演算結果をリセット
        self.last_saved_intensities[index] = None  # 保存された演算結果をリセット
        self.offsets[index] = 0
        self.selected_peaks = []
        self.mz_values = []
        self.peak_data = []
        self.calculated_tof_mz = []
        self.selected_line_index = 0
        self.selected_line_blinking = False
        self.cursor_text = None
        self.fit_done = False
        self.window_size = 5000
        self.center_tof = None
        self.ax.cla()
        self.text_widget.delete(1.0, END)
        self.canvas.draw()

    def load_data(self, file_path, index):
        if file_path.endswith('.mpa'):
            data = self.read_mpa_file(file_path)
        else:
            data = pd.read_csv(file_path, skiprows=158)
        
        self.tof[index] = data['TOF']
        self.intensity[index] = data['Intensity']
        self.original_tof[index] = self.tof[index].copy()
        self.original_intensity[index] = self.intensity[index].copy()
        self.base_intensity[index] = self.intensity[index].copy()  # 積算モードの初期値として保存
        self.saved_intensities[index] = self.intensity[index].copy()  # 初期値として保存
        self.center_tof = np.mean(self.tof[index])
        self.scrollbar.config(to=len(self.tof[index])-1)

    def read_mpa_file(self, file_path):
        with open(file_path, 'r') as file:
            lines = file.readlines()
        
        data_lines = lines[158:]
        data = [line.strip().split() for line in data_lines]
        df = pd.DataFrame(data, columns=['TOF', 'Intensity'])
        df = df.astype({'TOF': float, 'Intensity': float})
        return df

    def save_results(self):
        base_name = os.path.splitext(os.path.basename(self.file_paths[0]))[0]
        file_path = filedialog.asksaveasfilename(initialfile=f"{base_name}_calculated.csv", defaultextension=".csv", filetypes=[("CSV files", "*.csv")])
        if file_path:
            # テキストウィジェットの内容を取得して整理
            text_content = self.text_widget.get(1.0, END).strip().split("\n")
            columns = ['M/Z'] + [os.path.basename(fp) for fp in self.file_paths if fp]
            data = {col: [] for col in columns}

            for line in text_content:
                parts = line.split(", ")
                mz = parts[1].split(": ")[1]
                data['M/Z'].append(mz)
                for part in parts[2:]:
                    file_name, area = part.split(": ")
                    data[file_name].append(float(area))

            df = pd.DataFrame(data)
            df.to_csv(file_path, index=False)
            print(f"Results saved to {file_path}")

    def calculate_area_for_mz(self, mz, index):
        tof_value = next((t for t, mz_value, line in self.peak_data if mz_value == mz), None)
        if tof_value is None:
            return 0
        mask = (self.tof[index] >= tof_value - 0.5) & (self.tof[index] <= tof_value + 0.5)
        area = np.sum(self.intensity[index][mask])
        return area

    def apply_operation(self, index, entry):
        operation = entry.get().strip()
        if operation == "":
            if self.input_mode:
                self.intensity[index] = self.base_intensity[index].copy()  # 生データに戻す
            elif self.saved_intensities[index] is not None:
                self.intensity[index] = self.saved_intensities[index].copy()  # end_add_linesで保存された演算結果に戻す
        else:
            try:
                if self.input_mode:
                    x = self.base_intensity[index].copy()
                else:
                    x = self.saved_intensities[index].copy() if self.saved_intensities[index] is not None else self.base_intensity[index].copy()
                
                # 一般の演算を評価
                self.intensity[index] = eval(operation)
                self.saved_intensities[index] = self.intensity[index].copy()  # 演算結果を保存
            except Exception as e:
                print(f"Error in operation: {e}")
        self.update_plot()

    def subtract_intensity(self, index, entry):
        try:
            value = float(entry.get())
            self.intensity[index] = self.saved_intensities[index] - value  # 保存された演算結果から減算
            self.saved_intensities[index] = self.intensity[index].copy()  # 減算結果を保存
            entry.config(state=tk.DISABLED)  # Subtractボタンを無効化
            self.update_plot()
        except ValueError:
            print("Please enter a valid number.")

    def select_line(self):
        if self.peak_data:
            self.selected_line_index = 0
            self.update_selected_line()
            self.start_blinking()

    def select_next_line(self):
        if self.peak_data:
            self.selected_line_index = (self.selected_line_index + 1) % len(self.peak_data)
            self.update_selected_line()

    def start_blinking(self):
        self.selected_line_blinking = True
        self.blink_selected_line()

    def stop_blinking(self):
        self.selected_line_blinking = False

    def blink_selected_line(self):
        if not self.selected_line_blinking:
            return
        t, mz, line = self.peak_data[self.selected_line_index]
        current_color = line.get_color()
        new_color = 'white' if current_color == 'r' else 'r'
        line.set_color(new_color)
        self.canvas.draw()
        self.master.after(500, self.blink_selected_line)

    def stop_moving_mode(self):
        self.stop_blinking()
        self.update_selected_line(finalize=True)

    def update_selected_line(self, finalize=False):
        for i, (t, mz, line) in enumerate(self.peak_data):
            if finalize:
                line.set_color('r' if i == self.selected_line_index else 'b')
            else:
                line.set_color('r' if i == self.selected_line_index and self.selected_line_blinking else 'b')
        self.canvas.draw()

    def delete_selected_line(self):
        if self.peak_data:
            _, _, line = self.peak_data.pop(self.selected_line_index)
            line.remove()
            self.selected_line_index = max(0, self.selected_line_index - 1)
            self.update_plot()

    def on_click(self, event):
        if event.inaxes and event.button == 1:
            peak_time = event.xdata
            if self.add_lines_mode:
                mz_value = simpledialog.askinteger("Input", f"Enter integer M/Z value for peak at TOF {peak_time:.2f}:")
                if mz_value is not None:
                    line = self.ax.axvline(x=peak_time, color='b', linestyle='--', linewidth=0.8)
                    self.ax.text(peak_time, max(max(intensity) for intensity in self.intensity if intensity is not None) * 0.95, f"{mz_value}", color='b', ha='center')
                    self.selected_peaks.append(peak_time)
                    self.mz_values.append(mz_value)
                    self.peak_data.append((peak_time, mz_value, line))
            else:
                if len(self.vertical_lines) == 2:
                    _, line_to_remove = self.vertical_lines.pop(0)
                    line_to_remove.remove()
                line = self.ax.axvline(x=peak_time, color='g', linestyle='--', linewidth=0.8)
                self.vertical_lines.append((peak_time, line))
                if len(self.vertical_lines) == 2:
                    self.calculate_area_between_lines()
                self.canvas.draw()

    def on_motion(self, event):
        if event.inaxes:
            peak_time = event.xdata
            display_text = f"t: {peak_time:.2f}"
            if self.fit_done:
                closest_mz, closest_tof = self.get_closest_mz(peak_time)
                display_text += f", M/Z: {closest_mz:.2f}"
            if self.cursor_text is not None:
                self.cursor_text.remove()
            self.cursor_text = self.ax.text(event.xdata, event.ydata, display_text, color='black')
            self.canvas.draw()

    def get_closest_mz(self, tof):
        if not self.calculated_tof_mz:
            return None, 0
        calculated_tofs = np.array([t for t, mz in self.calculated_tof_mz])
        closest_index = np.argmin(np.abs(calculated_tofs - tof))
        closest_tof, closest_mz = self.calculated_tof_mz[closest_index]
        area = np.sum(self.intensity[0].loc[(self.tof[0] >= closest_tof) & (self.tof[0] <= tof)])
        return closest_mz, area

    def scroll_left(self, event):
        self.scrollbar.set(self.scrollbar.get() - 200)
        self.center_tof = self.tof[0][max(0, int(self.scrollbar.get()))]
        self.zoom_plot()

    def scroll_right(self, event):
        self.scrollbar.set(self.scrollbar.get() + 200)
        self.center_tof = self.tof[0][min(len(self.tof[0])-1, int(self.scrollbar.get()))]
        self.zoom_plot()

    def increase_shift(self):
        self.shift_amount += 1
        print(f"Shift amount increased to {self.shift_amount}")

    def decrease_shift(self):
        self.shift_amount = max(1, self.shift_amount - 1)
        print(f"Shift amount decreased to {self.shift_amount}")

    def toggle_plot(self):
        self.plot_type = "MZ" if self.plot_type == "TOF" else "TOF"
        self.zoom_plot()

    def zoom_plot(self):
        self.ax.cla()
        for i in range(len(self.file_paths)):
            if self.tof[i] is not None and self.intensity[i] is not None:
                if self.plot_type == "TOF":
                    self.ax.plot(self.tof[i], self.intensity[i], label=os.path.basename(self.file_paths[i]))
                else:
                    if self.fit_done:
                        mz_values = (self.tof[i] - self.calculated_tof_mz[0][1]) ** 2 / self.calculated_tof_mz[0][0] ** 2
                        self.ax.plot(mz_values, self.intensity[i], label=os.path.basename(self.file_paths[i]))
        for i, (t, mz, line) in enumerate(self.peak_data):
            color = 'r' if i == self.selected_line_index else 'b'
            line.set_color(color)
            if self.plot_type == "TOF":
                self.ax.axvline(x=t, color=color, linestyle='--', linewidth=0.8)
                self.ax.text(t, max(max(intensity) for intensity in self.intensity if intensity is not None) * 0.95, f"{mz}", color='b', ha='center')
            else:
                if self.fit_done:
                    mz_value = (t - self.calculated_tof_mz[0][1]) ** 2 / self.calculated_tof_mz[0][0] ** 2
                    self.ax.axvline(x=mz_value, color=color, linestyle='--', linewidth=0.8)
                    self.ax.text(mz_value, max(max(intensity) for intensity in self.intensity if intensity is not None) * 0.95, f"{mz}", color='b', ha='center')
        self.ax.set_xlabel('Time of Flight (TOF)' if self.plot_type == "TOF" else 'Mass-to-Charge Ratio (M/Z)')
        self.ax.set_ylabel('Intensity')
        self.ax.set_title('TOF-SIMS Data with Selected Peaks')
        self.ax.legend()
        self.ax.grid(True)
        
        if self.plot_type == "TOF":
            self.ax.set_xlim(self.center_tof - self.window_size, self.center_tof + self.window_size)
        else:
            if self.fit_done:
                mz_values = (np.array(self.tof[0]) - self.calculated_tof_mz[0][1]) ** 2 / self.calculated_tof_mz[0][0] ** 2
                self.ax.set_xlim(min(mz_values), max(mz_values))
        self.ax.set_ylim(0, max(max(intensity[(self.tof[i] >= self.center_tof - self.window_size) & (self.tof[i] <= self.center_tof + self.window_size)]) for i, intensity in enumerate(self.intensity) if intensity is not None) * 1.1)
        self.canvas.draw()

    def full_view(self):
        self.ax.cla()
        for i in range(len(self.file_paths)):
            if self.tof[i] is not None and self.intensity[i] is not None:
                if self.plot_type == "TOF":
                    self.ax.plot(self.tof[i], self.intensity[i], label=os.path.basename(self.file_paths[i]))
                else:
                    if self.fit_done:
                        mz_values = (self.tof[i] - self.calculated_tof_mz[0][1]) ** 2 / self.calculated_tof_mz[0][0] ** 2
                        self.ax.plot(mz_values, self.intensity[i], label=os.path.basename(self.file_paths[i]))
        for i, (t, mz, line) in enumerate(self.peak_data):
            line.set_color('b')
            if self.plot_type == "TOF":
                self.ax.axvline(x=t, color='b', linestyle='--', linewidth=0.8)
                self.ax.text(t, max(max(intensity) for intensity in self.intensity if intensity is not None) * 0.95, f"{mz}", color='b', ha='center')
            else:
                if self.fit_done:
                    mz_value = (t - self.calculated_tof_mz[0][1]) ** 2 / self.calculated_tof_mz[0][0] ** 2
                    self.ax.axvline(x=mz_value, color='b', linestyle='--', linewidth=0.8)
                    self.ax.text(mz_value, max(max(intensity) for intensity in self.intensity if intensity is not None) * 0.95, f"{mz}", color='b', ha='center')
        self.ax.set_xlabel('Time of Flight (TOF)' if self.plot_type == "TOF" else 'Mass-to-Charge Ratio (M/Z)')
        self.ax.set_ylabel('Intensity')
        self.ax.set_title('TOF-SIMS Data')
        self.ax.legend()
        self.ax.grid(True)
        
        if self.plot_type == "TOF":
            self.ax.set_xlim(min(min(tof) for tof in self.tof if tof is not None), max(max(tof) for tof in self.tof if tof is not None))
        else:
            if self.fit_done:
                mz_values = (np.array(self.tof[0]) - self.calculated_tof_mz[0][1]) ** 2 / self.calculated_tof_mz[0][0] ** 2
                self.ax.set_xlim(min(mz_values), max(mz_values))
        self.ax.set_ylim(0, max(max(intensity) for intensity in self.intensity if intensity is not None) * 1.1)
        self.canvas.draw()

    def clear_previous_lines(self):
        for _, line in self.previous_lines:
            line.remove()
        self.previous_lines = []
        self.canvas.draw()

    def update_text_widget(self, result):
        self.text_widget.insert(END, result + "\n")

    def update_plot(self):
        self.zoom_plot()

    def fit_and_calculate(self):
        if len(self.peak_data) < 2:
            print("Need at least 2 points to fit the curve.")
            return

        try:
            self.peak_data.sort(key=lambda x: x[0])
            tof_values = np.array([point[0] for point in self.peak_data])
            mz_values = np.array([point[1] for point in self.peak_data])

            popt, _ = curve_fit(self.tof_to_mz, mz_values, tof_values)
            A, B = popt
            print(f"Updated constants: A = {A}, B = {B}")

            max_tof = max(max(self.tof[i]) for i in range(len(self.file_paths)) if self.tof[i] is not None)
            mz_range = np.arange(1, int((max_tof - B) ** 2 / A ** 2) + 1)
            tof_calculated = A * np.sqrt(mz_range) + B

            self.calculated_tof_mz = list(zip(tof_calculated, mz_range))
            self.fit_done = True

        except Exception as e:
            print(f"An error occurred during curve fitting: {e}")

    def scroll(self, value):
        self.center_tof = self.tof[0][int(value)]
        self.zoom_plot()

    def zoom_in(self):
        self.window_size = max(100, self.window_size // 1.5)
        self.zoom_plot()

    def zoom_out(self):
        self.window_size = min(max(len(self.tof[i]) for i in range(len(self.file_paths)) if self.tof[i] is not None), self.window_size * 1.5)
        self.zoom_plot()

    @staticmethod
    def tof_to_mz(mz, A, B):
        return A * np.sqrt(mz) + B

    def end_add_lines(self):
        self.add_lines_mode = False
        print("Line addition and input work ended. Please add two vertical lines.")

        # 演算ボタンと移動ボタンを有効化
        for button in self.shift_buttons + self.apply_buttons + self.subtract_buttons:
            button.config(state=tk.NORMAL)
        for entry in self.operation_entries + self.subtract_entries:
            entry.config(state=tk.NORMAL)

        # 各データセットの演算結果を保存
        for i in range(len(self.file_paths)):
            if self.intensity[i] is not None:
                self.last_saved_intensities[i] = self.saved_intensities[i].copy() if self.saved_intensities[i] is not None else self.base_intensity[i].copy()
                self.saved_intensities[i] = self.intensity[i].copy()

        # 演算結果をプロットに反映
        self.update_plot()

    def toggle_mode(self):
        if self.input_mode:
            self.end_add_lines()
            self.input_mode = False
        else:
            self.add_lines_mode = True
            self.input_mode = True
            print("Switched to Input Mode. Performing operations will update the calculation list.")

    def calculate_area_between_lines(self):
        if len(self.vertical_lines) != 2:
            print("Two vertical lines are required.")
            return

        tof_start, tof_end = sorted([line[0] for line in self.vertical_lines])
        areas = []
        for i in range(len(self.file_paths)):
            if self.tof[i] is not None:
                shifted_tof = self.tof[i]  # 平行移動を考慮
                mask = (shifted_tof >= tof_start) & (shifted_tof <= tof_end)
                area = np.sum(self.saved_intensities[i][mask])  # end_add_linesで保存された演算結果を使用
                areas.append(area)
            else:
                areas.append(0)

        relevant_peaks = [(t, mz) for t, mz, _ in self.peak_data if tof_start <= t <= tof_end]

        # 最新のM/Zごとの結果のみ保持
        latest_results = {}
        for t, mz in relevant_peaks:
            if mz not in latest_results:
                latest_results[mz] = f"TOF: {t:.2f}, M/Z: {mz}" + "".join(f", {os.path.basename(self.file_paths[i])}: {areas[i]:.2f}" for i in range(len(self.file_paths)))
            else:
                for i in range(len(self.file_paths)):
                    key = f"{os.path.basename(self.file_paths[i])}"
                    latest_results[mz] += f", {key}: {areas[i]:.2f}"
                    areas[i] += float(latest_results[mz].split(f"{key}: ")[-1].split(",")[0])

        result = "\n".join(latest_results.values())

        if not self.add_lines_mode:
            existing_text = self.text_widget.get(1.0, END)
            existing_lines = existing_text.strip().split("\n")
            updated_lines = []
            for line in existing_lines:
                if not any(f"M/Z: {mz}" in line for mz in latest_results.keys()):
                    updated_lines.append(line)
            updated_lines.append(result)
            self.text_widget.delete(1.0, END)
            self.text_widget.insert(END, "\n".join(updated_lines) + "\n")

        print(result)

        self.latest_results = latest_results  # 最新の結果を保存

        self.previous_lines = self.vertical_lines
        self.vertical_lines = []
        self.canvas.draw()

    def clear_vertical_lines(self):
        for _, line in self.vertical_lines:
            line.remove()
        self.vertical_lines = []
        self.canvas.draw()

    def clear_previous_lines(self):
        for _, line in self.previous_lines:
            line.remove()
        self.previous_lines = []
        self.canvas.draw()

    def open_new_window(self):
        new_window = tk.Toplevel(self.master)
        PeakPicker(new_window)

    def undo(self, event=None):
        if self.undo_stack:
            last_action = self.undo_stack.pop()
            self.redo_stack.append(last_action)
            # Perform the undo operation based on last_action
            self.update_plot()

    def redo(self, event=None):
        if self.redo_stack:
            last_action = self.redo_stack.pop()
            self.undo_stack.append(last_action)
            # Perform the redo operation based on last_action
            self.update_plot()

if __name__ == "__main__":
    root = tk.Tk()
    app = PeakPicker(master=root)
    tk.mainloop()
