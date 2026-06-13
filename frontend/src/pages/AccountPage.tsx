import { useState, type FormEvent } from "react";
import { errorMessage } from "../api/client";
import type { UserUpdate } from "../api/types";
import { usersApi } from "../api/users";
import { useAuth } from "../auth/AuthContext";
import type { UserIdentity } from "../auth/types";
import { Button, ErrorBanner, Field, inputClass, SuccessBanner } from "../components/forms";

const PASSWORD_MIN_LENGTH = 8;

export default function AccountPage(): JSX.Element {
  const { identity, updateIdentity } = useAuth();

  if (!identity || identity.kind !== "user") {
    return <p className="text-sm text-gray-500">Loading…</p>;
  }

  if (identity.role === "researcher") {
    return (
      <div className="max-w-md space-y-4">
        <h1 className="text-xl font-semibold text-gray-900">Account</h1>
        <dl className="space-y-3 rounded-lg border border-gray-200 bg-white p-4 text-sm">
          <div>
            <dt className="font-medium text-gray-500">Name</dt>
            <dd className="text-gray-900">{identity.full_name}</dd>
          </div>
          <div>
            <dt className="font-medium text-gray-500">Email</dt>
            <dd className="text-gray-900">{identity.email}</dd>
          </div>
          <div>
            <dt className="font-medium text-gray-500">Role</dt>
            <dd className="capitalize text-gray-900">{identity.role}</dd>
          </div>
        </dl>
        <p className="text-sm text-gray-500">Contact an administrator to update your name, email, or password.</p>
      </div>
    );
  }

  return <AdminAccountForm identity={identity} updateIdentity={updateIdentity} />;
}

function AdminAccountForm({
  identity,
  updateIdentity,
}: {
  identity: UserIdentity;
  updateIdentity: (patch: Partial<UserIdentity>) => void;
}): JSX.Element {
  const [fullName, setFullName] = useState(identity.full_name);
  const [email, setEmail] = useState(identity.email);
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: FormEvent): Promise<void> => {
    e.preventDefault();
    setError(null);
    setSuccess(null);

    if (newPassword && newPassword.length < PASSWORD_MIN_LENGTH) {
      setError(`Password must be at least ${PASSWORD_MIN_LENGTH} characters.`);
      return;
    }
    if (newPassword && newPassword !== confirmPassword) {
      setError("Passwords do not match.");
      return;
    }

    const payload: UserUpdate = {};
    if (fullName !== identity.full_name) payload.full_name = fullName;
    if (email !== identity.email) payload.email = email;
    if (newPassword) payload.password = newPassword;

    if (Object.keys(payload).length === 0) {
      setSuccess("Nothing to update.");
      return;
    }

    setLoading(true);
    try {
      const updated = await usersApi.update(identity.id, payload);
      updateIdentity({ full_name: updated.full_name, email: updated.email });
      setNewPassword("");
      setConfirmPassword("");
      setSuccess("Account updated.");
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="max-w-md space-y-4">
      <h1 className="text-xl font-semibold text-gray-900">Account</h1>
      <form
        className="space-y-4 rounded-lg border border-gray-200 bg-white p-4"
        onSubmit={(e) => void handleSubmit(e)}
      >
        <ErrorBanner message={error} />
        <SuccessBanner message={success} />
        <Field label="Name">
          <input className={inputClass} value={fullName} onChange={(e) => setFullName(e.target.value)} required />
        </Field>
        <Field label="Email">
          <input
            type="email"
            className={inputClass}
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
          />
        </Field>
        <Field label="Role">
          <input className={`${inputClass} bg-gray-100 text-gray-500`} value="Admin" disabled readOnly />
        </Field>
        <div className="space-y-3 border-t border-gray-200 pt-4">
          <p className="text-sm font-medium text-gray-700">Change password</p>
          <Field
            label="New password"
            hint={`Leave blank to keep your current password. Minimum ${PASSWORD_MIN_LENGTH} characters.`}
          >
            <input
              type="password"
              className={inputClass}
              value={newPassword}
              onChange={(e) => setNewPassword(e.target.value)}
              autoComplete="new-password"
              minLength={PASSWORD_MIN_LENGTH}
            />
          </Field>
          <Field label="Confirm new password">
            <input
              type="password"
              className={inputClass}
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              autoComplete="new-password"
              minLength={PASSWORD_MIN_LENGTH}
            />
          </Field>
        </div>
        <Button type="submit" loading={loading}>
          Save changes
        </Button>
      </form>
    </div>
  );
}
