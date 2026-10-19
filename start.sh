#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

WEB_PORT="${PORT:-43147}"
ENGINE_PORT="${ENGINE_PORT:-8766}"

if [ ! -x "$ROOT/.venv/bin/python" ]; then
  echo "Создаю виртуальное окружение Python..."
  python3 -m venv "$ROOT/.venv"
fi

if [ ! -d "$ROOT/node_modules" ]; then
  echo "Ставлю интерфейс..."
  npm install
fi

if ! "$ROOT/.venv/bin/python" -c "import fastapi, numpy, scipy, soundfile" >/dev/null 2>&1; then
  echo "Ставлю движок (первый раз это небыстро)..."
  "$ROOT/.venv/bin/pip" install -r "$ROOT/engine/requirements.txt"
fi

if ! command -v ffmpeg >/dev/null 2>&1; then
  echo "Нужен ffmpeg. На Mac: brew install ffmpeg. На Ubuntu: sudo apt install ffmpeg"
  exit 1
fi

cleanup() {
  if [ -n "${ENGINE_PID:-}" ] && kill -0 "$ENGINE_PID" 2>/dev/null; then
    kill "$ENGINE_PID" 2>/dev/null || true
  fi
}
trap cleanup EXIT INT TERM

echo "Запускаю движок на порту $ENGINE_PORT..."
"$ROOT/.venv/bin/uvicorn" engine.main:app --host 127.0.0.1 --port "$ENGINE_PORT" &
ENGINE_PID=$!

for _ in $(seq 1 40); do
  if "$ROOT/.venv/bin/python" -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:${ENGINE_PORT}/health')" >/dev/null 2>&1; then
    break
  fi
  sleep 0.25
done

echo "Открывай в браузере: http://127.0.0.1:${WEB_PORT}"
npm run dev -- --port "$WEB_PORT" --hostname 0.0.0.0
