export interface UserIdentity {
  kind: "user";
  id: string;
  email: string;
  full_name: string;
  role: "admin" | "researcher";
}

export interface ParticipantIdentity {
  kind: "participant";
  id: string;
  code: string;
  study_name: string;
}

export type Identity = UserIdentity | ParticipantIdentity;

export type Role = "admin" | "researcher" | "participant";

export function identityRole(identity: Identity): Role {
  return identity.kind === "participant" ? "participant" : identity.role;
}

export function roleHome(role: Role): string {
  return role === "participant" ? "/me" : "/studies";
}
