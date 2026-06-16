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
  GroupSessionsOverviewResponse,
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
  // MOD-12 (MFR-209/210): name-based activation with explicit intervention_session_number.
  activate: (
    groupId: string,
    payload: { session_type: "onboarding" | "pre" | "post"; intervention_session_number: number | null },
  ): Promise<GroupActivateResponse> =>
    api.post<GroupActivateResponse>(`/groups/${groupId}/activate`, {
      session_type: payload.session_type,
      intervention_session_number: payload.intervention_session_number,
    } satisfies GroupActivateRequest),
  deactivate: (
    groupId: string,
    payload: {
      session_type: "onboarding" | "pre" | "post";
      intervention_session_number: number | null;
      force?: boolean;
    },
  ): Promise<GroupDeactivateResponse> =>
    api.post<GroupDeactivateResponse>(`/groups/${groupId}/deactivate`, {
      session_type: payload.session_type,
      intervention_session_number: payload.intervention_session_number,
      force: payload.force ?? false,
    } satisfies GroupDeactivateRequest),
  // MOD-12 (MFR-214): per-stage session status counts.
  sessionsOverview: (groupId: string): Promise<GroupSessionsOverviewResponse> =>
    api.get<GroupSessionsOverviewResponse>(`/groups/${groupId}/sessions-overview`),
};
