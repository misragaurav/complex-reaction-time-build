import { api, apiRequestBlob, type BlobResult } from "./client";
import type { PreviewResponse } from "./types";

export const exportsApi = {
  sessionCsv: (sessionId: string): Promise<BlobResult> => apiRequestBlob(`/sessions/${sessionId}/export.csv`),
  participantCsv: (participantId: string): Promise<BlobResult> =>
    apiRequestBlob(`/participants/${participantId}/export.csv`),
  studyZip: (studyId: string): Promise<BlobResult> => apiRequestBlob(`/studies/${studyId}/export.zip`),
  preview: (studyId: string): Promise<PreviewResponse> =>
    api.post<PreviewResponse>(`/studies/${studyId}/preview`),
};
