import type { Health, Job, ModeId } from "@/lib/types";

const ENGINE = "/engine";

function detailFromBody(payload: unknown, fallback: string): string {
  if (typeof payload === "object" && payload !== null && "detail" in payload) {
    const detail = (payload as { detail: unknown }).detail;
    if (typeof detail === "string" && detail.trim()) {
      return detail;
    }
  }
  return fallback;
}

async function readJson(response: Response): Promise<unknown> {
  const text = await response.text();
  if (!text) {
    return {};
  }
  try {
    return JSON.parse(text) as unknown;
  } catch {
    return { detail: text };
  }
}

export async function fetchHealth(): Promise<Health> {
  const response = await fetch(`${ENGINE}/health`, { cache: "no-store" });
  if (!response.ok) {
    throw new Error("Движок не отвечает. Запусти программу через start.sh");
  }
  return (await response.json()) as Health;
}

export async function startJob(file: File, mode: ModeId): Promise<Job> {
  const body = new FormData();
  body.append("file", file);
  body.append("mode", mode);
  const response = await fetch(`${ENGINE}/jobs`, { method: "POST", body });
  const payload = await readJson(response);
  if (!response.ok) {
    throw new Error(detailFromBody(payload, "Не получилось принять файл."));
  }
  return payload as Job;
}

export async function pollJob(id: string): Promise<Job> {
  const response = await fetch(`${ENGINE}/jobs/${id}`, { cache: "no-store" });
  const payload = await readJson(response);
  if (!response.ok) {
    throw new Error(detailFromBody(payload, "Задача потерялась. Залей трек ещё раз."));
  }
  return payload as Job;
}

export function engineUrl(path: string): string {
  return path.startsWith("/engine") ? path : `${ENGINE}${path}`;
}
