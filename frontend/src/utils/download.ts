import type { BlobResult } from "../api/client";

export function downloadBlob(result: BlobResult, fallbackFilename: string): void {
  const url = URL.createObjectURL(result.blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = result.filename ?? fallbackFilename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}
