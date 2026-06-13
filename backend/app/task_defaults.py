"""Task parameter defaults and constants from PRD §5.2-§5.4."""

from __future__ import annotations

from typing import Any, Final

TASK_TYPES: Final[list[str]] = ["CRT2", "CRT3", "CRT4"]

# §5.2 number of stimulus positions per task type
TASK_POSITIONS: Final[dict[str, int]] = {"CRT2": 2, "CRT3": 3, "CRT4": 4}

# §5.2 default key mappings, left -> right
DEFAULT_KEY_MAPS: Final[dict[str, list[str]]] = {
    "CRT2": ["ArrowLeft", "ArrowRight"],
    "CRT3": ["KeyZ", "KeyX", "KeyC"],
    "CRT4": ["KeyZ", "KeyX", "KeyN", "KeyM"],
}

# §5.2 displayed key cap labels
KEY_LABELS: Final[dict[str, str]] = {
    "ArrowLeft": "←",
    "ArrowRight": "→",
    "ArrowUp": "↑",
    "ArrowDown": "↓",
    **{f"Key{c}": c for c in "ABCDEFGHIJKLMNOPQRSTUVWXYZ"},
    **{f"Digit{d}": str(d) for d in range(10)},
}

# FR-39: allowed KeyboardEvent.code values for key_map (letters, digits, arrows)
ALLOWED_KEY_CODES: Final[list[str]] = (
    [f"Key{c}" for c in "ABCDEFGHIJKLMNOPQRSTUVWXYZ"]
    + [f"Digit{d}" for d in range(10)]
    + ["ArrowLeft", "ArrowRight", "ArrowUp", "ArrowDown"]
)

# §5.3 verbatim default instructions template
DEFAULT_INSTRUCTIONS_TEXT: Final[str] = (
    "You will see {N} crosses on the screen. On each trial, one of the crosses "
    "will change into a box. Press the key that matches the position of the box "
    "as quickly and as accurately as you can. The keys are: {KEYS}. Place your "
    "fingers on these keys now. There will be {P} practice trials first, then "
    "{T} test trials."
)

# §5.4 parameter defaults, excluding task_type and key_map (which are
# task-type dependent and added by default_params()).
PARAM_DEFAULTS_BASE: Final[dict[str, Any]] = {
    "practice_trials": 3,
    "test_trials": 20,
    "foreperiod_min_ms": 1000,
    "foreperiod_max_ms": 3000,
    "response_timeout_ms": 3000,
    "iti_ms": 500,
    "practice_feedback": True,
    "feedback_duration_ms": 500,
    "max_consecutive_repeats": 3,
    "outlier_low_ms": 150,
    "outlier_high_ms": 1500,
    "show_progress": True,
    "instructions_text": DEFAULT_INSTRUCTIONS_TEXT,
}

# §4.9 / D-9 default outlier thresholds, used by the statistics service.
DEFAULT_OUTLIER_LOW_MS: Final[int] = PARAM_DEFAULTS_BASE["outlier_low_ms"]
DEFAULT_OUTLIER_HIGH_MS: Final[int] = PARAM_DEFAULTS_BASE["outlier_high_ms"]


def default_params(task_type: str) -> dict[str, Any]:
    """Return the full §5.4 parameter set (incl. task_type and key_map) for
    a given task type. This is the canonical "study/session params" shape.
    """
    if task_type not in TASK_TYPES:
        raise ValueError(f"Unknown task_type: {task_type!r}")
    params = dict(PARAM_DEFAULTS_BASE)
    params["task_type"] = task_type
    params["key_map"] = list(DEFAULT_KEY_MAPS[task_type])
    return params


def render_instructions(template: str, params: dict[str, Any]) -> str:
    """Substitute {N}, {KEYS}, {P}, {T} placeholders per §5.3."""
    task_type = params["task_type"]
    n = TASK_POSITIONS[task_type]
    keys = " ".join(KEY_LABELS.get(code, code) for code in params["key_map"])
    return template.format(
        N=n,
        KEYS=keys,
        P=params["practice_trials"],
        T=params["test_trials"],
    )
