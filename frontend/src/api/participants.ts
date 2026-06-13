import { apiRequestBlob, type BlobResult, api } from "./client";
import type { ParticipantCreate, ParticipantOut, ParticipantUpdate } from "./types";

export const participantsApi = {
  list: (studyId: string): Promise<ParticipantOut[]> =>
    api.get<ParticipantOut[]>(`/studies/${studyId}/participants`),
  create: (studyId: string, payload: ParticipantCreate): Promise<ParticipantOut[]> =>
    api.post<ParticipantOut[]>(`/studies/${studyId}/participants`, payload),
  update: (participantId: string, payload: ParticipantUpdate): Promise<ParticipantOut> =>
    api.patch<ParticipantOut>(`/participants/${participantId}`, payload),
  exportCodesCsv: (studyId: string): Promise<BlobResult> =>
    apiRequestBlob(`/studies/${studyId}/participants.csv`),
};
