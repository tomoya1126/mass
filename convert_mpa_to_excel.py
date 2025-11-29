import pandas as pd
import os

def convert_files_to_csv(folder_path, file_extension='.mpa'):
    # CSVとして保存するサブフォルダを作成
    csv_folder_path = os.path.join(folder_path, 'CSV')
    if not os.path.exists(csv_folder_path):
        os.makedirs(csv_folder_path)

    # フォルダ内のすべてのファイルを走査
    for filename in os.listdir(folder_path):
        # 指定された拡張子を持つファイルをチェック
        if filename.endswith(file_extension):
            file_path = os.path.join(folder_path, filename)
            # ファイルを部分的に読み込み
            try:
                # 159行目までを読み込む（1列のみと仮定）
                data_before = pd.read_csv(file_path, header=None, delimiter="\t", nrows=158)
                # 160行目以降を読み込む（2列と仮定）
                data_after = pd.read_csv(file_path, header=None, delimiter="\t", skiprows=158)
                # データを縦に結合
                data_combined = pd.concat([data_before, data_after], ignore_index=True)
            except Exception as e:
                print(f"Error reading {filename}: {e}")
                continue  # ファイルの読み込みに失敗した場合はスキップ
            
            # 結合したデータのCSVファイル名を作成
            csv_filename = filename.replace(file_extension, '.csv')
            csv_file_path = os.path.join(csv_folder_path, csv_filename)
            # CSVとして保存
            data_combined.to_csv(csv_file_path, index=False)
            print(f"Converted and saved {filename} to {csv_filename} in CSV folder")

# 使用例
folder_path = 'D:\\UMP固体データ'  # フォルダのパスを指定
convert_files_to_csv(folder_path)
