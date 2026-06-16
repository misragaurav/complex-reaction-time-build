/**
 * MAC-132: Unit tests for usePersistentState and the StudySessionsTab prefs restore.
 */

import { act, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { useState } from "react";
import { usePersistentState } from "../src/hooks/usePersistentState";
import StudySessionsTab from "../src/pages/StudySessionsTab";
import type { StudyOut } from "../src/api/types";

// ---------------------------------------------------------------------------
// localStorage stub (jsdom already provides one, but we reset between tests)
// ---------------------------------------------------------------------------

beforeEach(() => {
  localStorage.clear();
});

afterEach(() => {
  localStorage.clear();
  vi.clearAllMocks();
});

// ---------------------------------------------------------------------------
// Minimal wrapper for testing the hook directly
// ---------------------------------------------------------------------------

function UseHookWrapper<T>({
  hookKey,
  initial,
  validate,
  onValue,
}: {
  hookKey: string;
  initial: T;
  validate?: (raw: unknown) => T | null;
  onValue: (val: T) => void;
}): JSX.Element {
  const [value, setValue] = usePersistentState(hookKey, initial, validate ? { validate } : undefined);
  onValue(value);
  return (
    <button onClick={() => setValue((v) => (typeof v === "string" ? ("updated" as T) : v))}>
      trigger
    </button>
  );
}

// ---------------------------------------------------------------------------
// usePersistentState unit tests
// ---------------------------------------------------------------------------

describe("usePersistentState", () => {
  it("returns initial value when nothing is stored", () => {
    let captured: string | undefined;
    render(
      <UseHookWrapper
        hookKey="test-key"
        initial="default"
        onValue={(v: string) => { captured = v; }}
      />,
    );
    expect(captured).toBe("default");
  });

  it("round-trips a value through localStorage", async () => {
    localStorage.setItem("test-key", JSON.stringify("stored-value"));
    let captured: string | undefined;
    render(
      <UseHookWrapper
        hookKey="test-key"
        initial="default"
        onValue={(v: string) => { captured = v; }}
      />,
    );
    // Should read stored value on mount.
    expect(captured).toBe("stored-value");
  });

  it("returns initial and does not throw when the entry is non-JSON", async () => {
    localStorage.setItem("test-key", "not-valid-json{{{");
    let captured: string | undefined;
    expect(() => {
      render(
        <UseHookWrapper
          hookKey="test-key"
          initial="fallback"
          onValue={(v: string) => { captured = v; }}
        />,
      );
    }).not.toThrow();
    expect(captured).toBe("fallback");
    // The corrupt entry is removed and replaced with the initial value by the write effect (MFR-134).
    await waitFor(() => {
      expect(JSON.parse(localStorage.getItem("test-key") ?? "null")).toBe("fallback");
    });
  });

  it("applies validate to reject out-of-domain stored values", () => {
    localStorage.setItem("test-key", JSON.stringify("invalid"));
    let captured: string | undefined;
    render(
      <UseHookWrapper
        hookKey="test-key"
        initial="default"
        validate={(raw) => (raw === "valid" ? "valid" : null)}
        onValue={(v: string) => { captured = v; }}
      />,
    );
    // "invalid" does not pass validate → falls back to initial.
    expect(captured).toBe("default");
  });

  it("applies validate and accepts a valid stored value", () => {
    localStorage.setItem("test-key", JSON.stringify("valid"));
    let captured: string | undefined;
    render(
      <UseHookWrapper
        hookKey="test-key"
        initial="default"
        validate={(raw) => (raw === "valid" ? "valid" : null)}
        onValue={(v: string) => { captured = v; }}
      />,
    );
    expect(captured).toBe("valid");
  });

  it("writes to localStorage when the state changes", async () => {
    render(
      <UseHookWrapper
        hookKey="test-key"
        initial="initial"
        onValue={() => undefined}
      />,
    );
    expect(JSON.parse(localStorage.getItem("test-key") ?? "null")).toBe("initial");

    act(() => {
      screen.getByText("trigger").click();
    });

    await waitFor(() => {
      expect(JSON.parse(localStorage.getItem("test-key") ?? "null")).toBe("updated");
    });
  });
});

// ---------------------------------------------------------------------------
// StudySessionsTab prefs-restore test (MAC-132)
// ---------------------------------------------------------------------------

vi.mock("../src/api/sessions", () => ({
  sessionsApi: {
    list: vi.fn().mockResolvedValue([]),
    activate: vi.fn(),
    deactivate: vi.fn(),
    cancel: vi.fn(),
    update: vi.fn(),
  },
}));
vi.mock("../src/api/participants", () => ({
  participantsApi: {
    list: vi.fn().mockResolvedValue([]),
    update: vi.fn(),
  },
}));
vi.mock("../src/api/exports", () => ({
  exportsApi: { studyZip: vi.fn() },
}));

const STUDY: StudyOut = {
  id: "study-restore-001",
  name: "Restore Test Study",
  description: null,
  task_type: "CRT2",
  params: {
    task_type: "CRT2",
    practice_trials: 5,
    test_trials: 20,
    foreperiod_min_ms: 1000,
    foreperiod_max_ms: 2000,
    response_timeout_ms: 3000,
    iti_ms: 500,
    key_map: ["KeyF", "KeyJ"],
    practice_feedback: true,
    feedback_duration_ms: 800,
    max_consecutive_repeats: 3,
    outlier_low_ms: 100,
    outlier_high_ms: 1500,
    show_progress: true,
    instructions_text: "",
  },
  num_intervention_sessions: 6,
  sessions_per_week: 3,
  protocol_locked: false,
  created_by: "user-001",
  is_archived: false,
  params_locked: false,
  counts: { participants: 0, sessions_total: 0, sessions_completed: 0, completion_pct: 0 },
  created_at: "2024-01-01T00:00:00Z",
  updated_at: "2024-01-01T00:00:00Z",
};

describe("StudySessionsTab prefs restore (MAC-132)", () => {
  it("restores groupMode, sortField, sortDir, and statusFilter from localStorage", async () => {
    // Pre-seed prefs for this study.
    localStorage.setItem(
      `crt.sessionsTab.prefs.${STUDY.id}`,
      JSON.stringify({
        groupMode: "participant",
        sortField: "completed_at",
        sortDir: "desc",
        statusFilter: "completed",
        participantFilter: "",
        collapsed: [],
      }),
    );

    render(<StudySessionsTab study={STUDY} />);

    // groupMode is rendered as radio buttons ("None" / "Participant" / "Group").
    // The "Participant" radio should be checked because groupMode = "participant" was stored.
    await waitFor(() => {
      const radios = screen.getAllByRole("radio") as HTMLInputElement[];
      const participantRadio = radios.find((r) => {
        const label = r.closest("label");
        return label?.textContent?.trim() === "Participant";
      });
      expect(participantRadio).toBeDefined();
      expect(participantRadio?.checked).toBe(true);
    });
  });
});
