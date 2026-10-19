export type ModeId = "classic" | "lead" | "draft";
export type JobState = "queued" | "running" | "done" | "error";
export type EnginePulse = "connecting" | "up" | "down";

export type ModeInfo = {
  id: ModeId;
  title: string;
  subtitle: string;
  engine: "ai" | "spectral";
  estimated: string;
  needsAi: boolean;
};

export type Health = {
  ok: boolean;
  aiReady: boolean;
  modes: ModeInfo[];
};

export type JobFiles = {
  original: string;
  instrumentalWav: string;
  instrumentalMp3: string;
  vocalsWav: string;
  vocalsMp3: string;
};

export type Job = {
  id: string;
  filename: string;
  mode: ModeId;
  state: JobState;
  progress: number;
  stage: string;
  error: string | null;
  stereo: boolean;
  duration: number;
  files?: JobFiles;
};

export function isModeId(value: string): value is ModeId {
  return value === "classic" || value === "lead" || value === "draft";
}

export function modeCopy(mode: ModeId): { title: string; hint: string } {
  switch (mode) {
    case "classic":
      return {
        title: "Классическая минусовка",
        hint: "Убирает весь вокал, оставляет оригинальную музыку",
      };
    case "lead":
      return {
        title: "Только солист",
        hint: "Срезает ведущий вокал, бэк-вокал остаётся",
      };
    case "draft":
      return {
        title: "Быстрый черновик",
        hint: "Без нейросети, за несколько секунд",
      };
    default: {
      const neverMode: never = mode;
      return neverMode;
    }
  }
}

export function enginePulseCopy(pulse: EnginePulse): { label: string; dotClass: string } {
  switch (pulse) {
    case "connecting":
      return { label: "Подключаюсь…", dotClass: "bg-amber-400" };
    case "up":
      return { label: "Движок слушает", dotClass: "bg-emerald-400" };
    case "down":
      return { label: "Движок спит", dotClass: "bg-red-400" };
    default: {
      const neverPulse: never = pulse;
      return neverPulse;
    }
  }
}

export function jobStateLabel(state: JobState): string {
  switch (state) {
    case "queued":
      return "В очереди";
    case "running":
      return "Работаю";
    case "done":
      return "Готово";
    case "error":
      return "Ошибка";
    default: {
      const neverState: never = state;
      return neverState;
    }
  }
}
