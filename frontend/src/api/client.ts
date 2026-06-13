import { expireSession, getAccessToken, setAccessToken } from "./tokenStore";

export const API_BASE = "/api/v1";

export type QueryParams = Record<string, string | number | boolean | undefined | null>;

export class ApiError extends Error {
  readonly status: number;
  readonly detail: unknown;

  constructor(status: number, detail: unknown) {
    super(extractMessage(detail) ?? `Request failed with status ${status}`);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
  }
}

function extractMessage(detail: unknown): string | null {
  if (typeof detail === "string") return detail;
  if (
    detail !== null &&
    typeof detail === "object" &&
    "message" in detail &&
    typeof (detail as { message: unknown }).message === "string"
  ) {
    return (detail as { message: string }).message;
  }
  return null;
}

/** Surface a human-readable message from any error, including FastAPI's
 * pydantic validation array shape (`detail: [{msg, ...}, ...]`). */
export function errorMessage(err: unknown): string {
  if (err instanceof ApiError) {
    if (Array.isArray(err.detail) && err.detail.length > 0) {
      const first = err.detail[0] as { msg?: string } | undefined;
      if (first?.msg) return first.msg;
    }
    return err.message;
  }
  if (err instanceof Error) return err.message;
  return "Something went wrong";
}

interface RequestOptions {
  method?: string;
  body?: unknown;
  query?: QueryParams;
  signal?: AbortSignal;
  /** Auth endpoints (login, refresh, logout, ...) opt out of the 401 -> refresh -> retry flow. */
  skipAuthRetry?: boolean;
}

function buildUrl(path: string, query?: QueryParams): string {
  if (!query) return `${API_BASE}${path}`;
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(query)) {
    if (value !== undefined && value !== null) {
      params.set(key, String(value));
    }
  }
  const qs = params.toString();
  return qs ? `${API_BASE}${path}?${qs}` : `${API_BASE}${path}`;
}

function rawFetch(url: string, options: RequestOptions, token: string | null): Promise<Response> {
  const headers = new Headers();
  let body: BodyInit | undefined;
  if (options.body !== undefined) {
    headers.set("Content-Type", "application/json");
    body = JSON.stringify(options.body);
  }
  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }
  return fetch(url, {
    method: options.method ?? "GET",
    headers,
    body,
    credentials: "include",
    signal: options.signal,
  });
}

let refreshPromise: Promise<string | null> | null = null;

function refreshAccessToken(): Promise<string | null> {
  if (!refreshPromise) {
    refreshPromise = fetch(`${API_BASE}/auth/refresh`, {
      method: "POST",
      credentials: "include",
    })
      .then(async (res) => {
        if (!res.ok) return null;
        const data = (await res.json()) as { access_token: string };
        return data.access_token;
      })
      .catch(() => null)
      .finally(() => {
        refreshPromise = null;
      });
  }
  return refreshPromise;
}

async function fetchWithAuth(path: string, options: RequestOptions): Promise<Response> {
  const url = buildUrl(path, options.query);
  const token = getAccessToken();
  let res = await rawFetch(url, options, token);

  if (res.status === 401 && !options.skipAuthRetry) {
    const newToken = await refreshAccessToken();
    if (newToken) {
      setAccessToken(newToken);
      res = await rawFetch(url, options, newToken);
    }
    if (res.status === 401) {
      expireSession();
    }
  }

  return res;
}

async function parseError(res: Response): Promise<never> {
  let detail: unknown = null;
  try {
    const data: unknown = await res.json();
    detail = data !== null && typeof data === "object" && "detail" in data ? (data as { detail: unknown }).detail : data;
  } catch {
    detail = res.statusText;
  }
  throw new ApiError(res.status, detail);
}

export async function apiRequest<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const res = await fetchWithAuth(path, options);
  if (!res.ok) {
    await parseError(res);
  }
  if (res.status === 204) {
    return undefined as T;
  }
  return (await res.json()) as T;
}

function parseFilename(disposition: string | null): string | null {
  if (!disposition) return null;
  const match = /filename="?([^"]+)"?/.exec(disposition);
  return match?.[1] ?? null;
}

export interface BlobResult {
  blob: Blob;
  filename: string | null;
}

export async function apiRequestBlob(path: string, options: RequestOptions = {}): Promise<BlobResult> {
  const res = await fetchWithAuth(path, options);
  if (!res.ok) {
    await parseError(res);
  }
  const blob = await res.blob();
  const filename = parseFilename(res.headers.get("Content-Disposition"));
  return { blob, filename };
}

export const api = {
  get: <T>(path: string, query?: QueryParams) => apiRequest<T>(path, { method: "GET", query }),
  post: <T>(path: string, body?: unknown) => apiRequest<T>(path, { method: "POST", body }),
  patch: <T>(path: string, body?: unknown) => apiRequest<T>(path, { method: "PATCH", body }),
  delete: <T>(path: string) => apiRequest<T>(path, { method: "DELETE" }),
};
