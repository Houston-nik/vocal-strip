from __future__ import annotations

import numpy as np
from scipy.ndimage import median_filter
from scipy.signal import istft, stft

from engine.audio_io import TARGET_SR

N_FFT = 4096
HOP = 1024


def _stft(channel: np.ndarray, sample_rate: int) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    frequencies, times, matrix = stft(
        channel,
        fs=sample_rate,
        nperseg=N_FFT,
        noverlap=N_FFT - HOP,
        window="hann",
        boundary="zeros",
        padded=True,
    )
    return frequencies, times, matrix


def _istft(matrix: np.ndarray, sample_rate: int, length: int) -> np.ndarray:
    _, recovered = istft(
        matrix,
        fs=sample_rate,
        nperseg=N_FFT,
        noverlap=N_FFT - HOP,
        window="hann",
        input_onesided=True,
    )
    recovered = recovered.astype(np.float32, copy=False)
    if recovered.size >= length:
        return recovered[:length]
    return np.pad(recovered, (0, length - recovered.size))


def _center_vocal_mask(left: np.ndarray, right: np.ndarray, frequencies: np.ndarray) -> np.ndarray:
    mag_left = np.abs(left)
    mag_right = np.abs(right)
    denom = np.maximum(np.maximum(mag_left, mag_right), 1e-8)
    magnitude_similarity = np.minimum(mag_left, mag_right) / denom

    phase_left = np.angle(left)
    phase_right = np.angle(right)
    phase_delta = np.abs(np.angle(np.exp(1j * (phase_left - phase_right))))
    phase_similarity = np.cos(np.clip(phase_delta, 0.0, np.pi))
    phase_similarity = np.clip(phase_similarity, 0.0, 1.0)

    mask = np.power(np.clip(magnitude_similarity * phase_similarity, 0.0, 1.0), 1.35)

    # Keep kick/bass: they often sit in the center too, like vocals.
    bass_protect = np.clip((180.0 - frequencies) / 180.0, 0.0, 1.0)[:, None]
    air_protect = np.clip((frequencies - 12000.0) / 4000.0, 0.0, 1.0)[:, None]
    mask = mask * (1.0 - 0.88 * bass_protect) * (1.0 - 0.35 * air_protect)

    mask = median_filter(mask, size=(1, 7))
    return np.clip(mask, 0.0, 1.0).astype(np.float32)


def _repeating_background_mask(magnitude: np.ndarray) -> np.ndarray:
    """REPET-style: repeating accompaniment is the median across similar frames."""
    frames = magnitude.shape[1]
    if frames < 16:
        return np.zeros_like(magnitude)

    energy = np.log1p(np.sum(magnitude, axis=0))
    energy = energy - np.mean(energy)
    if float(np.max(np.abs(energy))) < 1e-6:
        return np.zeros_like(magnitude)

    correlation = np.correlate(energy, energy, mode="full")[frames - 1 :]
    min_period = 8
    max_period = min(frames // 2, int(8.0 * TARGET_SR / HOP))
    if max_period <= min_period:
        return np.zeros_like(magnitude)

    search = correlation[min_period:max_period]
    period = int(np.argmax(search) + min_period)
    if correlation[period] < 0.12 * correlation[0]:
        return np.zeros_like(magnitude)

    padded = frames + (-frames % period)
    tiled = np.pad(magnitude, ((0, 0), (0, padded - frames)), mode="edge")
    repeating = np.median(tiled.reshape(magnitude.shape[0], -1, period), axis=1)
    repeating = np.tile(repeating, (1, tiled.shape[1] // period))[:, :frames]
    background = np.minimum(repeating, magnitude)
    vocalish = np.clip(magnitude - background, 0.0, None)
    total = np.maximum(magnitude, 1e-8)
    return np.clip(vocalish / total, 0.0, 1.0).astype(np.float32)


def separate_center_vocals(
    stereo: np.ndarray,
    sample_rate: int = TARGET_SR,
) -> tuple[np.ndarray, np.ndarray]:
    """Split stereo mix into instrumental and vocal-ish stems.

    Vocals are usually in the middle of a stereo track. We keep what is
    different between left and right (the band), and gently cut what is
    identical in both ears (the singer). A repeating-pattern pass then
    peels leftover voice from the groove.
    """
    if stereo.ndim != 2 or stereo.shape[0] != 2:
        raise ValueError("Need stereo audio shaped (2, samples).")

    left_wave = stereo[0]
    right_wave = stereo[1]
    length = left_wave.size

    frequencies, _, left_spec = _stft(left_wave, sample_rate)
    _, _, right_spec = _stft(right_wave, sample_rate)

    mid = (left_spec + right_spec) / 2.0
    side = (left_spec - right_spec) / 2.0

    center_mask = _center_vocal_mask(left_spec, right_spec, frequencies)
    repeating_mask = _repeating_background_mask(np.abs(mid))
    vocal_mask = np.clip(np.maximum(center_mask, 0.55 * repeating_mask * center_mask), 0.0, 1.0)

    instrumental_mid = mid * (1.0 - vocal_mask)
    vocal_mid = mid * vocal_mask

    instrumental_left = _istft(instrumental_mid + side, sample_rate, length)
    instrumental_right = _istft(instrumental_mid - side, sample_rate, length)
    vocal_left = _istft(vocal_mid, sample_rate, length)
    vocal_right = vocal_left.copy()

    instrumental = np.stack([instrumental_left, instrumental_right], axis=0)
    vocals = np.stack([vocal_left, vocal_right], axis=0)

    mix_peak = float(np.max(np.abs(stereo))) or 1.0
    inst_peak = float(np.max(np.abs(instrumental))) or 1.0
    vocal_peak = float(np.max(np.abs(vocals))) or 1.0
    instrumental = instrumental * (mix_peak / inst_peak)
    vocals = vocals * min(1.0, mix_peak / vocal_peak)
    return (
        np.clip(instrumental, -1.0, 1.0).astype(np.float32),
        np.clip(vocals, -1.0, 1.0).astype(np.float32),
    )
