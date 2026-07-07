/**
 * Typed fetch wrappers for all backend API endpoints.
 */
import type { JobStatusResponse, UploadResponse } from "./schema";

const API_BASE =
  process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export async function uploadDrawing(file: File): Promise<UploadResponse> {
  const form = new FormData();
  form.append("file", file);

  const res = await fetch(`${API_BASE}/api/upload`, {
    method: "POST",
    body: form,
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: "Upload failed" }));
    throw new Error(err.detail || `Upload failed: ${res.status}`);
  }

  return res.json();
}

export async function fetchJobStatus(jobId: string): Promise<JobStatusResponse> {
  const res = await fetch(`${API_BASE}/api/mto/${jobId}`);

  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: "Fetch failed" }));
    throw new Error(err.detail || `Status fetch failed: ${res.status}`);
  }

  return res.json();
}

export function getCSVUrl(jobId: string): string {
  return `${API_BASE}/api/mto/${jobId}/csv`;
}

export function getXLSXUrl(jobId: string): string {
  return `${API_BASE}/api/mto/${jobId}/xlsx`;
}

export async function checkHealth(): Promise<boolean> {
  try {
    const res = await fetch(`${API_BASE}/api/health`, { cache: "no-store" });
    return res.ok;
  } catch {
    return false;
  }
}
