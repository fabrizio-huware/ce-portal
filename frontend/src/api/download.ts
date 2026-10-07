import { API_BASE } from "./client";
import { authStore } from "./authStore";
import { ApiError } from "../lib/errors";

type Params = Record<string, string | number | boolean | null | undefined>;

/** Scarica un file dall'API (serve il token: un semplice link non basterebbe). */
export async function downloadFile(path: string, params: Params = {}): Promise<string> {
  const query = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== null && value !== "") query.set(key, String(value));
  }
  const token = authStore.getToken();
  const response = await fetch(`${API_BASE}${path}?${query}`, { headers: token ? { Authorization: `Bearer ${token}` } : {} });
  if (response.status === 401) authStore.expire();
  if (!response.ok) {
    let body: unknown = null;
    try {
      body = await response.json();
    } catch {
      /* risposta non JSON */
    }
    throw new ApiError(response.status, body);
  }
  const disposition = response.headers.get("Content-Disposition") ?? "";
  const filename = /filename="([^"]+)"/.exec(disposition)?.[1] ?? "export";
  const url = URL.createObjectURL(await response.blob());
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  setTimeout(() => URL.revokeObjectURL(url), 10_000);
  return filename;
}
