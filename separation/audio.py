import torch
import torchaudio
import numpy as np
import librosa
import soundfile as sf
from scipy.signal.windows import hann

def load(path, offset=0, duration=-1):
    sr = sf.info(path).samplerate
    data, sr = sf.read(path, start=int(offset*sr), frames=int(duration*sr),
                       dtype='float32')
    return data, sr

def save(path, data, sample_rate):
    sf.write(path, data, sample_rate)

def duration(path):
    return sf.info(path).duration

def resample(data, source_sr, target_sr):
    data = torchaudio.transforms.Resample(source_sr, target_sr)(data)
    return data

def pre_stft(data, source_sr, target_sr):
    data = data.T
    if source_sr != target_sr:
        data = resample(data, source_sr, target_sr)
    channel = data.shape[0]
    if channel == 1:
        data = torch.cat((data, data), dim=0)
    elif channel > 2:
        data = data[:2, :]
    return data.T
    
def stft(data, frame_length, frame_step, inverse=False, length=None):
    data = np.asfortranarray(data)
    channel = data.shape[-1]
    window = hann(frame_length, False)
    output = []

    for i in range(channel):
        if not inverse:
            transformed = data[:, i]
            transformed = librosa.core.stft(
                transformed,
                hop_length=frame_step,
                window=window,
                center=False,
                n_fft=frame_length,
            )
            transformed = np.expand_dims(transformed.T, axis=2)
        else:
            transformed = data[:, :, i].T
            transformed = librosa.core.istft(
                transformed,
                hop_length=frame_step,
                window=window,
                center=False,
                win_length=None,
                length=length,
            )
            transformed = np.expand_dims(transformed.T, axis=1)
        output.append(transformed)

    if channel == 1:
        return output[0]
    return np.concatenate(output, axis=1 if inverse else 2)

def to_mag_phase(mix_wave, stem_wave, win_length, hop_length):
    mix_spectrogram = librosa.stft(mix_wave, n_fft=win_length, hop_length=hop_length)
    stem_spec = librosa.stft(stem_wave, n_fft=win_length, hop_length=hop_length)
    mix_magnitude, mix_phase = librosa.magphase(mix_spectrogram)
    stem_magnitude, stem_phase = librosa.magphase(stem_spec)

    mix_mag_max = mix_magnitude.max()
    mix_magnitude /= mix_mag_max
    stem_magnitude /= mix_mag_max

    return mix_magnitude, mix_phase, stem_magnitude, stem_phase

def to_wave(magnitude, phase, mix_spectrogram, win_length, hop_length):
    spectrogram = magnitude * phase
    spectrogram *= mix_spectrogram.max()
    return librosa.istft(spectrogram, win_length=win_length, hop_length=hop_length)