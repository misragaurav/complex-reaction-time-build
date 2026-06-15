import { api } from "./client";
import type {
  GroupActivateRequest,
  GroupActivateResponse,
  GroupAssignRequest,
  GroupAssignResponse,
  GroupCreate,
  GroupDeactivateRequest,
  GroupDeactivateResponse,
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
  // MOD-5: group-level activation (MFR-31/32).
  activate: (groupId: string, sessionType: "pre" | "post" = "pre"): Promise<GroupActivateResponse> =>
    api.post<GroupActivateResponse>(`/groups/${groupId}/activate`, {
      session_type: sessionType,
    } satisfies GroupActivateRequest),
  deactivate: (groupId: string, force = false): Promise<GroupDeactivateResponse> =>
    api.post<GroupDeactivateResponse>(`/groups/${groupId}/deactivate`, {
      force,
    } satisfies GroupDeactivateRequest),
};
