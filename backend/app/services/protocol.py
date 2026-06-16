"""MOD-3: longitudinal protocol structure, labelling, and generation helpers.

A study's protocol is 1 onboarding session + N intervention pairs (pre/post),
where N = ``num_intervention_sessions``. order_index is 1 for onboarding,
``2k`` for pre(k), ``2k+1`` for post(k) (k = 1..N).
"""

from __future__ import annotations

import math
from typing import Any, TypedDict


def compute_week_day(
    intervention_session_number: int, sessions_per_week: int, week_start: int = 1
) -> tuple[int, int]:
    """(week_number, day_within_week) for an intervention session (MFR-15).

    ``week_number = week_start - 1 + ceil(k / sessions_per_week)`` and
    ``day_within_week = ((k - 1) mod sessions_per_week) + 1``.
    """
    k = intervention_session_number
    week = week_start - 1 + math.ceil(k / sessions_per_week)
    day = ((k - 1) % sessions_per_week) + 1
    return week, day


def compute_display_label(
    session_type: str, week_number: int | None, day_within_week: int | None
) -> str:
    """Auto-computed label per MFR-16."""
    if session_type == "onboarding":
        return "Onboarding"
    suffix = "Pre" if session_type == "pre" else "Post"
    return f"Week {week_number} · Day {day_within_week} · {suffix}"


class ProtocolSessionSpec(TypedDict):
    order_index: int
    session_type: str
    intervention_session_number: int | None
    week_number: int | None
    day_within_week: int | None
    display_label: str
    task_type: str


def build_protocol_specs(
    *,
    num_intervention_sessions: int,
    sessions_per_week: int,
    week_start: int,
    task_type: str,
) -> list[ProtocolSessionSpec]:
    """Full ordered list of ``1 + 2N`` session specs for one participant (MFR-13/17).

    MOD-7: all stages (onboarding, pre, post) use the single study ``task_type``.
    """
    specs: list[ProtocolSessionSpec] = [
        {
            "order_index": 1,
            "session_type": "onboarding",
            "intervention_session_number": None,
            "week_number": None,
            "day_within_week": None,
            "display_label": compute_display_label("onboarding", None, None),
            "task_type": task_type,
        }
    ]
    for k in range(1, num_intervention_sessions + 1):
        week, day = compute_week_day(k, sessions_per_week, week_start)
        specs.append(
            {
                "order_index": 2 * k,
                "session_type": "pre",
                "intervention_session_number": k,
                "week_number": week,
                "day_within_week": day,
                "display_label": compute_display_label("pre", week, day),
                "task_type": task_type,
            }
        )
        specs.append(
            {
                "order_index": 2 * k + 1,
                "session_type": "post",
                "intervention_session_number": k,
                "week_number": week,
                "day_within_week": day,
                "display_label": compute_display_label("post", week, day),
                "task_type": task_type,
            }
        )
    return specs


