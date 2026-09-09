from __future__ import annotations

import logging
import re
import threading
from pathlib import Path
from typing import Callable

from engine.modes import Mode

ProgressCallback = Callable[[float, str], None]

_LOGGER = logging.getLogger("minusovka.ai")
_PERCENT = re.compile(r"(?:progress|Progress|%+)\s*[:=]?\s*(\d{1,3}(?:\.\d+)?)%?", re.IGNORECASE)

_separator = None
_loaded_model: str | None = None
_lock = threading.Lock()


class _ProgressLogHandler(logging.Handler):
    def __init__(self, callback: ProgressCallback) -> None:
        super().__init__(level=logging.INFO)
        self.callback = callback

    def emit(self, record: logging.LogRecord) -> None:
        message = record.getMessage()
        match = _PERCENT.search(message)
        if match:
            value = min(99.0, max(1.0, float(match.group(1))))
            self.callback(15.0 + value * 0.75, "Нейросеть аккуратно снимает голос с музыки")
            return
        lowered = message.lower()
        if "download" in lowered:
            self.callback(8.0, "Скачиваю модель — это один раз, потом будет быстрее")
        elif "load" in lowered:
            self.callback(12.0, "Загружаю модель в память")


def ai_available() -> bool:
    try:
        import audio_separator.separator  # noqa: F401

        return True
    except ImportError:
        return False


def _build_separator(output_dir: Path, model_dir: Path):
    from audio_separator.separator import Separator

    return Separator(
        log_level=logging.INFO,
        model_file_dir=str(model_dir),
        output_dir=str(output_dir),
        output_format="WAV",
        sample_rate=44100,
        normalization_threshold=0.9,
        mdx_params={
            "hop_length": 1024,
            "segment_size": 256,
            "overlap": 0.25,
            "batch_size": 1,
            "enable_denoise": False,
        },
    )


def separate_with_ai(
    source: Path,
    output_dir: Path,
    mode: Mode,
    model_dir: Path,
    on_progress: ProgressCallback,
) -> tuple[Path, Path | None]:
    if mode.model_filename is None:
        raise RuntimeError("У этого режима нет нейросети.")

    handler = _ProgressLogHandler(on_progress)
    logging.getLogger().addHandler(handler)
    try:
        on_progress(6.0, "Готовлю точную модель отделения вокала")
        with _lock:
            global _separator, _loaded_model
            if _separator is None:
                _separator = _build_separator(output_dir, model_dir)
            else:
                _separator.output_dir = str(output_dir)
                output_dir.mkdir(parents=True, exist_ok=True)
            if _loaded_model != mode.model_filename:
                on_progress(10.0, f"Загружаю {mode.model_filename}")
                _separator.load_model(model_filename=mode.model_filename)
                _loaded_model = mode.model_filename

            on_progress(18.0, "Слушаю трек и отделяю солиста от фонограммы")
            output_names = {
                "Instrumental": "instrumental",
                "Vocals": "vocals",
            }
            written = _separator.separate(str(source), output_names)

        files = [Path(item) for item in written]
        instrumental = _pick_stem(files, "instrumental", output_dir)
        vocals = _pick_stem(files, "vocals", output_dir, required=False)
        if instrumental is None:
            raise RuntimeError("Модель не вернула минусовку. Попробуй другой режим.")
        on_progress(92.0, "Сохраняю чистую фонограмму")
        return instrumental, vocals
    finally:
        logging.getLogger().removeHandler(handler)


def _pick_stem(files: list[Path], key: str, output_dir: Path, required: bool = True) -> Path | None:
    lowered = key.lower()
    for item in files:
        if lowered in item.stem.lower():
            return item
    matches = list(output_dir.glob(f"*{key}*"))
    if matches:
        return matches[0]
    if required:
        return None
    return None


def warmup(model_filename: str, model_dir: Path) -> None:
    if not ai_available():
        return
    dummy = Path("/tmp/minusovka-warmup")
    dummy.mkdir(parents=True, exist_ok=True)
    with _lock:
        global _separator, _loaded_model
        if _separator is None:
            _separator = _build_separator(dummy, model_dir)
        if _loaded_model != model_filename:
            _LOGGER.info("Warming model %s", model_filename)
            _separator.load_model(model_filename=model_filename)
            _loaded_model = model_filename
