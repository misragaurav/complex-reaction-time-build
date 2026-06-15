import { api } from "./client";
import type {
  MySessionOut,
  SessionActionRequest,
  SessionOut,
  SessionSort,
  SessionStatus,
} from "./types";

export interface ListSessionsParams {
  status?: SessionStatus;
  participantId?: string;
  sort?: SessionSort;
}

export const sessionsApi = {
  list: (studyId: string, params: ListSessionsParams = {}): Promise<SessionOut[]> =>
    api.get<SessionOut[]>(`/studies/${studyId}/sessions`, {
      status: params.status,
      participant_id: params.participantId,
      sort: params.sort,
    }),
  update: (sessionId: string, payload: SessionActionRequest): Promise<SessionOut> =>
    api.patch<SessionOut>(`/sessions/${sessionId}`, payload),
  remove: (sessionId: string): Promise<void> => api.delete<void>(`/sessions/${sessionId}`),
  listMine: (): Promise<MySessionOut[]> => api.get<MySessionOut[]>("/me/sessions"),
  // MOD-5: per-session activation (MFR-33).
  activate: (sessionId: string): Promise<SessionOut> =>
    api.post<SessionOut>(`/sessions/${sessionId}/activate`, {}),
  deactivate: (sessionId: string): Promise<SessionOut> =>
    api.post<SessionOut>(`/sessions/${sessionId}/deactivate`, {}),
};
