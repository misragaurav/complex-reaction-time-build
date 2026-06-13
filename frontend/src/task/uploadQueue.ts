import { API_BASE } from "../api/client";
import { runtimeApi } from "../api/runtime";
import { getAccessToken } from "../api/tokenStore";
import type { TrialIn } from "../api/types";

const BATCH_SIZE = 5;
const MAX_BATCH = 25;
const INITIAL_RETRY_MS = 1000;
const MAX_RETRY_MS = 30000;
/** §5.7: warn (non-fatal) if the unsent buffer grows past this size. */
const WARN_BUFFER_SIZE = 50;

function delay(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

/**
 * FR-34: buffers completed trials and POSTs them in batches of 5 (plus a
 * final flush at block end). On network error, retries with exponential
 * backoff (1s/2s/4s/.../30s) -- the task itself is never blocked by this.
 * Idempotent server-side upsert on `client_uuid` makes retries safe.
 */
export class TrialUploadQueue {
  private buffer: TrialIn[] = [];
  private retryDelayMs = INITIAL_RETRY_MS;
  private flushPromise: Promise<void> | null = null;
  private warned = false;

  constructor(
    private readonly sessionId: string,
    private readonly onBufferWarning?: (size: number) => void,
  ) {}

  push(trial: TrialIn): void {
    this.buffer.push(trial);
    if (this.buffer.length > WARN_BUFFER_SIZE && !this.warned) {
      this.warned = true;
      this.onBufferWarning?.(this.buffer.length);
    }
    if (this.buffer.length >= BATCH_SIZE) {
      void this.flush();
    }
  }

  /**
   * Sends everything currently buffered, retrying with backoff until the
   * server accepts it. Concurrent calls share the same in-flight attempt.
   */
  flush(): Promise<void> {
    if (!this.flushPromise) {
      this.flushPromise = this.runFlushLoop().finally(() => {
        this.flushPromise = null;
      });
    }
    return this.flushPromise;
  }

  private async runFlushLoop(): Promise<void> {
    while (this.buffer.length > 0) {
      const batch = this.buffer.slice(0, MAX_BATCH);
      try {
        await runtimeApi.submitTrials(this.sessionId, { trials: batch });
        this.buffer.splice(0, batch.length);
        this.retryDelayMs = INITIAL_RETRY_MS;
      } catch {
        await delay(this.retryDelayMs);
        this.retryDelayMs = Math.min(this.retryDelayMs * 2, MAX_RETRY_MS);
      }
    }
  }

  /**
   * Best-effort delivery on page unload. `navigator.sendBeacon` cannot carry
   * the `Authorization` header our API requires (the access token lives only
   * in memory, never in a cookie reachable by this endpoint), so this uses
   * `fetch` with `keepalive: true` instead -- see DECISIONS_TAKEN.md.
   */
  flushOnUnload(): void {
    if (this.buffer.length === 0) return;
    const token = getAccessToken();
    if (!token) return;
    const body = JSON.stringify({ trials: this.buffer });
    this.buffer = [];
    void fetch(`${API_BASE}/sessions/${this.sessionId}/trials`, {
      method: "POST",
      headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
      body,
      keepalive: true,
      credentials: "include",
    }).catch(() => {});
  }
}
