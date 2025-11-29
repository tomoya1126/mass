import tkinter as tk
from tkinter import filedialog, messagebox
import os
import struct
import traceback # エラーの詳細情報を取得するためのライブラリ

def read_chn_data(file_path):
    """
    シンプルなバイナリ形式の.chnファイルを読み込む。
    """
    try:
        with open(file_path, 'rb') as f:
            f.seek(0, 2)
            file_size = f.tell()
            if file_size % 4 != 0:
                raise ValueError("ファイルサイズが4の倍数ではありません。異なる形式のCHNファイルの可能性があります。")
            num_channels = file_size // 4
            f.seek(0)
            counts_format = f'<{num_channels}I'
            counts_tuple = struct.unpack(counts_format, f.read(file_size))
            return list(counts_tuple)
    except FileNotFoundError:
        raise
    except Exception as e:
        raise IOError(f"ファイルの読み込みに失敗しました。サポートされていない形式の可能性があります。\n詳細: {e}")

class ChnConverterApp:
    def __init__(self, root):
        self.root = root
        self.root.title("CHN to TXT Converter (Diagnostic)")
        self.root.geometry("500x250")

        self.input_path = tk.StringVar()
        self.output_folder = tk.StringVar()

        tk.Label(root, text="入力.chnファイル:").grid(row=0, column=0, padx=10, pady=10, sticky="w")
        tk.Entry(root, textvariable=self.input_path, width=50).grid(row=0, column=1, padx=10, pady=10)
        tk.Button(root, text="選択...", command=self.select_input_file).grid(row=0, column=2, padx=10, pady=10)

        tk.Label(root, text="出力先フォルダ:").grid(row=1, column=0, padx=10, pady=10, sticky="w")
        tk.Entry(root, textvariable=self.output_folder, width=50).grid(row=1, column=1, padx=10, pady=10)
        tk.Button(root, text="選択...", command=self.select_output_folder).grid(row=1, column=2, padx=10, pady=10)

        tk.Button(root, text="変換実行", command=self.convert_file, font=("Helvetica", 12, "bold"), bg="lightgreen").grid(row=2, column=1, pady=20)

        self.status_label = tk.Label(root, text="ファイルと出力先を選択してください", fg="blue")
        self.status_label.grid(row=3, column=0, columnspan=3, pady=10)

    def select_input_file(self):
        path = filedialog.askopenfilename(
            title="変換する.chnファイルを選択してください",
            filetypes=[("MCA Channel File", "*.chn"), ("All Files", "*.*")]
        )
        if path:
            self.input_path.set(path)

    def select_output_folder(self):
        path = filedialog.askdirectory(title="保存先のフォルダを選択してください")
        if path:
            self.output_folder.set(path)

    def convert_file(self):
        # (この部分は変更ありません)
        input_p = self.input_path.get()
        output_f = self.output_folder.get()
        if not input_p or not output_f:
            messagebox.showerror("エラー", "入力ファイルと出力先フォルダの両方を選択してください。")
            return
        base_name = os.path.basename(input_p)
        file_name_without_ext = os.path.splitext(base_name)[0]
        output_path = os.path.join(output_f, f"{file_name_without_ext}.txt")
        try:
            self.status_label.config(text="変換処理中...", fg="blue")
            self.root.update_idletasks()
            counts = read_chn_data(input_p)
            channels = range(len(counts))
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(f"# Source File: {base_name}\n")
                f.write("# Channel,Counts\n")
                for channel, count in zip(channels, counts):
                    f.write(f"{channel},{count}\n")
            self.status_label.config(text=f"✅ 変換完了: {output_path}", fg="green")
            messagebox.showinfo("成功", f"ファイルの変換が完了しました。\n保存先: {output_path}")
        except Exception as e:
            self.status_label.config(text=f"❌ エラー: {e}", fg="red")
            messagebox.showerror("変換エラー", f"ファイルの変換中にエラーが発生しました。\n\n詳細: {e}")

# --- メインの実行部分をエラーキャッチで囲む ---
if __name__ == '__main__':
    try:
        root = tk.Tk()
        app = ChnConverterApp(root)
        root.mainloop()
    except Exception as e:
        # 起動時のどんなエラーもここでキャッチする
        error_message = traceback.format_exc()
        # エラー内容をファイルに書き出す
        with open("error_log.txt", "w", encoding="utf-8") as f:
            f.write("スクリプトの起動中に予期せぬエラーが発生しました。\n")
            f.write("="*50 + "\n")
            f.write(error_message)
        # 念のためコンソールにも表示
        print(f"An error occurred. See error_log.txt for details.")
        print(error_message)