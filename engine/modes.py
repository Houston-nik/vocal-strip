from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

ModeId = Literal["classic", "lead", "draft"]


@dataclass(frozen=True)
class Mode:
    id: ModeId
    title: str
    subtitle: str
    engine: Literal["ai", "spectral"]
    model_filename: str | None
    estimated: str


MODES: dict[ModeId, Mode] = {
    "classic": Mode(
        id="classic",
        title="Классическая минусовка",
        subtitle="Убирает весь вокал, оставляет оригинальную музыку",
        engine="ai",
        model_filename="UVR-MDX-NET-Inst_HQ_3.onnx",
        estimated="обычно 1–4 минуты на трек",
    ),
    "lead": Mode(
        id="lead",
        title="Только солист",
        subtitle="Срезает ведущий вокал, бэк-вокал и хор остаются",
        engine="ai",
        model_filename="UVR_MDXNET_KARA_2.onnx",
        estimated="обычно 1–3 минуты на трек",
    ),
    "draft": Mode(
        id="draft",
        title="Быстрый черновик",
        subtitle="Без нейросети: вычитает голос из центра стерео",
        engine="spectral",
        model_filename=None,
        estimated="несколько секунд",
    ),
}


def get_mode(mode_id: str) -> Mode:
    if mode_id not in MODES:
        allowed = ", ".join(MODES)
        raise ValueError(f"Неизвестный режим «{mode_id}». Доступны: {allowed}")
    return MODES[mode_id]


def public_modes() -> list[dict[str, str | bool]]:
    return [
        {
            "id": mode.id,
            "title": mode.title,
            "subtitle": mode.subtitle,
            "engine": mode.engine,
            "estimated": mode.estimated,
            "needsAi": mode.engine == "ai",
        }
        for mode in MODES.values()
    ]
