from __future__ import annotations

import argparse
from pathlib import Path

from engine.audio_io import AudioError, load_stereo, transcode_mp3, write_wav
from engine.modes import MODES, get_mode
from engine.spectral import separate_center_vocals


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Сделать минусовку из песни: оригинальная музыка без ведущего вокала."
    )
    parser.add_argument("input", help="Путь к MP3/WAV/FLAC")
    parser.add_argument(
        "-m",
        "--mode",
        choices=list(MODES),
        default="classic",
        help="classic — вся минусовка, lead — только солист, draft — быстро без нейросети",
    )
    parser.add_argument("-o", "--output", help="Куда сохранить WAV минусовки")
    args = parser.parse_args()

    source = Path(args.input).expanduser().resolve()
    if not source.exists():
        raise SystemExit(f"Нет файла: {source}")

    mode = get_mode(args.mode)
    output = Path(args.output).expanduser() if args.output else source.with_name(f"{source.stem}-minusovka.wav")

    try:
        if mode.engine == "spectral":
            stereo, sample_rate, _ = load_stereo(source)
            instrumental, vocals = separate_center_vocals(stereo, sample_rate)
            write_wav(output, instrumental, sample_rate)
            vocals_path = output.with_name(output.stem.replace("minusovka", "vokal") + output.suffix)
            if vocals_path == output:
                vocals_path = output.with_name(f"{output.stem}-vokal.wav")
            write_wav(vocals_path, vocals, sample_rate)
        else:
            from engine.ai import ai_available, separate_with_ai
            from engine.jobs import MODEL_DIR

            if not ai_available():
                raise AudioError("Нейросеть не установлена. Запусти: pip install -r engine/requirements.txt")

            folder = output.parent
            folder.mkdir(parents=True, exist_ok=True)

            def report(value: float, stage: str) -> None:
                print(f"{value:5.1f}%  {stage}")

            instrumental, vocals = separate_with_ai(
                source=source,
                output_dir=folder,
                mode=mode,
                model_dir=MODEL_DIR,
                on_progress=report,
            )
            if instrumental != output:
                instrumental.replace(output)
            if vocals is not None:
                vocals_target = output.with_name(f"{source.stem}-vokal.wav")
                vocals.replace(vocals_target)
        mp3 = output.with_suffix(".mp3")
        transcode_mp3(output, mp3)
        print(f"Готово: {output}")
        print(f"И MP3:  {mp3}")
    except AudioError as error:
        raise SystemExit(str(error)) from error


if __name__ == "__main__":
    main()
