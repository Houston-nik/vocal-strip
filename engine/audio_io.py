from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import numpy as np

ALLOWED_EXTENSIONS = {".mp3", ".wav", ".flac", ".m4a", ".ogg", ".aac", ".aiff", ".aif", ".wma"}
MAX_DURATION_SECONDS = 15 * 60
MAX_BYTES = 80 * 1024 * 1024
TARGET_SR = 44100


class AudioError(ValueError):
    """User-facing audio problem."""


def require_ffmpeg() -> str:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise AudioError("Не найден ffmpeg. Поставь его и запусти программу снова.")
    return ffmpeg


def require_ffprobe() -> str:
    ffprobe = shutil.which("ffprobe")
    if not ffprobe:
        raise AudioError("Не найден ffprobe (идёт вместе с ffmpeg).")
    return ffprobe


def extension_ok(name: str) -> bool:
    return Path(name).suffix.lower() in ALLOWED_EXTENSIONS


def probe(path: Path) -> dict[str, float | int | bool]:
    ffprobe = require_ffprobe()
    command = [
        ffprobe,
        "-v",
        "error",
        "-show_entries",
        "format=duration,size:stream=channels,sample_rate,codec_type",
        "-of",
        "json",
        str(path),
    ]
    try:
        raw = subprocess.check_output(command, stderr=subprocess.STDOUT, text=True)
    except subprocess.CalledProcessError as error:
        raise AudioError("Это не похоже на музыкальный файл. Попробуй MP3, WAV или FLAC.") from error

    data = json.loads(raw)
    duration = float((data.get("format") or {}).get("duration") or 0)
    audio_streams = [
        stream
        for stream in data.get("streams") or []
        if stream.get("codec_type") == "audio"
    ]
    if not audio_streams or duration <= 0:
        raise AudioError("В файле нет звука, который можно разобрать.")
    if duration > MAX_DURATION_SECONDS:
        minutes = MAX_DURATION_SECONDS // 60
        raise AudioError(f"Трек длиннее {minutes} минут — такой пока не тянем, разрежь его короче.")

    channels = int(audio_streams[0].get("channels") or 1)
    sample_rate = int(audio_streams[0].get("sample_rate") or TARGET_SR)
    return {
        "duration": duration,
        "channels": channels,
        "sampleRate": sample_rate,
        "stereo": channels >= 2,
    }


def load_stereo(path: Path, sample_rate: int = TARGET_SR) -> tuple[np.ndarray, int, bool]:
    """Return float32 array shaped (2, samples), sample rate, and whether source was mono."""
    ffmpeg = require_ffmpeg()
    command = [
        ffmpeg,
        "-nostdin",
        "-i",
        str(path),
        "-ac",
        "2",
        "-ar",
        str(sample_rate),
        "-f",
        "f32le",
        "-acodec",
        "pcm_f32le",
        "-v",
        "error",
        "pipe:1",
    ]
    try:
        raw = subprocess.check_output(command, stderr=subprocess.STDOUT)
    except subprocess.CalledProcessError as error:
        raise AudioError("Не получилось прочитать трек. Попробуй другой формат, например WAV.") from error

    audio = np.frombuffer(raw, dtype=np.float32)
    if audio.size < 2:
        raise AudioError("Файл слишком короткий или пустой.")
    frames = audio.reshape(-1, 2).T.copy()
    info = probe(path)
    was_mono = not bool(info["stereo"])
    peak = float(np.max(np.abs(frames)))
    if peak > 1e-6:
        frames = np.clip(frames / max(peak, 1.0), -1.0, 1.0)
    return frames, sample_rate, was_mono


def write_wav(path: Path, stereo: np.ndarray, sample_rate: int = TARGET_SR) -> None:
    import soundfile as sf

    path.parent.mkdir(parents=True, exist_ok=True)
    audio = np.clip(np.asarray(stereo, dtype=np.float32), -1.0, 1.0)
    if audio.ndim != 2 or audio.shape[0] != 2:
        raise AudioError("Внутренняя ошибка: ожидался стерео-звук.")
    sf.write(str(path), audio.T, sample_rate, subtype="PCM_16")


def transcode_mp3(wav_path: Path, mp3_path: Path) -> None:
    ffmpeg = require_ffmpeg()
    command = [
        ffmpeg,
        "-y",
        "-nostdin",
        "-i",
        str(wav_path),
        "-codec:a",
        "libmp3lame",
        "-q:a",
        "2",
        "-v",
        "error",
        str(mp3_path),
    ]
    try:
        subprocess.check_call(command, stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
    except subprocess.CalledProcessError as error:
        raise AudioError("Не получилось сохранить MP3.") from error
