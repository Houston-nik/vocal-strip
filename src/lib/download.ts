export async function saveAsFile(url: string, filename: string): Promise<void> {
  const separator = url.includes("?") ? "&" : "?";
  const response = await fetch(`${url}${separator}download=1`, { cache: "no-store" });
  if (!response.ok) {
    throw new Error("Файл не скачался. Попробуй ещё раз.");
  }
  const blob = await response.blob();
  const objectUrl = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = objectUrl;
  link.download = filename;
  link.rel = "noopener";
  document.body.append(link);
  link.click();
  link.remove();
  window.setTimeout(() => URL.revokeObjectURL(objectUrl), 1500);
}

export function downloadName(originalName: string, kind: "original" | "minusovka" | "vocals"): string {
  const stem = originalName.replace(/\.[^.]+$/, "") || "track";
  switch (kind) {
    case "original":
      return originalName || "original.mp3";
    case "minusovka":
      return `${stem}-minusovka.mp3`;
    case "vocals":
      return `${stem}-vokal.mp3`;
    default: {
      const neverKind: never = kind;
      return neverKind;
    }
  }
}
