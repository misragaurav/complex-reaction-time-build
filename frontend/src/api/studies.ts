import { api } from "./client";
import type {
  GenerateProtocolRequest,
  GenerateProtocolResponse,
  StudyCreate,
  StudyOut,
  StudyUpdate,
} from "./types";

export const studiesApi = {
  list: (archived?: boolean): Promise<StudyOut[]> =>
    api.get<StudyOut[]>("/studies", archived === undefined ? undefined : { archived }),
  create: (payload: StudyCreate): Promise<StudyOut> => api.post<StudyOut>("/studies", payload),
  get: (studyId: string): Promise<StudyOut> => api.get<StudyOut>(`/studies/${studyId}`),
  update: (studyId: string, payload: StudyUpdate): Promise<StudyOut> =>
    api.patch<StudyOut>(`/studies/${studyId}`, payload),
  // MOD-3: protocol generation (API #33).
  generateProtocol: (
    studyId: string,
    payload: GenerateProtocolRequest,
  ): Promise<GenerateProtocolResponse> =>
    api.post<GenerateProtocolResponse>(`/studies/${studyId}/generate-protocol`, payload),
};
