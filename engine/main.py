from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path
from threading import Thread

from fastapi import FastAPI, File, Form, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel

from engine.ai import ai_available
from engine.audio_io import AudioError
from engine.jobs import create_job, file_for, get_job, start_worker
from engine.modes import public_modes

DOWNLOAD_NAMES = {
    "original": "original",
    "instrumental.wav": "minusovka.wav",
    "instrumental.mp3": "minusovka.mp3",
    "vocals.wav": "vokal.wav",
    "vocals.mp3": "vokal.mp3",
}


class HealthResponse(BaseModel):
    ok: bool
    aiReady: bool
    modes: list[dict]


@asynccontextmanager
async def lifespan(_app: FastAPI):
    start_worker()

    def _warmup() -> None:
        try:
            from engine.ai import warmup
            from engine.jobs import MODEL_DIR
            from engine.modes import MODES

            if ai_available():
                warmup(MODES["classic"].model_filename or "", MODEL_DIR)
        except Exception:
            return

    Thread(target=_warmup, name="minusovka-warmup", daemon=True).start()
    yield


app = FastAPI(title="Минусовка", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(ok=True, aiReady=ai_available(), modes=public_modes())


@app.post("/jobs")
async def start_job(file: UploadFile = File(...), mode: str = Form("classic")):
    data = await file.read()
    filename = file.filename or "track.mp3"
    try:
        job = create_job(filename, data, mode)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    except AudioError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    return job.to_public()


@app.get("/jobs/{job_id}")
def job_status(job_id: str):
    job = get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Задача уже исчезла. Залей трек ещё раз.")
    return job.to_public()


@app.get("/jobs/{job_id}/{kind}")
def job_file(job_id: str, kind: str, download: bool = Query(default=False)):
    job = get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Файл не найден.")
    path = file_for(job, kind)
    if path is None:
        raise HTTPException(status_code=404, detail="Этот файл ещё не готов.")
    download_name = _download_name(job.filename, kind)
    media = "application/octet-stream" if download else _media_type(path)
    return FileResponse(
        path,
        media_type=media,
        filename=download_name,
        content_disposition_type="attachment" if download else "inline",
    )


def _download_name(original: str, kind: str) -> str:
    stem = Path(original).stem or "track"
    suffix = DOWNLOAD_NAMES.get(kind, kind)
    if kind == "original":
        return original
    return f"{stem}-{suffix}"


def _media_type(path: Path) -> str:
    mapping = {
        ".mp3": "audio/mpeg",
        ".wav": "audio/wav",
        ".flac": "audio/flac",
        ".m4a": "audio/mp4",
        ".ogg": "audio/ogg",
    }
    return mapping.get(path.suffix.lower(), "application/octet-stream")
