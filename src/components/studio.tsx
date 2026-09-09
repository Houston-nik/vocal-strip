"use client";

import {
  AlertCircle,
  Disc3,
  Download,
  Mic2,
  Music2,
  RotateCcw,
  Sparkles,
  Upload,
  Zap,
} from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState, type DragEvent } from "react";

import { StemPlayer } from "@/components/stem-player";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { engineUrl, fetchHealth, pollJob, startJob } from "@/lib/api";
import { isModeId, modeCopy, type Health, type Job, type ModeId } from "@/lib/types";

const ACCEPT = ".mp3,.wav,.flac,.m4a,.ogg,.aac,.aiff,.aif";

const FALLBACK_MODES: Health["modes"] = [
  {
    id: "classic",
    title: "Классическая минусовка",
    subtitle: "Убирает весь вокал, оставляет оригинальную музыку",
    engine: "ai",
    estimated: "обычно 1–4 минуты на трек",
    needsAi: true,
  },
  {
    id: "lead",
    title: "Только солист",
    subtitle: "Срезает ведущий вокал, бэк-вокал и хор остаются",
    engine: "ai",
    estimated: "обычно 1–3 минуты на трек",
    needsAi: true,
  },
  {
    id: "draft",
    title: "Быстрый черновик",
    subtitle: "Без нейросети: вычитает голос из центра стерео",
    engine: "spectral",
    estimated: "несколько секунд",
    needsAi: false,
  },
];

const MODE_ICONS: Record<ModeId, typeof Sparkles> = {
  classic: Sparkles,
  lead: Mic2,
  draft: Zap,
};

function fileSizeLabel(bytes: number): string {
  if (bytes < 1024 * 1024) {
    return `${Math.max(1, Math.round(bytes / 1024))} КБ`;
  }
  return `${(bytes / (1024 * 1024)).toFixed(1)} МБ`;
}

function extractError(error: unknown): string {
  if (error instanceof Error && error.message) {
    return error.message;
  }
  return "Что-то пошло не так. Попробуй ещё раз.";
}

export function Studio() {
  const inputRef = useRef<HTMLInputElement>(null);
  const [health, setHealth] = useState<Health | null>(null);
  const [engineError, setEngineError] = useState<string | null>(null);
  const [file, setFile] = useState<File | null>(null);
  const [mode, setMode] = useState<ModeId>("classic");
  const [job, setJob] = useState<Job | null>(null);
  const [busy, setBusy] = useState(false);
  const [localError, setLocalError] = useState<string | null>(null);
  const [dragOver, setDragOver] = useState(false);
  const [playing, setPlaying] = useState<"original" | "instrumental" | "vocals" | null>(null);

  useEffect(() => {
    let cancelled = false;
    const loadHealth = async () => {
      try {
        const next = await fetchHealth();
        if (cancelled) {
          return;
        }
        setHealth(next);
        setEngineError(null);
      } catch (error) {
        if (!cancelled) {
          setEngineError(extractError(error));
        }
      }
    };
    void loadHealth();
    const timer = window.setInterval(() => {
      void loadHealth();
    }, 8000);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, []);

  const jobId = job?.id;
  const jobState = job?.state;

  useEffect(() => {
    if (!jobId || (jobState !== "queued" && jobState !== "running")) {
      return;
    }
    let cancelled = false;
    const tick = async () => {
      try {
        const next = await pollJob(jobId);
        if (!cancelled) {
          setJob(next);
        }
      } catch (error) {
        if (!cancelled) {
          setLocalError(extractError(error));
        }
      }
    };
    const timer = window.setInterval(() => {
      void tick();
    }, 900);
    void tick();
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, [jobId, jobState]);

  const takeFile = useCallback((next: File | undefined) => {
    if (!next) {
      return;
    }
    setFile(next);
    setJob(null);
    setPlaying(null);
    setLocalError(null);
  }, []);

  const onDrop = useCallback(
    (event: DragEvent<HTMLElement>) => {
      event.preventDefault();
      setDragOver(false);
      takeFile(event.dataTransfer.files[0]);
    },
    [takeFile],
  );

  const selectedModeLocked = Boolean(job && (job.state === "queued" || job.state === "running"));
  const canRun = Boolean(file) && !busy && !selectedModeLocked && !engineError;
  const activeMode: ModeId = health && !health.aiReady ? "draft" : mode;

  async function onCreate() {
    if (!file) {
      setLocalError("Сначала кинь сюда песню.");
      return;
    }
    setBusy(true);
    setLocalError(null);
    setPlaying(null);
    try {
      const created = await startJob(file, activeMode);
      setJob(created);
    } catch (error) {
      setLocalError(extractError(error));
    } finally {
      setBusy(false);
    }
  }

  function reset() {
    setFile(null);
    setJob(null);
    setPlaying(null);
    setLocalError(null);
    if (inputRef.current) {
      inputRef.current.value = "";
    }
  }

  const modes = health?.modes?.length ? health.modes : FALLBACK_MODES;
  const files = job?.files;
  const warning = useMemo(() => {
    if (job?.state === "done" && !job.stereo) {
      return "Этот трек был моно. Голос и музыка сидели в одном месте, поэтому минусовка может быть грубее.";
    }
    return null;
  }, [job]);

  return (
    <div className="relative mx-auto flex w-full max-w-5xl flex-1 flex-col gap-8 px-4 py-8 sm:px-6 sm:py-12">
      <header className="flex flex-col gap-5 sm:flex-row sm:items-end sm:justify-between">
        <div className="space-y-3">
          <Badge variant="outline" className="border-amber-400/30 bg-amber-400/10 text-amber-200">
            Своя студия минусовок
          </Badge>
          <h1 className="font-heading text-4xl leading-[1.05] tracking-tight text-balance sm:text-5xl">
            Оригинальная фонограмма
            <span className="block text-amber-300">без ведущего вокала</span>
          </h1>
          <p className="max-w-xl text-base text-muted-foreground sm:text-lg">
            Кидаешь целую песню — получаешь ту же музыку, только солиста уже нет. Не
            «новая аранжировка», а вынутый голос из твоего файла.
          </p>
        </div>
        <div className="flex items-center gap-3 text-sm text-muted-foreground">
          <span className={`size-2.5 rounded-full ${health?.ok ? "bg-emerald-400" : "bg-red-400"}`} />
          {health?.ok ? "Движок слушает" : "Движок спит"}
        </div>
      </header>

      {engineError ? (
        <Card className="border-destructive/40 bg-destructive/10">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <AlertCircle className="size-4" />
              Сейчас обработать песню нельзя
            </CardTitle>
            <CardDescription className="text-destructive/90">{engineError}</CardDescription>
          </CardHeader>
        </Card>
      ) : null}

      <section
        onDragOver={(event) => {
          event.preventDefault();
          setDragOver(true);
        }}
        onDragLeave={() => setDragOver(false)}
        onDrop={onDrop}
        className={`vinyl relative overflow-hidden rounded-3xl border px-5 py-10 text-center transition sm:px-10 ${
          dragOver ? "border-amber-300 bg-amber-300/10" : "border-white/10 bg-black/20"
        }`}
      >
        <input
          ref={inputRef}
          type="file"
          accept={ACCEPT}
          className="sr-only"
          onChange={(event) => takeFile(event.target.files?.[0])}
        />
        <Disc3 className="mx-auto size-12 text-amber-300" />
        <h2 className="mt-4 font-heading text-2xl tracking-tight">Брось трек сюда</h2>
        <p className="mx-auto mt-2 max-w-md text-sm text-muted-foreground">
          MP3, WAV, FLAC или M4A. Лучше стерео — так программе проще понять, где голос.
        </p>
        <div className="mt-6 flex flex-col items-center justify-center gap-3 sm:flex-row">
          <Button type="button" size="lg" onClick={() => inputRef.current?.click()}>
            <Upload data-icon="inline-start" />
            Выбрать файл
          </Button>
          {file ? (
            <p className="text-sm text-amber-100">
              {file.name} · {fileSizeLabel(file.size)}
            </p>
          ) : (
            <p className="text-sm text-muted-foreground">или перетащи мышкой</p>
          )}
        </div>
      </section>

      <section className="grid gap-3 md:grid-cols-3">
        {modes.map((item) => {
          const id = item.id;
          if (!isModeId(id)) {
            return null;
          }
          const Icon = MODE_ICONS[id];
          const copy = modeCopy(id);
          const disabled = item.needsAi && !health?.aiReady;
          const active = activeMode === id;
          return (
            <button
              key={id}
              type="button"
              disabled={disabled || selectedModeLocked}
              onClick={() => setMode(id)}
              className={`rounded-2xl border p-4 text-left transition ${
                active
                  ? "border-amber-300 bg-amber-300/10"
                  : "border-white/10 bg-black/20 hover:border-white/25"
              } disabled:opacity-40`}
            >
              <Icon className="size-5 text-amber-300" />
              <p className="mt-3 font-medium">{copy.title}</p>
              <p className="mt-1 text-sm text-muted-foreground">{copy.hint}</p>
              <p className="mt-3 text-xs text-amber-200/80">{item.estimated}</p>
              {disabled ? (
                <p className="mt-2 text-xs text-destructive">Нейросеть ещё не установлена</p>
              ) : null}
            </button>
          );
        })}
      </section>

      <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
        <Button type="button" size="lg" disabled={!canRun} onClick={() => void onCreate()}>
          <Music2 data-icon="inline-start" />
          Сделать минусовку
        </Button>
        <Button type="button" size="lg" variant="ghost" onClick={reset}>
          <RotateCcw data-icon="inline-start" />
          Другой трек
        </Button>
      </div>

      {localError || job?.error ? (
        <Card className="border-destructive/40 bg-destructive/10">
          <CardContent className="flex items-start gap-3 pt-6">
            <AlertCircle className="mt-0.5 size-4 shrink-0" />
            <p>{localError || job?.error}</p>
          </CardContent>
        </Card>
      ) : null}

      {job && (job.state === "queued" || job.state === "running") ? (
        <Card>
          <CardHeader>
            <CardTitle>Снимаю голос с «{job.filename}»</CardTitle>
            <CardDescription>{job.stage}</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            <Progress value={job.progress}>
              <span className="text-sm text-muted-foreground">{Math.round(job.progress)}%</span>
            </Progress>
            <p className="text-sm text-muted-foreground">
              Точный режим думает минуту-другую: это нормально. Не закрывай вкладку.
            </p>
          </CardContent>
        </Card>
      ) : null}

      {job?.state === "done" && files ? (
        <section className="space-y-4">
          <div className="flex flex-wrap items-end justify-between gap-3">
            <div>
              <h2 className="font-heading text-2xl tracking-tight">Слушай, что получилось</h2>
              <p className="text-sm text-muted-foreground">
                Слева направо: оригинал, минусовка, снятый голос. Если в минусовке ещё слышен
                солист — попробуй другой режим.
              </p>
            </div>
            <div className="flex flex-wrap gap-2">
              <Button render={<a href={engineUrl(files.instrumentalMp3)} download />}>
                <Download data-icon="inline-start" />
                Минусовка MP3
              </Button>
              <Button variant="outline" render={<a href={engineUrl(files.instrumentalWav)} download />}>
                WAV без сжатия
              </Button>
            </div>
          </div>
          {warning ? (
            <p className="rounded-xl border border-amber-300/20 bg-amber-300/10 px-4 py-3 text-sm text-amber-100">
              {warning}
            </p>
          ) : null}
          <div className="grid gap-3 lg:grid-cols-3">
            <StemPlayer
              label="Оригинал"
              hint="Как было"
              src={engineUrl(files.original)}
              playing={playing === "original"}
              onToggle={() => setPlaying((current) => (current === "original" ? null : "original"))}
            />
            <StemPlayer
              label="Минусовка"
              hint="Музыка без солиста"
              src={engineUrl(files.instrumentalMp3)}
              playing={playing === "instrumental"}
              onToggle={() =>
                setPlaying((current) => (current === "instrumental" ? null : "instrumental"))
              }
            />
            <StemPlayer
              label="Снятый голос"
              hint="Чтобы проверить, что именно убрали"
              src={engineUrl(files.vocalsMp3)}
              playing={playing === "vocals"}
              onToggle={() => setPlaying((current) => (current === "vocals" ? null : "vocals"))}
            />
          </div>
          <div className="flex flex-wrap gap-2">
            <Button variant="secondary" render={<a href={engineUrl(files.vocalsMp3)} download />}>
              Скачать голос MP3
            </Button>
            <Button variant="ghost" render={<a href={engineUrl(files.vocalsWav)} download />}>
              Голос WAV
            </Button>
          </div>
        </section>
      ) : null}

      <section className="grid gap-4 border-t border-white/10 pt-8 text-sm text-muted-foreground md:grid-cols-3">
        <div>
          <p className="font-medium text-foreground">Как это работает</p>
          <p className="mt-2">
            Программа не пишет новую музыку. Она слушает твой файл и вытаскивает из него
            голос, оставляя исходную фонограмму.
          </p>
        </div>
        <div>
          <p className="font-medium text-foreground">Что лучше закидывать</p>
          <p className="mt-2">
            Обычные студийные песни в стерео. Живые концерты, моно и сильный реверб даются
            труднее — тогда бери «Только солист» или черновик.
          </p>
        </div>
        <div>
          <p className="font-medium text-foreground">Про права</p>
          <p className="mt-2">
            Делай минусовки из своих записей или треков, на которые у тебя есть право. Чужие
            песни без разрешения в интернет лучше не выкладывать.
          </p>
        </div>
      </section>
    </div>
  );
}
