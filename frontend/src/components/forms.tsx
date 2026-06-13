import type { ReactNode } from "react";

export const inputClass =
  "block w-full rounded-md border border-gray-300 px-3 py-2 text-sm text-gray-900 shadow-sm focus:border-gray-500 focus:outline-none focus:ring-1 focus:ring-gray-500";

export const selectClass = inputClass;

export function Field({
  label,
  children,
  hint,
}: {
  label: string;
  children: ReactNode;
  hint?: string;
}): JSX.Element {
  return (
    <label className="block">
      <span className="mb-1 block text-sm font-medium text-gray-700">{label}</span>
      {children}
      {hint && <span className="mt-1 block text-xs text-gray-500">{hint}</span>}
    </label>
  );
}

interface ButtonProps {
  type?: "button" | "submit";
  variant?: "primary" | "secondary" | "danger";
  loading?: boolean;
  disabled?: boolean;
  onClick?: () => void;
  children: ReactNode;
  className?: string;
}

const VARIANT_CLASSES: Record<NonNullable<ButtonProps["variant"]>, string> = {
  primary: "bg-gray-900 text-white hover:bg-gray-700",
  secondary: "border border-gray-300 text-gray-700 hover:bg-gray-50",
  danger: "bg-red-600 text-white hover:bg-red-500",
};

export function Button({
  type = "button",
  variant = "primary",
  loading = false,
  disabled = false,
  onClick,
  children,
  className = "",
}: ButtonProps): JSX.Element {
  return (
    <button
      type={type}
      onClick={onClick}
      disabled={disabled || loading}
      className={`rounded-md px-3 py-2 text-sm font-medium disabled:cursor-not-allowed disabled:opacity-50 ${VARIANT_CLASSES[variant]} ${className}`}
    >
      {loading ? "Please wait…" : children}
    </button>
  );
}

export function ErrorBanner({ message }: { message: string | null }): JSX.Element | null {
  if (!message) return null;
  return <div className="rounded border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">{message}</div>;
}

export function SuccessBanner({ message }: { message: string | null }): JSX.Element | null {
  if (!message) return null;
  return (
    <div className="rounded border border-green-200 bg-green-50 px-3 py-2 text-sm text-green-700">{message}</div>
  );
}
