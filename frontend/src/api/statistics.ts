import { api } from "./client";
import type { ParticipantSummaryOut, SessionSummaryDetailOut, StudySummaryOut } from "./types";

export const statisticsApi = {
  sessionSummary: (sessionId: string): Promise<SessionSummaryDetailOut> =>
    api.get<SessionSummaryDetailOut>(`/sessions/${sessionId}/summary`),
  participantSummary: (participantId: string): Promise<ParticipantSummaryOut> =>
    api.get<ParticipantSummaryOut>(`/participants/${participantId}/summary`),
  studySummary: (studyId: string): Promise<StudySummaryOut> =>
    api.get<StudySummaryOut>(`/studies/${studyId}/summary`),
};
