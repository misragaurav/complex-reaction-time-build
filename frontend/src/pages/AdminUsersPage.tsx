import { useEffect, useState, type FormEvent } from "react";
import { errorMessage } from "../api/client";
import type { UserCreate, UserOut, UserRole, UserUpdate } from "../api/types";
import { usersApi } from "../api/users";
import { useAuth } from "../auth/AuthContext";
import { Button, ErrorBanner, Field, inputClass, selectClass, SuccessBanner } from "../components/forms";

const PASSWORD_MIN_LENGTH = 8;

const ROLE_LABELS: Record<UserRole, string> = {
  admin: "Admin",
  researcher: "Researcher",
};

function CreateUserForm({ onCreated }: { onCreated: (user: UserOut) => void }): JSX.Element {
  const [email, setEmail] = useState("");
  const [fullName, setFullName] = useState("");
  const [role, setRole] = useState<UserRole>("researcher");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(e: FormEvent): Promise<void> {
    e.preventDefault();
    setError(null);
    if (password.length < PASSWORD_MIN_LENGTH) {
      setError(`Password must be at least ${PASSWORD_MIN_LENGTH} characters.`);
      return;
    }
    setSubmitting(true);
    try {
      const payload: UserCreate = { email: email.trim(), full_name: fullName.trim(), role, password };
      const user = await usersApi.create(payload);
      onCreated(user);
      setEmail("");
      setFullName("");
      setRole("researcher");
      setPassword("");
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <form onSubmit={(e) => void handleSubmit(e)} className="space-y-4 rounded-lg border border-gray-200 bg-white p-4">
      <h2 className="text-base font-semibold text-gray-900">Create user</h2>
      <ErrorBanner message={error} />
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <Field label="Email">
          <input
            type="email"
            className={inputClass}
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
          />
        </Field>
        <Field label="Full name">
          <input className={inputClass} value={fullName} onChange={(e) => setFullName(e.target.value)} required />
        </Field>
        <Field label="Role">
          <select className={selectClass} value={role} onChange={(e) => setRole(e.target.value as UserRole)}>
            {(Object.keys(ROLE_LABELS) as UserRole[]).map((r) => (
              <option key={r} value={r}>
                {ROLE_LABELS[r]}
              </option>
            ))}
          </select>
        </Field>
        <Field label="Password" hint={`Minimum ${PASSWORD_MIN_LENGTH} characters.`}>
          <input
            type="password"
            className={inputClass}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            autoComplete="new-password"
            minLength={PASSWORD_MIN_LENGTH}
            required
          />
        </Field>
      </div>
      <Button type="submit" loading={submitting}>
        Create user
      </Button>
    </form>
  );
}

function UserRow({
  user,
  isSelf,
  onUpdated,
}: {
  user: UserOut;
  isSelf: boolean;
  onUpdated: (user: UserOut) => void;
}): JSX.Element {
  const [editing, setEditing] = useState(false);
  const [email, setEmail] = useState(user.email);
  const [fullName, setFullName] = useState(user.full_name);
  const [role, setRole] = useState<UserRole>(user.role === "admin" ? "admin" : "researcher");
  const [newPassword, setNewPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function handleSave(): Promise<void> {
    setError(null);
    setSuccess(null);
    if (newPassword && newPassword.length < PASSWORD_MIN_LENGTH) {
      setError(`Password must be at least ${PASSWORD_MIN_LENGTH} characters.`);
      return;
    }
    const payload: UserUpdate = {};
    if (email.trim() !== user.email) payload.email = email.trim();
    if (fullName.trim() !== user.full_name) payload.full_name = fullName.trim();
    if (role !== user.role) payload.role = role;
    if (newPassword) payload.password = newPassword;
    if (Object.keys(payload).length === 0) {
      setEditing(false);
      return;
    }
    setBusy(true);
    try {
      onUpdated(await usersApi.update(user.id, payload));
      setNewPassword("");
      setEditing(false);
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  async function toggleActive(): Promise<void> {
    setError(null);
    setSuccess(null);
    setBusy(true);
    try {
      onUpdated(await usersApi.update(user.id, { is_active: !user.is_active }));
      setSuccess(user.is_active ? "User deactivated." : "User reactivated.");
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <li className={`space-y-3 px-4 py-4 ${user.is_active ? "" : "opacity-60"}`}>
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="font-medium text-gray-900">
            {user.full_name}
            {isSelf && <span className="ml-2 text-xs text-gray-400">(you)</span>}
            {!user.is_active && (
              <span className="ml-2 rounded-full bg-gray-100 px-2 py-0.5 text-xs font-medium text-gray-500">
                Deactivated
              </span>
            )}
          </p>
          <p className="text-sm text-gray-500">
            {user.email} · {user.role === "admin" ? "Admin" : "Researcher"}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="secondary" onClick={() => setEditing((v) => !v)}>
            {editing ? "Close" : "Edit"}
          </Button>
          {!isSelf && (
            <Button variant={user.is_active ? "danger" : "secondary"} onClick={() => void toggleActive()} disabled={busy}>
              {user.is_active ? "Deactivate" : "Reactivate"}
            </Button>
          )}
        </div>
      </div>
      <ErrorBanner message={error} />
      <SuccessBanner message={success} />
      {editing && (
        <div className="space-y-4 rounded border border-gray-200 p-3">
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <Field label="Email">
              <input type="email" className={inputClass} value={email} onChange={(e) => setEmail(e.target.value)} />
            </Field>
            <Field label="Full name">
              <input className={inputClass} value={fullName} onChange={(e) => setFullName(e.target.value)} />
            </Field>
            <Field label="Role">
              <select className={selectClass} value={role} onChange={(e) => setRole(e.target.value as UserRole)}>
                {(Object.keys(ROLE_LABELS) as UserRole[]).map((r) => (
                  <option key={r} value={r}>
                    {ROLE_LABELS[r]}
                  </option>
                ))}
              </select>
            </Field>
            <Field label="New password" hint="Leave blank to keep the current password.">
              <input
                type="password"
                className={inputClass}
                value={newPassword}
                onChange={(e) => setNewPassword(e.target.value)}
                autoComplete="new-password"
              />
            </Field>
          </div>
          <Button onClick={() => void handleSave()} loading={busy}>
            Save
          </Button>
        </div>
      )}
    </li>
  );
}

export default function AdminUsersPage(): JSX.Element {
  const { identity } = useAuth();
  const [users, setUsers] = useState<UserOut[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  const selfId = identity?.kind === "user" ? identity.id : null;

  useEffect(() => {
    usersApi
      .list()
      .then(setUsers)
      .catch((err: unknown) => setError(errorMessage(err)));
  }, []);

  return (
    <div className="max-w-3xl space-y-6">
      <h1 className="text-xl font-semibold text-gray-900">Users</h1>
      <ErrorBanner message={error} />
      {!users ? (
        <p className="text-sm text-gray-500">Loading…</p>
      ) : (
        <ul className="divide-y divide-gray-200 rounded-lg border border-gray-200 bg-white">
          {users.map((u) => (
            <UserRow
              key={u.id}
              user={u}
              isSelf={u.id === selfId}
              onUpdated={(updated) => setUsers((prev) => prev?.map((x) => (x.id === updated.id ? updated : x)) ?? prev)}
            />
          ))}
        </ul>
      )}
      <CreateUserForm onCreated={(user) => setUsers((prev) => (prev ? [...prev, user] : [user]))} />
    </div>
  );
}
