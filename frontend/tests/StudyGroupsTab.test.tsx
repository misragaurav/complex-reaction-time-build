/**
 * MAC-125: Render test for StudyGroupsTab (MOD-8).
 *
 * Asserts:
 * - Selected row carries bg-blue-50 / ring-2 / ring-blue-500 / font-semibold (MFR-123)
 * - Three stage rows present with Activate / Deactivate / Force deactivate controls
 * - Pre/Post controls disabled when IS is unset; Onboarding controls enabled
 * - No "Open", "Close", or "Expire" action labels in the rendered output
 */

import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import { describe, expect, it, vi, beforeEach } from "vitest";
import StudyGroupsTab from "../src/pages/StudyGroupsTab";
import type { GroupDetailOut, GroupOut, StudyOut } from "../src/api/types";

// Mock the entire groupsApi module.
vi.mock("../src/api/groups", () => ({
  groupsApi: {
    list: vi.fn(),
    get: vi.fn(),
    create: vi.fn(),
    update: vi.fn(),
    remove: vi.fn(),
    assign: vi.fn(),
    activate: vi.fn(),
    deactivate: vi.fn(),
  },
}));

// Import after mocking so we get the mocked version.
import { groupsApi } from "../src/api/groups";

const STUDY: StudyOut = {
  id: "study-001",
  name: "Test Study",
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
  counts: { participants: 2, sessions_total: 14, sessions_completed: 3, completion_pct: 21 },
  created_at: "2024-01-01T00:00:00Z",
  updated_at: "2024-01-01T00:00:00Z",
};

const GROUP_WITH_IS: GroupOut = {
  id: "group-001",
  study_id: "study-001",
  name: "Group A",
  description: null,
  current_intervention_session: 3,
  member_count: 2,
  created_at: "2024-01-01T00:00:00Z",
};

const GROUP_NO_IS: GroupOut = {
  id: "group-002",
  study_id: "study-001",
  name: "Group B",
  description: null,
  current_intervention_session: null,
  member_count: 1,
  created_at: "2024-01-01T00:00:00Z",
};

const DETAIL_WITH_IS: GroupDetailOut = {
  ...GROUP_WITH_IS,
  members: [
    { participant_id: "p-001", code: "P001", is_active: true, sessions_assigned: 7, sessions_completed: 2 },
    { participant_id: "p-002", code: "P002", is_active: true, sessions_assigned: 7, sessions_completed: 1 },
  ],
  completion: {
    total_assigned: 2,
    completed_pre_overall: 2,
    completed_post_overall: 1,
    completed_pre_current: 1,
    completed_post_current: 0,
  },
};

const DETAIL_NO_IS: GroupDetailOut = {
  ...GROUP_NO_IS,
  members: [
    { participant_id: "p-003", code: "P003", is_active: true, sessions_assigned: 7, sessions_completed: 0 },
  ],
  completion: {
    total_assigned: 1,
    completed_pre_overall: 0,
    completed_post_overall: 0,
    completed_pre_current: 0,
    completed_post_current: 0,
  },
};

function mockList(groups: GroupOut[]): void {
  vi.mocked(groupsApi.list).mockResolvedValue(groups);
}

function mockGet(detail: GroupDetailOut): void {
  vi.mocked(groupsApi.get).mockResolvedValue(detail);
}

beforeEach(() => {
  vi.clearAllMocks();
});

describe("StudyGroupsTab — MAC-125 render tests", () => {
  it("selected row carries MFR-123 highlight classes", async () => {
    mockList([GROUP_WITH_IS]);
    mockGet(DETAIL_WITH_IS);

    render(<StudyGroupsTab study={STUDY} />);

    // Wait for the groups list to load.
    await waitFor(() => screen.getByText("Group A"));

    const row = screen.getByText("Group A").closest("button");
    expect(row).not.toBeNull();

    // Before selection: none of the highlight classes (hover:bg-blue-50 is a different token).
    expect(row?.classList.contains("bg-blue-50")).toBe(false);
    expect(row?.classList.contains("ring-2")).toBe(false);
    expect(row?.classList.contains("font-semibold")).toBe(false);

    // Click to select.
    fireEvent.click(row!);

    // After selection: all three highlight classes present (MFR-123).
    expect(row?.classList.contains("bg-blue-50")).toBe(true);
    expect(row?.classList.contains("ring-2")).toBe(true);
    expect(row?.classList.contains("ring-blue-500")).toBe(true);
    expect(row?.classList.contains("font-semibold")).toBe(true);
  });

  it("all three stage rows appear with Activate, Deactivate, Force deactivate buttons", async () => {
    mockList([GROUP_WITH_IS]);
    mockGet(DETAIL_WITH_IS);

    render(<StudyGroupsTab study={STUDY} />);
    await waitFor(() => screen.getByText("Group A"));
    fireEvent.click(screen.getByText("Group A").closest("button")!);

    // Wait for detail panel to load.
    await waitFor(() => screen.getByText("Onboarding"));

    // All three stage labels.
    expect(screen.getByText("Onboarding")).toBeDefined();
    expect(screen.getByText(`Pre (IS ${GROUP_WITH_IS.current_intervention_session})`)).toBeDefined();
    expect(screen.getByText(`Post (IS ${GROUP_WITH_IS.current_intervention_session})`)).toBeDefined();

    // Each row has three buttons: 3 rows × 3 buttons = 9 total activation buttons.
    const activateBtns = screen.getAllByRole("button", { name: "Activate" });
    const deactivateBtns = screen.getAllByRole("button", { name: "Deactivate" });
    const forceBtns = screen.getAllByRole("button", { name: "Force deactivate" });
    expect(activateBtns).toHaveLength(3);
    expect(deactivateBtns).toHaveLength(3);
    expect(forceBtns).toHaveLength(3);
  });

  it("Pre and Post controls are disabled when group has no IS; Onboarding is enabled", async () => {
    mockList([GROUP_NO_IS]);
    mockGet(DETAIL_NO_IS);

    render(<StudyGroupsTab study={STUDY} />);
    await waitFor(() => screen.getByText("Group B"));
    fireEvent.click(screen.getByText("Group B").closest("button")!);
    await waitFor(() => screen.getByText("Onboarding"));

    // Collect all Activate buttons; the one for onboarding should be enabled.
    const activateBtns = screen.getAllByRole("button", { name: "Activate" }) as HTMLButtonElement[];
    const deactivateBtns = screen.getAllByRole("button", { name: "Deactivate" }) as HTMLButtonElement[];
    const forceBtns = screen.getAllByRole("button", { name: "Force deactivate" }) as HTMLButtonElement[];

    // Index 0 = Onboarding, 1 = Pre, 2 = Post.
    expect(activateBtns[0].disabled).toBe(false);
    expect(activateBtns[1].disabled).toBe(true);
    expect(activateBtns[2].disabled).toBe(true);
    expect(deactivateBtns[0].disabled).toBe(false);
    expect(deactivateBtns[1].disabled).toBe(true);
    expect(deactivateBtns[2].disabled).toBe(true);
    expect(forceBtns[0].disabled).toBe(false);
    expect(forceBtns[1].disabled).toBe(true);
    expect(forceBtns[2].disabled).toBe(true);
  });

  it("no 'Open', 'Close', or 'Expire' action labels appear in the rendered output", async () => {
    mockList([GROUP_WITH_IS]);
    mockGet(DETAIL_WITH_IS);

    render(<StudyGroupsTab study={STUDY} />);
    await waitFor(() => screen.getByText("Group A"));
    fireEvent.click(screen.getByText("Group A").closest("button")!);
    await waitFor(() => screen.getByText("Onboarding"));

    // No button or text matching these forbidden labels.
    expect(screen.queryByRole("button", { name: /^Open/i })).toBeNull();
    expect(screen.queryByRole("button", { name: /^Close/i })).toBeNull();
    expect(screen.queryByRole("button", { name: /^Expire/i })).toBeNull();
    // Also verify no rendered text that reads exactly "Expire".
    expect(screen.queryByText(/\bExpire\b/)).toBeNull();
    expect(screen.queryByText(/\bExpired\b/)).toBeNull();
  });
});
