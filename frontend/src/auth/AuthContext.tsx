import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react";
import {
  login as loginRequest,
  logout as logoutRequest,
  participantLogin as participantLoginRequest,
  participantRefresh as participantRefreshRequest,
  participantSetPassword as participantSetPasswordRequest,
  refresh as refreshRequest,
} from "../api/auth";
import { onSessionExpire, setAccessToken, setIdentityKind } from "../api/tokenStore";
import type { ParticipantPublic, UserPublic } from "../api/types";
import type { Identity, UserIdentity } from "./types";

const STORAGE_KEY = "crt.identity";

type AuthStatus = "loading" | "authenticated" | "anonymous";

interface AuthState {
  identity: Identity | null;
  status: AuthStatus;
}

interface AuthContextValue extends AuthState {
  loginUser: (email: string, password: string) => Promise<UserPublic>;
  loginParticipant: (code: string, password: string) => Promise<ParticipantPublic>;
  setParticipantPassword: (code: string, password: string) => Promise<ParticipantPublic>;
  updateIdentity: (patch: Partial<UserIdentity>) => void;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

function readStoredIdentity(): Identity | null {
  try {
    const raw = sessionStorage.getItem(STORAGE_KEY);
    return raw ? (JSON.parse(raw) as Identity) : null;
  } catch {
    return null;
  }
}

function writeStoredIdentity(identity: Identity): void {
  sessionStorage.setItem(STORAGE_KEY, JSON.stringify(identity));
}

function clearStoredIdentity(): void {
  sessionStorage.removeItem(STORAGE_KEY);
}

export function AuthProvider({ children }: { children: ReactNode }): JSX.Element {
  const [state, setState] = useState<AuthState>({ identity: null, status: "loading" });

  // Access tokens live in memory only, so a page reload restores the session
  // by exchanging the httpOnly refresh cookie for a new access token and
  // re-hydrating the (non-sensitive) identity cached in sessionStorage.
  useEffect(() => {
    let cancelled = false;

    onSessionExpire(() => {
      setIdentityKind(null);
      clearStoredIdentity();
      setState({ identity: null, status: "anonymous" });
    });

    const stored = readStoredIdentity();
    if (!stored) {
      setState({ identity: null, status: "anonymous" });
    } else {
      // Set the realm BEFORE calling refresh so client.ts routes 401-retries correctly.
      setIdentityKind(stored.kind);
      const doRefresh = stored.kind === "participant" ? participantRefreshRequest : refreshRequest;
      doRefresh()
        .then(({ access_token }) => {
          if (cancelled) return;
          setAccessToken(access_token);
          setState({ identity: stored, status: "authenticated" });
        })
        .catch(() => {
          if (cancelled) return;
          setIdentityKind(null);
          clearStoredIdentity();
          setState({ identity: null, status: "anonymous" });
        });
    }

    return () => {
      cancelled = true;
      onSessionExpire(null);
    };
  }, []);

  const loginUser = useCallback(async (email: string, password: string): Promise<UserPublic> => {
    const res = await loginRequest({ email, password });
    setAccessToken(res.access_token);
    setIdentityKind("user");
    const identity: Identity = {
      kind: "user",
      id: res.user.id,
      email: res.user.email,
      full_name: res.user.full_name,
      role: res.user.role as "admin" | "researcher",
    };
    writeStoredIdentity(identity);
    setState({ identity, status: "authenticated" });
    return res.user;
  }, []);

  const loginParticipant = useCallback(async (code: string, password: string): Promise<ParticipantPublic> => {
    const res = await participantLoginRequest({ code, password });
    setAccessToken(res.access_token);
    setIdentityKind("participant");
    const identity: Identity = { kind: "participant", ...res.participant };
    writeStoredIdentity(identity);
    setState({ identity, status: "authenticated" });
    return res.participant;
  }, []);

  const setParticipantPassword = useCallback(
    async (code: string, password: string): Promise<ParticipantPublic> => {
      const res = await participantSetPasswordRequest({ code, password });
      setAccessToken(res.access_token);
      setIdentityKind("participant");
      const identity: Identity = { kind: "participant", ...res.participant };
      writeStoredIdentity(identity);
      setState({ identity, status: "authenticated" });
      return res.participant;
    },
    [],
  );

  const updateIdentity = useCallback((patch: Partial<UserIdentity>): void => {
    setState((prev) => {
      if (!prev.identity || prev.identity.kind !== "user") {
        return prev;
      }
      const next: Identity = { ...prev.identity, ...patch };
      writeStoredIdentity(next);
      return { ...prev, identity: next };
    });
  }, []);

  const logout = useCallback(async (): Promise<void> => {
    try {
      await logoutRequest();
    } finally {
      setAccessToken(null);
      setIdentityKind(null);
      clearStoredIdentity();
      setState({ identity: null, status: "anonymous" });
    }
  }, []);

  return (
    <AuthContext.Provider
      value={{ ...state, loginUser, loginParticipant, setParticipantPassword, updateIdentity, logout }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return ctx;
}
