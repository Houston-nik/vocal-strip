"use client";

import { Download, Pause, Play } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { Button } from "@/components/ui/button";
import { Slider } from "@/components/ui/slider";
import { saveAsFile } from "@/lib/download";

function formatTime(seconds: number): string {
  if (!Number.isFinite(seconds) || seconds < 0) {
    return "0:00";
  }
  const whole = Math.floor(seconds);
  const mins = Math.floor(whole / 60);
  const secs = whole % 60;
  return `${mins}:${secs.toString().padStart(2, "0")}`;
}

type StemPlayerProps = {
  label: string;
  hint: string;
  src: string;
  downloadName: string;
  playing: boolean;
  onToggle: () => void;
};

export function StemPlayer({
  label,
  hint,
  src,
  downloadName,
  playing,
  onToggle,
}: StemPlayerProps) {
  const audioRef = useRef<HTMLAudioElement>(null);
  const [time, setTime] = useState(0);
  const [duration, setDuration] = useState(0);
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);

  useEffect(() => {
    const node = audioRef.current;
    if (!node) {
      return;
    }
    if (playing) {
      void node.play();
    } else {
      node.pause();
    }
  }, [playing, src]);

  async function onDownload() {
    setSaving(true);
    setSaveError(null);
    try {
      await saveAsFile(src, downloadName);
    } catch (error) {
      setSaveError(error instanceof Error ? error.message : "Не скачалось.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="rounded-2xl border border-white/10 bg-black/25 p-4">
      <audio
        ref={audioRef}
        src={src}
        preload="metadata"
        onTimeUpdate={() => setTime(audioRef.current?.currentTime ?? 0)}
        onLoadedMetadata={() => setDuration(audioRef.current?.duration ?? 0)}
        onEnded={onToggle}
      />
      <div className="flex items-start gap-3">
        <Button
          type="button"
          size="icon-lg"
          variant={playing ? "default" : "secondary"}
          className="size-11 rounded-full"
          onClick={onToggle}
          aria-label={playing ? `Пауза: ${label}` : `Слушать: ${label}`}
        >
          {playing ? <Pause /> : <Play />}
        </Button>
        <div className="min-w-0 flex-1">
          <div className="flex items-baseline justify-between gap-3">
            <p className="font-medium tracking-tight">{label}</p>
            <p className="font-mono text-xs text-muted-foreground tabular-nums">
              {formatTime(time)} / {formatTime(duration)}
            </p>
          </div>
          <p className="mt-0.5 text-xs text-muted-foreground">{hint}</p>
          <div className="mt-3" data-playing={playing ? "true" : "false"}>
            <Slider
              min={0}
              max={Math.max(duration, 0.01)}
              step={0.1}
              value={[time]}
              onValueChange={(next) => {
                const value = Array.isArray(next) ? next[0] : 0;
                const node = audioRef.current;
                if (node) {
                  node.currentTime = value;
                }
                setTime(value);
              }}
              aria-label={`Позиция: ${label}`}
            />
          </div>
          <div className="eq mt-3 flex h-6 items-end gap-0.5" data-playing={playing ? "true" : "false"} aria-hidden>
            {Array.from({ length: 18 }, (_, index) => (
              <span key={index} style={{ animationDelay: `${index * 0.05}s` }} />
            ))}
          </div>
          <Button
            type="button"
            size="sm"
            variant="secondary"
            className="mt-3"
            disabled={saving}
            onClick={() => void onDownload()}
          >
            <Download data-icon="inline-start" />
            {saving ? "Сохраняю…" : `Скачать ${label.toLowerCase()}`}
          </Button>
          {saveError ? <p className="mt-2 text-xs text-destructive">{saveError}</p> : null}
        </div>
      </div>
    </div>
  );
}
