import os
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from scipy.ndimage import gaussian_filter1d
from scipy.signal import find_peaks
import time

def is_mostly_increasing(arr, tolerance=0.7):
    return np.mean(np.diff(arr) > 0) >= tolerance

def is_mostly_decreasing(arr, tolerance=0.7):
    return np.mean(np.diff(arr) < 0) >= tolerance

def detect_reliable_peaks(data, window=20, tolerance=0.7, sigma=5, threshold=1.02):
    # データをガウスフィルタでスムージング
    smoothed_data = gaussian_filter1d(data, sigma=sigma)
    
    # 前後20ポイントの平均を計算
    windowed_mean = np.convolve(smoothed_data, np.ones(2 * window + 1) / (2 * window + 1), mode='same')
    
    # データがその窓の平均よりも一定割合以上高い点をピークとして検出
    potential_peaks = np.where(smoothed_data > windowed_mean * threshold)[0]
    
    # find_peaksを用いてさらに厳格にピークをフィルタリング
    peaks, _ = find_peaks(smoothed_data[potential_peaks], height=np.mean(smoothed_data) / 4)
    reliable_peaks = potential_peaks[peaks]

    # 単調増加・単調減少の確認
    final_peaks = []
    for peak in reliable_peaks:
        if peak > window and peak < len(smoothed_data) - window:
            if is_mostly_increasing(smoothed_data[peak-window:peak], tolerance) and is_mostly_decreasing(smoothed_data[peak:peak+window], tolerance):
                final_peaks.append(peak)
    return np.array(final_peaks)

def filter_close_peaks(peaks, intensities, distance=50):
    filtered_peaks = []
    peaks = sorted(peaks, key=lambda x: intensities[x], reverse=True)  # 強度でソート
    for peak in peaks:
        if all(abs(peak - fp) > distance for fp in filtered_peaks):
            filtered_peaks.append(peak)
    return np.array(filtered_peaks)

def plot_data_with_peaks(file_path, output_folder):
    start_time = time.time()

    # データを読み込む
    data = pd.read_csv(file_path)
    tof = data.iloc[158:, 0].astype(float)
    intensity = data.iloc[158:, 1].astype(float)

    # 信頼性の高いピークを検出
    peaks = detect_reliable_peaks(intensity.values)

    # 50以内に複数のピークがある場合、最大のピークのみを選択
    filtered_peaks = filter_close_peaks(peaks, intensity.values)

    # 検出されたピークのうち、強度が高い順に30個を選択
    if len(filtered_peaks) > 30:
        peak_intensities = intensity.iloc[filtered_peaks]
        top_peaks = filtered_peaks[np.argsort(peak_intensities.iloc[-30:])]
    else:
        top_peaks = filtered_peaks

    # グラフの描画
    plt.figure(figsize=(15, 7))
    plt.plot(tof, intensity, label='Intensity', linestyle='-')

    # 縦線を追加してピークをマーク
    for peak in top_peaks:
        plt.axvline(x=tof.iloc[peak], color='r', linestyle='--', linewidth=0.8, label='Detected Peaks')

    plt.title('TOF-SIMS Data with Detected Peaks')
    plt.xlabel('Time of Flight (TOF)')
    plt.ylabel('Intensity')
    plt.legend()
    plt.grid(True)

    # 画像として保存
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)
    output_path = os.path.join(output_folder, os.path.basename(file_path).replace('.csv', '.jpg'))
    plt.savefig(output_path)
    plt.close()

    end_time = time.time()
    return end_time - start_time

def process_folder(input_directory, output_directory):
    total_time = 0
    for filename in os.listdir(input_directory):
        if filename.endswith('.csv'):
            file_path = os.path.join(input_directory, filename)
            processing_time = plot_data_with_peaks(file_path, output_directory)
            print(f"Processing time for {filename}: {processing_time:.2f} seconds")
            total_time += processing_time
    print(f"Total processing time: {total_time:.2f} seconds")

# 使用例
input_directory = r"C:\Users\discu\OneDrive\デスクトップ\UMP固体データ\CSV"  # 入力フォルダパス
output_directory = r"C:\Users\discu\OneDrive\デスクトップ\UMP固体データ\jpg"  # 出力フォルダパス
process_folder(input_directory, output_directory)
