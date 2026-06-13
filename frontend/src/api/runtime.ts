import { api } from "./client";
import type {
  ClientEnvIn,
  DemographicAnswersRequest,
  SessionStartResponse,
  TrialBatchRequest,
  TrialBatchResponse,
} from "./types";

export const runtimeApi = {
  start: (sessionId: string): Promise<SessionStartResponse> =>
    api.post<SessionStartResponse>(`/sessions/${sessionId}/start`),
  submitDemographics: (sessionId: string, payload: DemographicAnswersRequest): Promise<void> =>
    api.post<void>(`/sessions/${sessionId}/demographics`, payload),
  submitTrials: (sessionId: string, payload: TrialBatchRequest): Promise<TrialBatchResponse> =>
    api.post<TrialBatchResponse>(`/sessions/${sessionId}/trials`, payload),
  complete: (sessionId: string): Promise<void> => api.post<void>(`/sessions/${sessionId}/complete`),
  submitClientEnv: (sessionId: string, payload: ClientEnvIn): Promise<void> =>
    api.post<void>(`/sessions/${sessionId}/client-env`, payload),
};
