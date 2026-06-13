// In-memory access token (never persisted) plus a session-expiry hook so
// AuthContext can react when client.ts gives up on refreshing.
let accessToken: string | null = null;
let onExpire: (() => void) | null = null;

export function getAccessToken(): string | null {
  return accessToken;
}

export function setAccessToken(token: string | null): void {
  accessToken = token;
}

export function onSessionExpire(handler: (() => void) | null): void {
  onExpire = handler;
}

export function expireSession(): void {
  accessToken = null;
  onExpire?.();
}
