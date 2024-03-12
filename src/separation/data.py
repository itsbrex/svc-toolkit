import math
from multiprocessing import cpu_count
from concurrent.futures import ThreadPoolExecutor, as_completed

import numpy as np
import pandas as pd
import torch
from tqdm import tqdm
from numpy import random
from torch.utils.data import Dataset

from separation.audio import load, to_mag_phase

class MagnitudeDataset(Dataset):
    def __init__(self, csv_path, expand_factor, win_length, hop_length, patch_length, sample_rate) -> None:
        self.win_length = win_length
        self.hop_length = hop_length
        self.patch_length = patch_length
        self.expand_factor = expand_factor
        self.sample_rate = sample_rate

        df = pd.read_csv(csv_path)

        self.magnitudes = [None] * len(df)
        self.expanded_magnitudes = []

        with ThreadPoolExecutor(max_workers=cpu_count()) as executor:
            futures = [executor.submit(self.load_magnitude, index, row) for index, row in df.iterrows()]

            for future in tqdm(as_completed(futures), total=len(df)):
                index, mix_magnitude, stem_magnitude, weight = future.result()
                self.magnitudes[index] = (mix_magnitude, stem_magnitude)

                self.expanded_magnitudes.extend([index] * weight)

            self.expanded_magnitudes = sorted(self.expanded_magnitudes)

    def load_magnitude(self, index, row):
        # Load audio
        mixture_path = row['mixture_path']
        stem_path = row['stem_path']
        mixture_wave, mixture_sr = load(mixture_path, sr=self.sample_rate)
        stem_wave, _stem_sr = load(stem_path, sr=self.sample_rate)

        # Get magnitude
        mix_magnitude, _mix_phase = to_mag_phase(mixture_wave, self.win_length, self.hop_length)
        stem_magnitude, _stem_phase = to_mag_phase(stem_wave, self.win_length, self.hop_length)

        mix_magnitude_max = mix_magnitude.max()
        mix_magnitude /= mix_magnitude_max
        stem_magnitude /= mix_magnitude_max

        # Expand dataset by duration of each song
        duration = mixture_wave.shape[0] / mixture_sr
        weight = math.ceil(duration / self.expand_factor)

        return index, mix_magnitude, stem_magnitude, weight

    def __len__(self):
        return len(self.expanded_magnitudes)
    
    def __getitem__(self, index):
        actual_index = self.expanded_magnitudes[index]
        mix_magnitude, stem_magnitude = self.magnitudes[actual_index]
        start = random.randint(0, mix_magnitude.shape[1] - self.patch_length + 1)

        mix_magnitude = mix_magnitude[np.newaxis, : -1, start: start + self.patch_length]
        stem_magnitude = stem_magnitude[np.newaxis, : -1, start: start + self.patch_length]

        mix_tensor = torch.from_numpy(mix_magnitude)
        stem_tensor = torch.from_numpy(stem_magnitude)

        return mix_tensor, stem_tensor

if __name__ == "__main__":
    print('test')
    dataset = MagnitudeDataset('train.csv', 30, 1024, 768, 128)