import { api } from "./client";
import type {
  GroupAssignRequest,
  GroupAssignResponse,
  GroupCreate,
  GroupDetailOut,
  GroupOut,
  GroupUpdate,
} from "./types";

export const groupsApi = {
  list: (studyId: string): Promise<GroupOut[]> =>
    api.get<GroupOut[]>(`/studies/${studyId}/groups`),
  create: (studyId: string, payload: GroupCreate): Promise<GroupOut> =>
    api.post<GroupOut>(`/studies/${studyId}/groups`, payload),
  get: (groupId: string): Promise<GroupDetailOut> => api.get<GroupDetailOut>(`/groups/${groupId}`),
  update: (groupId: string, payload: GroupUpdate): Promise<GroupOut> =>
    api.patch<GroupOut>(`/groups/${groupId}`, payload),
  remove: (groupId: string): Promise<void> => api.delete<void>(`/groups/${groupId}`),
  assign: (groupId: string, payload: GroupAssignRequest): Promise<GroupAssignResponse> =>
    api.post<GroupAssignResponse>(`/groups/${groupId}/assign`, payload),
};
