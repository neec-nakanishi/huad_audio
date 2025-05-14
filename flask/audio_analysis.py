import os
import numpy as np
import matplotlib.pyplot as plt
import japanize_matplotlib
from scipy.io import wavfile
from scipy.fft import rfft, rfftfreq
import csv #csvファイルの操作を追加
import pandas as pd # CSVデータを読み込むために必要

class AudioAnalysis:
    def __init__(self, trainee_name, wav_files, output_dir='images/static'):
        self.trainee_name = trainee_name
        self.wav_files = wav_files
        self.output_dir = os.path.join(output_dir, trainee_name) #研修生名フォルダ
        self.labels = ["音量の変化", "高さの変化", "速さの変化", "明瞭さの変化"]

        # 出力フォルダの作成
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)

    @staticmethod
    def calculate_syllables_per_second(data, sample_rate, threshold_db=-20):
        """音節数を1秒あたりで計算"""
        data_db = 20 * np.log10(np.abs(data) + 1e-10)
        voiced_data = data[data_db > threshold_db]
        if len(voiced_data) == 0:
            return 0
        zero_crossings = np.where(np.diff(np.sign(voiced_data)))[0]
        num_syllables = len(zero_crossings) / 2
        duration_seconds = len(data) / sample_rate
        return num_syllables / duration_seconds if duration_seconds > 0 else 0

    def plot_audio_feature(self, x, y, yerr, feature_name, line_color):
        """音声特徴量のグラフを作成して保存"""
        plt.figure(figsize=(8, 6))
        plt.errorbar(
            x, y, yerr=yerr, fmt='-o', capsize=5, color=line_color,
            ecolor='black', elinewidth=2, markeredgecolor='black'
        )
        plt.xticks(x, [f"{i}回目" for i in range(len(x))])
        plt.title(f"{self.trainee_name} - {feature_name}")
        plt.xlabel("審査回数")
        plt.ylabel(feature_name)
        plt.grid(True)
        plt.tight_layout()

        # グラフを保存
        output_path = os.path.join(self.output_dir, f"{self.trainee_name}_{feature_name}.png")
        plt.savefig(output_path)
        plt.close()
        print(f"{feature_name} graph saved: {output_path}")

    def generate_csv(self):
        """音声ファイルを分析し、CSVファイルを生成"""
        csv_path = os.path.join(self.output_dir, f"{self.trainee_name}_features.csv")
        features = {
            "音量の変化": {"values": [], "std": []},
            "高さの変化": {"values": [], "std": []},
            "速さの変化": {"values": [], "std": []},
            "明瞭さの変化": {"values": [], "std": []},
        }

        for wav_file in self.wav_files:
            try:
                sample_rate, data = wavfile.read(wav_file)
                if data.ndim == 2:
                    data = data.mean(axis=1)

                #特徴量の計算
                mean_abs_value = np.mean(np.abs(data))
                volume_db = 20 * np.log10(mean_abs_value) if mean_abs_value > 0 else -np.inf


                yf = rfft(data)
                xf = rfftfreq(len(data), 1 / sample_rate)
                dominant_freq = xf[np.argmax(np.abs(yf))]

                rms = np.sqrt(np.mean(data**2))
                clarity_db = 20 * np.log10(rms) if rms > 0 else -np.inf

                speed = self.calculate_syllables_per_second(data, sample_rate)

                # データを保存
                features["音量の変化"]["values"].append(volume_db)
                features["高さの変化"]["values"].append(dominant_freq)
                features["速さの変化"]["values"].append(speed)
                features["明瞭さの変化"]["values"].append(clarity_db)

            except Exception as e:
                print(f"Error processing {wav_file}: {e}")
                for key in features:
                    features[key]["values"].apeend(np.nan)
            
        # 標準偏差を計算
        for key in features:
            values = features[key]["values"]
            std_dev = np.nanstd(values) if len(values) > 1 else 0
            features[key]["std"] = [std_dev] *len(values)

        # CSVに書き出し
        with open(csv_path, mode='w', newline='', encoding='utf-8') as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(["審査回数", "音量の変化", "音量の変化(標準偏差)",
                             "高さの変化", "高さの変化(標準偏差)",
                             "速さの変化", "速さの変化(標準偏差)",
                             "明瞭さの変化", "明瞭さの変化(標準偏差)"])
            for i in range(len(self.wav_files)):
                writer.writerow([
                    f"{i+1}回目",
                    features["音量の変化"]["values"][i], features["音量の変化"]["std"][i],
                    features["高さの変化"]["values"][i], features["高さの変化"]["std"][i],
                    features["速さの変化"]["values"][i], features["速さの変化"]["std"][i],
                    features["明瞭さの変化"]["values"][i], features["明瞭さの変化"]["std"][i],
                ])
        print(f"CSV saved at {csv_path}")

    def generate_graphs_from_csv(self, csv_path):
        """CSVファイルからグラフを生成"""
        data = np.genfromtxt(csv_path, delimiter=',', skip_header=1, encoding='utf-8')
        x = np.arange(1, len(data) + 1)

        features = ["音量の変化", "高さの変化", "速さの変化", "明瞭さの変化"]
        colors = ["skyblue", "orange", "purple", "green"]

        for i, feature in enumerate(features):
            y = data[:, i * 2 + 1]
            yerr = data[:, i * 2 + 2]
            self.plot_audio_feature(x, y, yerr, feature, colors[i])