import os
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from scipy.optimize import curve_fit
import tkinter as tk
from tkinter import filedialog, simpledialog, Text, END
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

class PeakPicker:
    def __init__(self):
        self.tof = None
        self.intensity = None
        self.original_intensity = None
        self.selected_peaks = []
        self.mz_values = []
        self.peak_data = []  # (t, M/Z, line)のリスト
        self.calculated_tof_mz = []
        self.selected_line_index = 0
        self.selected_line_blinking = False
        self.cursor_text = None
        self.fit_done = False
        self.window_size = 5000
        self.center_tof = None
        self.fig, self.ax = plt.subplots(figsize=(10, 5))
        self.root = tk.Tk()
        self.create_widgets()
        self.add_lines_mode = True  # ライン追加モード
        self.vertical_lines = []  # 縦線を格納
        self.previous_lines = []  # 前の縦線を格納
        self.configure_fonts()

    def configure_fonts(self):
        import matplotlib.font_manager as fm
        import matplotlib as mpl

        path = 'C:\\Windows\\Fonts\\msgothic.ttc'
        prop = fm.FontProperties(fname=path)
        mpl.rcParams['font.family'] = prop.get_name()

    def create_widgets(self):
        # グラフエリア
        self.canvas = FigureCanvasTkAgg(self.fig, master=self.root)
        self.canvas.get_tk_widget().grid(row=1, column=0, columnspan=9, sticky="nsew")

        # ファイル選択ボタン
        self.select_file_button = tk.Button(self.root, text="Select File", width=20, height=2, command=self.select_file)
        self.select_file_button.grid(row=0, column=0, sticky="nw")

        # 計算結果保存ボタン
        self.save_results_button = tk.Button(self.root, text="Save Results", width=20, height=2, command=self.save_results)
        self.save_results_button.grid(row=0, column=1, sticky="nw")

        # プログラム終了ボタン
        self.quit_button = tk.Button(self.root, text="Quit", width=20, height=2, command=self.root.quit)
        self.quit_button.grid(row=0, column=8, sticky="ne")

        # 拡大縮小ボタン
        self.zoom_in_button = tk.Button(self.root, text="Zoom In", width=20, height=2, command=self.zoom_in)
        self.zoom_in_button.grid(row=2, column=0, sticky="ew")

        self.zoom_out_button = tk.Button(self.root, text="Zoom Out", width=20, height=2, command=self.zoom_out)
        self.zoom_out_button.grid(row=2, column=1, sticky="ew")

        # 全体表示ボタン
        self.full_view_button = tk.Button(self.root, text="Full View", width=20, height=2, command=self.full_view)
        self.full_view_button.grid(row=2, column=2, sticky="ew")

        # 全体から値を引くエントリとボタン
        self.subtract_entry = tk.Entry(self.root)
        self.subtract_entry.grid(row=2, column=3, sticky="ew")
        self.subtract_button = tk.Button(self.root, text="Subtract Count", width=20, height=2, command=self.subtract_count)
        self.subtract_button.grid(row=2, column=4, sticky="ew")

        # その他の操作ボタン
        self.select_button = tk.Button(self.root, text="Select Line", width=20, height=2, command=self.select_line)
        self.select_button.grid(row=3, column=0, sticky="ew")

        self.delete_button = tk.Button(self.root, text="Delete Line", width=20, height=2, command=self.delete_selected_line)
        self.delete_button.grid(row=3, column=1, sticky="ew")

        self.next_button = tk.Button(self.root, text="Next Line", width=20, height=2, command=self.select_next_line)
        self.next_button.grid(row=3, column=2, sticky="ew")

        self.stop_button = tk.Button(self.root, text="Stop Moving", width=20, height=2, command=self.stop_moving_mode)
        self.stop_button.grid(row=3, column=3, sticky="ew")

        self.fit_button = tk.Button(self.root, text="Fit and Calculate", width=20, height=2, command=self.fit_and_calculate)
        self.fit_button.grid(row=3, column=4, sticky="ew")

        self.end_add_lines_button = tk.Button(self.root, text="End Input", width=20, height=2, command=self.end_add_lines)
        self.end_add_lines_button.grid(row=3, column=5, sticky="ew")

        self.resume_add_lines_button = tk.Button(self.root, text="Resume Input", width=20, height=2, command=self.resume_add_lines)
        self.resume_add_lines_button.grid(row=3, column=6, sticky="ew")

        # 入力値リスト表示ウィジェット
        self.text_widget = Text(self.root, height=10, width=50)
        self.text_widget.grid(row=4, column=0, columnspan=9, sticky="nsew")

        # 移動用スクロールバー
        self.scrollbar = tk.Scale(self.root, from_=0, to=100, orient=tk.HORIZONTAL, command=self.scroll)
        self.scrollbar.grid(row=5, column=0, columnspan=9, sticky="ew")

        # ウィジェットの配置を調整
        self.root.grid_rowconfigure(1, weight=1)
        self.root.grid_rowconfigure(4, weight=1)
        self.root.grid_columnconfigure(0, weight=1)
        for i in range(1, 9):
            self.root.grid_columnconfigure(i, weight=1)

    def select_file(self):
        file_path = filedialog.askopenfilename()
        if file_path:
            self.reset_data()
            self.file_path = file_path
            self.load_data(file_path)
            self.zoom_plot()
            self.canvas.mpl_connect('button_press_event', self.on_click)
            self.canvas.mpl_connect('motion_notify_event', self.on_motion)

    def reset_data(self):
        self.tof = None
        self.intensity = None
        self.original_intensity = None
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

    def load_data(self, file_path):
        if file_path.endswith('.mpa'):
            data = self.read_mpa_file(file_path)
        else:
            data = pd.read_csv(file_path, skiprows=158)
        
        self.tof = data['TOF']
        self.intensity = data['Intensity']
        self.original_intensity = self.intensity.copy()
        self.center_tof = np.mean(self.tof)
        self.scrollbar.config(to=len(self.tof)-1)

    def read_mpa_file(self, file_path):
        with open(file_path, 'r') as file:
            lines = file.readlines()
        
        # データが始まる行を見つける
        data_lines = lines[158:]
        
        # データをDataFrameに変換
        data = [line.strip().split() for line in data_lines]
        df = pd.DataFrame(data, columns=['TOF', 'Intensity'])
        
        # データ型を適切に変換
        df = df.astype({'TOF': float, 'Intensity': float})
        
        return df

    def save_results(self):
        base_name = os.path.splitext(os.path.basename(self.file_path))[0]
        file_path = filedialog.asksaveasfilename(initialfile=f"{base_name}_calculated.csv", defaultextension=".csv", filetypes=[("CSV files", "*.csv")])
        if file_path:
            text_content = self.text_widget.get("1.0", END).strip()
            lines = text_content.split('\n')
            data = []
            for line in lines:
                if line.startswith("TOF"):
                    parts = line.split(', ')
                    t_value = float(parts[0].split(': ')[1])
                    mz_value = int(parts[1].split(': ')[1])
                    area_value = float(parts[2].split(': ')[1])
                    data.append([t_value, mz_value, area_value])
            df = pd.DataFrame(data, columns=['TOF', 'M/Z', 'Area'])
            df.to_csv(file_path, index=False)
            print(f"Results saved to {file_path}")

    def subtract_count(self):
        try:
            subtract_value = float(self.subtract_entry.get())
            self.intensity = self.original_intensity - subtract_value
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
        self.root.after(500, self.blink_selected_line)

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
        if event.inaxes and event.button == 1:  # 左クリックで入力
            peak_time = event.xdata
            if self.add_lines_mode:
                mz_value = simpledialog.askinteger("Input", f"Enter integer M/Z value for peak at TOF {peak_time:.2f}:")
                if mz_value is not None:
                    line = self.ax.axvline(x=peak_time, color='b', linestyle='--', linewidth=0.8)
                    self.ax.text(peak_time, max(self.intensity) * 0.95, f"{mz_value}", color='b', ha='center')
                    self.selected_peaks.append(peak_time)
                    self.mz_values.append(mz_value)
                    self.peak_data.append((peak_time, mz_value, line))
                    if not self.add_lines_mode:
                        self.update_text_widget()
            else:
                if len(self.vertical_lines) == 2:
                    # 三本目のラインが追加されたら一本目のラインを消す
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
        area = np.sum(self.intensity[(self.tof >= closest_tof) & (self.tof <= tof)])
        return closest_mz, area

    def zoom_plot(self):
        self.ax.cla()
        self.ax.plot(self.tof, self.intensity, label='Intensity')
        for i, (t, mz, line) in enumerate(self.peak_data):
            color = 'r' if i == self.selected_line_index else 'b'
            line.set_color(color)
            self.ax.axvline(x=t, color=color, linestyle='--', linewidth=0.8)
            self.ax.text(t, max(self.intensity) * 0.95, f"{mz}", color='b', ha='center')
        self.ax.set_xlabel('Time of Flight (TOF)')
        self.ax.set_ylabel('Intensity')
        self.ax.set_title('TOF-SIMS Data with Selected Peaks')
        self.ax.legend()
        self.ax.grid(True)
        
        # 拡大表示の範囲設定
        self.ax.set_xlim(self.center_tof - self.window_size, self.center_tof + self.window_size)
        self.ax.set_ylim(0, max(self.intensity[(self.tof >= self.center_tof - self.window_size) & (self.tof <= self.center_tof + self.window_size)]) * 1.1)
        self.canvas.draw()

    def full_view(self):
        # 全体表示の範囲設定
        self.ax.cla()
        self.ax.plot(self.tof, self.intensity, label='Intensity')
        for i, (t, mz, line) in enumerate(self.peak_data):
            line.set_color('b')
            self.ax.axvline(x=t, color='b', linestyle='--', linewidth=0.8)
            self.ax.text(t, max(self.intensity) * 0.95, f"{mz}", color='b', ha='center')
        self.ax.set_xlabel('Time of Flight (TOF)')
        self.ax.set_ylabel('Intensity')
        self.ax.set_title('TOF-SIMS Data')
        self.ax.legend()
        self.ax.grid(True)
        self.ax.set_xlim(min(self.tof), max(self.tof))
        self.ax.set_ylim(0, max(self.intensity) * 1.1)
        self.canvas.draw()

    def clear_previous_lines(self):
        for _, line in self.previous_lines:
            line.remove()
        self.previous_lines = []
        self.canvas.draw()

    def update_text_widget(self):
        if not self.add_lines_mode:
            self.text_widget.delete(1.0, END)
            for t, mz, line in self.peak_data:
                area = np.sum(self.intensity[(self.tof >= t) & (self.tof <= t + 1)])
                self.text_widget.insert(END, f"TOF: {t:.2f}, M/Z: {mz}, Area: {area:.2f}\n")

    def update_plot(self):
        self.zoom_plot()

    def fit_and_calculate(self):
        if len(self.peak_data) < 2:
            print("Need at least 2 points to fit the curve.")
            return

        try:
            # (t, M/Z)リストをtの値で昇順にソート
            self.peak_data.sort(key=lambda x: x[0])

            # ソートされたデータからTOF値とM/Z値を抽出
            tof_values = np.array([point[0] for point in self.peak_data])
            mz_values = np.array([point[1] for point in self.peak_data])

            # t = A * sqrt(mz) + B のパラメータフィット
            popt, _ = curve_fit(self.tof_to_mz, mz_values, tof_values)
            A, B = popt
            print(f"Updated constants: A = {A}, B = {B}")

            # TOFの範囲に対応するM/Zの値を計算
            max_tof = max(self.tof)
            mz_range = np.arange(1, int((max_tof - B) ** 2 / A ** 2) + 1)
            tof_calculated = A * np.sqrt(mz_range) + B

            # 結果を保存
            self.calculated_tof_mz = list(zip(tof_calculated, mz_range))
            self.fit_done = True

        except Exception as e:
            print(f"An error occurred during curve fitting: {e}")

    def scroll(self, value):
        self.center_tof = self.tof[int(value)]
        self.zoom_plot()

    def zoom_in(self):
        self.window_size = max(100, self.window_size // 1.5)  # ズームインの幅を大きくする
        self.zoom_plot()

    def zoom_out(self):
        self.window_size = min(len(self.tof), self.window_size * 1.5)  # ズームアウトの幅を大きくする
        self.zoom_plot()

    @staticmethod
    def tof_to_mz(mz, A, B):
        return A * np.sqrt(mz) + B

    def end_add_lines(self):
        self.add_lines_mode = False
        print("Line addition and input work ended. Please add two vertical lines.")

    def resume_add_lines(self):
        self.add_lines_mode = True
        self.selected_peaks = []
        self.vertical_lines = []
        print("Line addition and input work resumed.")

    def calculate_area_between_lines(self):
        if len(self.vertical_lines) != 2:
            print("Two vertical lines are required.")
            return

        tof_start, tof_end = sorted([line[0] for line in self.vertical_lines])
        mask = (self.tof >= tof_start) & (self.tof <= tof_end)
        area = np.sum(self.intensity[mask])

        # 選択されたラインが縦線の間にあるか確認
        relevant_peaks = [(t, mz) for t, mz, _ in self.peak_data if tof_start <= t <= tof_end]

        # 結果を表示
        result = ""
        for t, mz in relevant_peaks:
            result += f"TOF: {t:.2f}, M/Z: {mz}, Area: {area:.2f}\n"

        # テキストウィジェットを更新
        if not self.add_lines_mode:
            existing_text = self.text_widget.get(1.0, END)
            new_text = "\n".join([line for line in existing_text.split("\n") if f"TOF: {t:.2f}, M/Z: {mz}" not in line])
            self.text_widget.delete(1.0, END)
            self.text_widget.insert(END, new_text.strip() + "\n" + result.strip() + "\n")

        print(result)

        # 次の縦線が追加されたときに消えるように前の縦線を保存
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

if __name__ == "__main__":
    peak_picker = PeakPicker()
    tk.mainloop()
