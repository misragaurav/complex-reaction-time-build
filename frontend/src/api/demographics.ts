import { api } from "./client";
import type { DemographicFieldCreate, DemographicFieldOut, DemographicFieldUpdate } from "./types";

export const demographicsApi = {
  list: (studyId: string): Promise<DemographicFieldOut[]> =>
    api.get<DemographicFieldOut[]>(`/studies/${studyId}/demographic-fields`),
  create: (studyId: string, payload: DemographicFieldCreate): Promise<DemographicFieldOut> =>
    api.post<DemographicFieldOut>(`/studies/${studyId}/demographic-fields`, payload),
  update: (fieldId: string, payload: DemographicFieldUpdate): Promise<DemographicFieldOut> =>
    api.patch<DemographicFieldOut>(`/demographic-fields/${fieldId}`, payload),
  remove: (fieldId: string): Promise<void> => api.delete<void>(`/demographic-fields/${fieldId}`),
};
