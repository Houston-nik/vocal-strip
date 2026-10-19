from __future__ import annotations

import numpy as np

from engine.spectral import separate_center_vocals


def _tone(freq: float, seconds: float, sr: int, pan: str) -> np.ndarray:
    t = np.arange(int(seconds * sr), dtype=np.float32) / sr
    wave = (0.35 * np.sin(2 * np.pi * freq * t)).astype(np.float32)
    if pan == "center":
        return np.stack([wave, wave], axis=0)
    if pan == "left":
        return np.stack([wave, np.zeros_like(wave)], axis=0)
    return np.stack([np.zeros_like(wave), wave], axis=0)


def _band_energy(stereo: np.ndarray, sr: int, freq: float) -> float:
    mix = stereo.mean(axis=0)
    window = np.hanning(mix.size).astype(np.float32)
    spectrum = np.fft.rfft(mix * window)
    freqs = np.fft.rfftfreq(mix.size, d=1.0 / sr)
    band = (freqs > freq * 0.92) & (freqs < freq * 1.08)
    return float(np.sum(np.abs(spectrum[band]) ** 2))


def test_center_voice_is_removed_side_instruments_stay() -> None:
    sr = 44100
    vocal = _tone(880, 1.2, sr, "center")
    guitar = _tone(220, 1.2, sr, "left")
    keys = _tone(330, 1.2, sr, "right")
    mix = np.clip(vocal + guitar + keys, -1.0, 1.0)

    instrumental, vocals = separate_center_vocals(mix, sr)

    assert _band_energy(instrumental, sr, 880) < 0.25 * _band_energy(mix, sr, 880)
    assert _band_energy(vocals, sr, 880) > 0.4 * _band_energy(mix, sr, 880)
    assert _band_energy(instrumental, sr, 220) > 0.45 * _band_energy(mix, sr, 220)
    assert _band_energy(instrumental, sr, 330) > 0.45 * _band_energy(mix, sr, 330)


def test_output_shape_matches_input() -> None:
    sr = 44100
    mix = _tone(440, 0.4, sr, "center") + _tone(110, 0.4, sr, "left")
    instrumental, vocals = separate_center_vocals(mix, sr)
    assert instrumental.shape == mix.shape
    assert vocals.shape == mix.shape
    assert float(np.max(np.abs(instrumental))) > 0
    assert float(np.max(np.abs(vocals))) > 0
