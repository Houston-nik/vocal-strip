from __future__ import annotations

import threading
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

from engine.audio_io import (
    MAX_BYTES,
    AudioError,
    extension_ok,
    load_stereo,
    probe,
    transcode_mp3,
    write_wav,
)
from engine.modes import ModeId, get_mode
from engine.spectral import separate_center_vocals

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data" / "jobs"
MODEL_DIR = ROOT / "data" / "models"


class JobState(str, Enum):
    queued = "queued"
    running = "running"
    done = "done"
    error = "error"


@dataclass
class Job:
    id: str
    filename: str
    mode: ModeId
    state: JobState = JobState.queued
    progress: float = 0.0
    stage: str = "В очереди"
    error: str | None = None
    stereo: bool = True
    duration: float = 0.0
    created_at: float = field(default_factory=time.time)
    folder: Path = field(init=False)

    def __post_init__(self) -> None:
        self.folder = DATA_DIR / self.id

    def to_public(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "id": self.id,
            "filename": self.filename,
            "mode": self.mode,
            "state": self.state.value,
            "progress": round(self.progress, 1),
            "stage": self.stage,
            "error": self.error,
            "stereo": self.stereo,
            "duration": round(self.duration, 2),
        }
        if self.state is JobState.done:
            payload["files"] = {
                "original": f"/engine/jobs/{self.id}/original",
                "instrumentalWav": f"/engine/jobs/{self.id}/instrumental.wav",
                "instrumentalMp3": f"/engine/jobs/{self.id}/instrumental.mp3",
                "vocalsWav": f"/engine/jobs/{self.id}/vocals.wav",
                "vocalsMp3": f"/engine/jobs/{self.id}/vocals.mp3",
            }
        return payload


_jobs: dict[str, Job] = {}
_lock = threading.Lock()
_work = threading.Event()
_queue: list[str] = []


def create_job(filename: str, data: bytes, mode_id: str) -> Job:
    if len(data) > MAX_BYTES:
        raise AudioError("Файл больше 80 МБ. Сожми его или возьми MP3 полегче.")
    if not extension_ok(filename):
        raise AudioError("Нужен обычный музыкальный файл: MP3, WAV, FLAC или M4A.")

    mode = get_mode(mode_id)
    job = Job(id=uuid.uuid4().hex[:12], filename=Path(filename).name, mode=mode.id)
    job.folder.mkdir(parents=True, exist_ok=True)
    source = job.folder / f"original{Path(filename).suffix.lower() or '.bin'}"
    source.write_bytes(data)

    info = probe(source)
    job.duration = float(info["duration"])
    job.stereo = bool(info["stereo"])

    with _lock:
        _jobs[job.id] = job
        _queue.append(job.id)
        _work.set()
    return job


def get_job(job_id: str) -> Job | None:
    with _lock:
        return _jobs.get(job_id)


def file_for(job: Job, kind: str) -> Path | None:
    mapping = {
        "original": _original_path(job),
        "instrumental.wav": job.folder / "instrumental.wav",
        "instrumental.mp3": job.folder / "instrumental.mp3",
        "vocals.wav": job.folder / "vocals.wav",
        "vocals.mp3": job.folder / "vocals.mp3",
    }
    path = mapping.get(kind)
    if path is None or not path.exists():
        return None
    return path


def _original_path(job: Job) -> Path:
    matches = list(job.folder.glob("original.*"))
    if not matches:
        raise FileNotFoundError(job.folder)
    return matches[0]


def _set(job: Job, **changes: Any) -> None:
    with _lock:
        for key, value in changes.items():
            setattr(job, key, value)


def _progress(job: Job, value: float, stage: str) -> None:
    _set(job, progress=max(job.progress, min(value, 99.0)), stage=stage, state=JobState.running)


def _run_job(job: Job) -> None:
    from engine.ai import ai_available, separate_with_ai

    mode = get_mode(job.mode)
    source = _original_path(job)
    MODEL_DIR.mkdir(parents=True, exist_ok=True)

    def report(value: float, stage: str) -> None:
        _progress(job, value, stage)

    report(3.0, "Читаю трек")

    try:
        if mode.engine == "ai":
            if not ai_available():
                raise AudioError(
                    "Точный режим сейчас недоступен: не установлена нейросеть. Возьми «Быстрый черновик»."
                )
            instrumental_path, vocals_path = separate_with_ai(
                source=source,
                output_dir=job.folder,
                mode=mode,
                model_dir=MODEL_DIR,
                on_progress=report,
            )
            if instrumental_path.resolve() != (job.folder / "instrumental.wav").resolve():
                write_target = job.folder / "instrumental.wav"
                if instrumental_path.suffix.lower() == ".wav":
                    instrumental_path.replace(write_target)
                else:
                    stereo, sr, _ = load_stereo(instrumental_path)
                    write_wav(write_target, stereo, sr)
            if vocals_path is not None:
                target = job.folder / "vocals.wav"
                if vocals_path.resolve() != target.resolve():
                    if vocals_path.suffix.lower() == ".wav":
                        vocals_path.replace(target)
                    else:
                        stereo, sr, _ = load_stereo(vocals_path)
                        write_wav(target, stereo, sr)
            else:
                stereo, sr, _ = load_stereo(source)
                original = stereo
                inst, sr2, _ = load_stereo(job.folder / "instrumental.wav")
                min_len = min(original.shape[1], inst.shape[1])
                vocals = original[:, :min_len] - inst[:, :min_len]
                write_wav(job.folder / "vocals.wav", vocals, sr)
        else:
            report(12.0, "Раскладываю стерео на «центр» и «края»")
            stereo, sample_rate, was_mono = load_stereo(source)
            job.stereo = not was_mono
            if was_mono:
                report(20.0, "Трек моно — голос и музыка слиты, выйдет грубее")
            report(35.0, "Ищу голос в середине и повторяющийся аккомпанемент")
            instrumental, vocals = separate_center_vocals(stereo, sample_rate)
            report(80.0, "Собираю минусовку обратно в песню")
            write_wav(job.folder / "instrumental.wav", instrumental, sample_rate)
            write_wav(job.folder / "vocals.wav", vocals, sample_rate)

        report(94.0, "Пишу MP3, чтобы файл легче скачивался")
        transcode_mp3(job.folder / "instrumental.wav", job.folder / "instrumental.mp3")
        if (job.folder / "vocals.wav").exists():
            transcode_mp3(job.folder / "vocals.wav", job.folder / "vocals.mp3")
        _set(job, state=JobState.done, progress=100.0, stage="Готово — слушай минусовку")
    except AudioError as error:
        _set(job, state=JobState.error, error=str(error), stage="Не вышло", progress=0.0)
    except Exception as error:  # noqa: BLE001 - surface any engine crash to the UI
        _set(
            job,
            state=JobState.error,
            error=f"Движок споткнулся: {error}",
            stage="Ошибка",
            progress=0.0,
        )


def _worker() -> None:
    while True:
        _work.wait(timeout=0.5)
        with _lock:
            job_id = _queue.pop(0) if _queue else None
            if not _queue:
                _work.clear()
        if job_id is None:
            continue
        job = get_job(job_id)
        if job is None:
            continue
        _set(job, state=JobState.running, stage="Начинаю", progress=1.0)
        _run_job(job)


def start_worker() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    thread = threading.Thread(target=_worker, name="minusovka-worker", daemon=True)
    thread.start()
