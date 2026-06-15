"""Shared schemas: the §5.4 task parameter set and merge/validation helpers."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.task_defaults import ALLOWED_KEY_CODES, TASK_POSITIONS, default_params

TaskType = Literal["SRT", "CRT2", "CRT3", "CRT4"]  # MOD-2: SRT added


class TaskParams(BaseModel):
    """The exact §5.4 parameter set. Every study and session `params` JSON
    blob is exactly this shape (including `task_type`, per the §5.4 table)."""

    model_config = ConfigDict(extra="forbid")

    task_type: TaskType
    practice_trials: int = Field(ge=0, le=50)
    test_trials: int = Field(ge=1, le=500)
    foreperiod_min_ms: int = Field(ge=200, le=10000)
    foreperiod_max_ms: int = Field(ge=200, le=10000)
    response_timeout_ms: int = Field(ge=500, le=10000)
    iti_ms: int = Field(ge=0, le=5000)
    key_map: list[str]
    practice_feedback: bool
    feedback_duration_ms: int = Field(ge=100, le=3000)
    max_consecutive_repeats: int = Field(ge=1, le=10)
    outlier_low_ms: int = Field(ge=0)
    outlier_high_ms: int
    show_progress: bool
    instructions_text: str = Field(max_length=2000)

    @model_validator(mode="after")
    def _validate_cross_fields(self) -> "TaskParams":
        if self.foreperiod_min_ms > self.foreperiod_max_ms:
            raise ValueError("foreperiod_min_ms must be <= foreperiod_max_ms")
        if self.outlier_high_ms <= self.outlier_low_ms:
            raise ValueError("outlier_high_ms must be > outlier_low_ms")
        n = TASK_POSITIONS[self.task_type]
        if len(self.key_map) != n:
            raise ValueError(f"key_map must have exactly {n} entries for {self.task_type}")
        if len(set(self.key_map)) != len(self.key_map):
            raise ValueError("key_map entries must be distinct")
        for code in self.key_map:
            if code not in ALLOWED_KEY_CODES:
                raise ValueError(f"key_map entry {code!r} is not an allowed KeyboardEvent.code")
        return self


def merge_and_validate_params(
    task_type: TaskType,
    base: dict[str, Any] | None,
    overrides: dict[str, Any] | None,
) -> dict[str, Any]:
    """Merge `overrides` over `base` (or §5.4 defaults if `base` is None),
    force `task_type`, validate, and return a plain JSON-able dict.

    Raises pydantic.ValidationError (-> 422) on any constraint violation,
    including unknown keys (extra="forbid").
    """
    merged: dict[str, Any] = dict(base) if base is not None else default_params(task_type)
    if overrides:
        # If the key_map isn't part of the override but task_type changes,
        # fall back to the new task type's default key_map (different length).
        if "task_type" in overrides and overrides["task_type"] != merged.get("task_type"):
            if "key_map" not in overrides:
                merged["key_map"] = default_params(overrides["task_type"])["key_map"]
        merged.update(overrides)
    merged["task_type"] = task_type
    validated = TaskParams.model_validate(merged)
    return validated.model_dump(mode="json")
