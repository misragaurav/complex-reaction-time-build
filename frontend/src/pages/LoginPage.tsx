import { useState, type FormEvent } from "react";
import { Navigate, useLocation, type Location } from "react-router-dom";
import { participantCheck } from "../api/auth";
import { errorMessage } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import { identityRole, roleHome } from "../auth/types";
import { Button, ErrorBanner, Field, inputClass } from "../components/forms";

type Tab = "participant" | "researcher";
type ParticipantStep = "code" | "password" | "set-password";

interface LocationState {
  from?: Location;
}

const TAB_CLASS = "flex-1 rounded px-3 py-1.5 text-sm font-medium transition-colors";

export default function LoginPage(): JSX.Element {
  const { identity, status, loginUser, loginParticipant, setParticipantPassword } = useAuth();
  const location = useLocation();

  const [tab, setTab] = useState<Tab>("participant");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const [step, setStep] = useState<ParticipantStep>("code");
  const [code, setCode] = useState("");
  const [participantPassword, setParticipantPasswordValue] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");

  if (status === "authenticated" && identity) {
    const from = (location.state as LocationState | null)?.from;
    const target = from ? `${from.pathname}${from.search}` : roleHome(identityRole(identity));
    return <Navigate to={target} replace />;
  }

  const switchTab = (next: Tab): void => {
    setTab(next);
    setError(null);
    setStep("code");
    setCode("");
    setParticipantPasswordValue("");
    setConfirmPassword("");
    setEmail("");
    setPassword("");
  };

  const handleCodeSubmit = async (e: FormEvent): Promise<void> => {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      const trimmed = code.trim();
      const res = await participantCheck({ code: trimmed });
      setCode(trimmed);
      setStep(res.password_set ? "password" : "set-password");
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setLoading(false);
    }
  };

  const handleParticipantLogin = async (e: FormEvent): Promise<void> => {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      await loginParticipant(code, participantPassword);
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setLoading(false);
    }
  };

  const handleSetPassword = async (e: FormEvent): Promise<void> => {
    e.preventDefault();
    setError(null);
    if (participantPassword.length < 6) {
      setError("Password must be at least 6 characters.");
      return;
    }
    if (participantPassword !== confirmPassword) {
      setError("Passwords do not match.");
      return;
    }
    setLoading(true);
    try {
      await setParticipantPassword(code, participantPassword);
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setLoading(false);
    }
  };

  const handleResearcherLogin = async (e: FormEvent): Promise<void> => {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      await loginUser(email, password);
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-gray-50 px-4">
      <div className="w-full max-w-sm rounded-lg border border-gray-200 bg-white p-6 shadow-sm">
        <h1 className="mb-6 text-center text-xl font-semibold text-gray-900">Choice Reaction Time Lab</h1>

        <div className="mb-6 flex rounded-md border border-gray-200 p-1">
          <button
            type="button"
            className={`${TAB_CLASS} ${tab === "participant" ? "bg-gray-900 text-white" : "text-gray-600 hover:bg-gray-50"}`}
            onClick={() => switchTab("participant")}
          >
            Participant
          </button>
          <button
            type="button"
            className={`${TAB_CLASS} ${tab === "researcher" ? "bg-gray-900 text-white" : "text-gray-600 hover:bg-gray-50"}`}
            onClick={() => switchTab("researcher")}
          >
            Researcher
          </button>
        </div>

        <div className="mb-4">
          <ErrorBanner message={error} />
        </div>

        {tab === "participant" && step === "code" && (
          <form className="space-y-4" onSubmit={(e) => void handleCodeSubmit(e)}>
            <Field label="Participant code">
              <input
                className={inputClass}
                value={code}
                onChange={(e) => setCode(e.target.value)}
                autoFocus
                required
                autoComplete="username"
              />
            </Field>
            <Button type="submit" loading={loading} className="w-full">
              Continue
            </Button>
          </form>
        )}

        {tab === "participant" && step === "password" && (
          <form className="space-y-4" onSubmit={(e) => void handleParticipantLogin(e)}>
            <p className="text-sm text-gray-600">
              Code <span className="font-mono font-semibold">{code}</span>
            </p>
            <Field label="Password">
              <input
                type="password"
                className={inputClass}
                value={participantPassword}
                onChange={(e) => setParticipantPasswordValue(e.target.value)}
                autoFocus
                required
                autoComplete="current-password"
              />
            </Field>
            <div className="flex gap-2">
              <Button type="submit" loading={loading} className="flex-1">
                Log in
              </Button>
              <Button type="button" variant="secondary" onClick={() => setStep("code")}>
                Back
              </Button>
            </div>
          </form>
        )}

        {tab === "participant" && step === "set-password" && (
          <form className="space-y-4" onSubmit={(e) => void handleSetPassword(e)}>
            <p className="text-sm text-gray-600">
              First time signing in with code <span className="font-mono font-semibold">{code}</span>. Choose a
              password for future logins.
            </p>
            <Field label="Password" hint="Minimum 6 characters">
              <input
                type="password"
                className={inputClass}
                value={participantPassword}
                onChange={(e) => setParticipantPasswordValue(e.target.value)}
                autoFocus
                required
                minLength={6}
                autoComplete="new-password"
              />
            </Field>
            <Field label="Confirm password">
              <input
                type="password"
                className={inputClass}
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                required
                minLength={6}
                autoComplete="new-password"
              />
            </Field>
            <div className="flex gap-2">
              <Button type="submit" loading={loading} className="flex-1">
                Set password and log in
              </Button>
              <Button type="button" variant="secondary" onClick={() => setStep("code")}>
                Back
              </Button>
            </div>
          </form>
        )}

        {tab === "researcher" && (
          <form className="space-y-4" onSubmit={(e) => void handleResearcherLogin(e)}>
            <Field label="Email">
              <input
                type="email"
                className={inputClass}
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                autoFocus
                required
                autoComplete="username"
              />
            </Field>
            <Field label="Password">
              <input
                type="password"
                className={inputClass}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                autoComplete="current-password"
              />
            </Field>
            <Button type="submit" loading={loading} className="w-full">
              Log in
            </Button>
          </form>
        )}
      </div>
    </div>
  );
}
