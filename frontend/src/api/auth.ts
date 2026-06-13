import { apiRequest } from "./client";
import type {
  AccessTokenResponse,
  LoginRequest,
  ParticipantCheckRequest,
  ParticipantCheckResponse,
  ParticipantLoginRequest,
  ParticipantSetPasswordRequest,
  ParticipantTokenResponse,
  TokenResponse,
} from "./types";

export function login(payload: LoginRequest): Promise<TokenResponse> {
  return apiRequest<TokenResponse>("/auth/login", { method: "POST", body: payload, skipAuthRetry: true });
}

export function refresh(): Promise<AccessTokenResponse> {
  return apiRequest<AccessTokenResponse>("/auth/refresh", { method: "POST", skipAuthRetry: true });
}

export function logout(): Promise<void> {
  return apiRequest<void>("/auth/logout", { method: "POST", skipAuthRetry: true });
}

export function participantLogin(payload: ParticipantLoginRequest): Promise<ParticipantTokenResponse> {
  return apiRequest<ParticipantTokenResponse>("/auth/participant/login", {
    method: "POST",
    body: payload,
    skipAuthRetry: true,
  });
}

export function participantCheck(payload: ParticipantCheckRequest): Promise<ParticipantCheckResponse> {
  return apiRequest<ParticipantCheckResponse>("/auth/participant/check", {
    method: "POST",
    body: payload,
    skipAuthRetry: true,
  });
}

export function participantSetPassword(
  payload: ParticipantSetPasswordRequest,
): Promise<ParticipantTokenResponse> {
  return apiRequest<ParticipantTokenResponse>("/auth/participant/set-password", {
    method: "POST",
    body: payload,
    skipAuthRetry: true,
  });
}
