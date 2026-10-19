# vocal-strip — local vocal remover and backing-track maker (минусовка)

**English:** Upload a song, get an instrumental (minusovka) or isolated vocals in the browser. AI modes use [audio-separator](https://github.com/nomadkaraoke/python-audio-separator) with UVR ONNX models; draft mode uses a fast stereo/spectral trick without a neural net.

---

## Что это

**vocal-strip** (в коде пакет называется `minusovka`) — локальное веб-приложение: загружаешь аудиофайл, выбираешь режим, ждёшь обработку и скачиваешь результат. Музыку заново не генерирует: из **твоего** трека отделяет вокал от фонограммы.

### Режимы

| Режим | Как работает | Модель / метод |
|--------|----------------|----------------|
| **Классическая минусовка** | Убирает весь вокал, оставляет инструментал | `UVR-MDX-NET-Inst_HQ_3.onnx` через **audio-separator** |
| **Только солист** | Срезает ведущий вокал, бэк и хор часто остаются | `UVR_MDXNET_KARA_2.onnx` через **audio-separator** |
| **Быстрый черновик** | Секунды, без нейросети | Вычитание центрального вокала в стерео (STFT), см. `engine/spectral.py` |

Первый запуск AI-режимов скачивает нужную ONNX-модель (порядка десятков мегабайт) в `data/models/`. Это один раз на машину.

### Интерфейс

Одна страница (`Studio`): перетаскивание файла или выбор с диска, три карточки режимов, прогресс, встроенный прослушиватель стемов и кнопки скачивания WAV/MP3. Есть демо-трек `public/demo-pesnya.wav` для пробы без своего файла. Фронт — **Next.js 16** + React; бэкенд — **FastAPI** на `127.0.0.1:8766`, запросы идут через прокси `/engine` в `next.config.ts`.

---

## Требования

- **Python 3.10+**
- **Node.js 20+**
- **ffmpeg** (для MP3 и части форматов)

Ubuntu:

```bash
sudo apt install ffmpeg python3 python3-venv
```

macOS:

```bash
brew install ffmpeg
```

---

## Установка и запуск

В корне репозитория:

```bash
chmod +x start.sh
./start.sh
```

Скрипт создаёт `.venv`, ставит зависимости Python (`engine/requirements.txt`) и npm, поднимает движок и фронт. В терминале появится адрес, обычно **http://127.0.0.1:43147**.

Порты можно переопределить: `PORT` (веб), `ENGINE_PORT` (движок), `ENGINE_URL` (для Next при отдельном запуске).

### Раздельный запуск (разработка)

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r engine/requirements.txt
npm install

npm run dev:engine    # FastAPI на :8766
npm run dev           # Next.js на :43147
npm run test:engine   # pytest для spectral-режима
```

### Только терминал (без браузера)

```bash
source .venv/bin/activate
python -m engine путь/к/песне.mp3 -m classic
```

Флаги режима: `classic`, `lead`, `draft`. Рядом с исходником появятся `…-minusovka.wav` и MP3 (см. `engine/__main__.py`).

---

## Пример использования

1. Запусти `./start.sh`.
2. Открой http://127.0.0.1:43147.
3. Загрузи MP3/WAV/FLAC (или нажми демо).
4. Выбери **Классическая минусовка** или **Только солист** (или **Быстрый черновик** для проверки).
5. Дождись 100% и скачай **minusovka** / при необходимости **vokal**.

Поддерживаемые расширения и лимит размера задаются в `engine/audio_io.py` (загрузка через API).

---

## Структура проекта

```text
.
├── start.sh              # один скрипт «всё сразу»
├── engine/               # Python: FastAPI, jobs, AI и spectral
│   ├── main.py           # HTTP API (/health, /jobs, скачивание)
│   ├── ai.py             # audio-separator + UVR ONNX
│   ├── spectral.py       # быстрый draft без нейросети
│   ├── modes.py          # режимы и имена моделей
│   └── requirements.txt
├── src/
│   ├── app/              # Next.js App Router
│   └── components/       # Studio UI, stem-player
├── tests/                # pytest (spectral)
├── public/               # статика, demo-pesnya.wav
└── data/                 # не в git: jobs и скачанные модели
```

---

## Ограничения

- Обработка **локальная**, без облачного API: нужны CPU, место на диске и время (AI-режимы часто **1–4 минуты** на трек на обычном ПК).
- Качество зависит от записи: лучше всего **студийное стерео**; живые концерты, моно и сильное эхо даются хуже.
- **audio-separator** и модели UVR — сторонние; возможны артефакты («призрачный» вокал, глушение инструментов в центре).
- Черновик (`draft`) быстрый, но грубый: подходит для пробы, не для «чистой» минусовки.
- Используй только треки, на которые у тебя есть права.

---

## Лицензия и этика

Делай минусовки из своих записей или материала с разрешением правообладателя. Репозиторий — демонстрация для портфолио; автор не несёт ответственности за нарушение авторских прав пользователями.
