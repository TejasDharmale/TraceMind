from __future__ import annotations

import traceback as _traceback
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4

from .serialize import clean_text

SCHEMA_VERSION = 1
MAX_TRACEBACK_CHARS = 8000


class Status(str, Enum):
    SUCCESS = "success"
    ERROR = "error"


def _new_id() -> str:
    return uuid4().hex


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True, slots=True)
class Trace:
    """One recorded function execution. Immutable once created."""

    function_name: str
    function_module: str
    status: Status
    app_version: str
    duration_ms: float
    args: list[Any] = field(default_factory=list)
    kwargs: dict[str, Any] = field(default_factory=dict)
    return_value: Any = None  # always None when status is ERROR
    error_type: str | None = None
    error_message: str | None = None
    error_traceback: str | None = None
    # Pass the real call-start time from the wrapper; the default is for tests.
    started_at: datetime = field(default_factory=_utc_now)
    metadata: dict[str, Any] = field(default_factory=dict)
    id: str = field(default_factory=_new_id)
    schema_version: int = SCHEMA_VERSION

    def __post_init__(self) -> None:
        # frozen=True, so normalisation goes through object.__setattr__
        object.__setattr__(self, "status", Status(self.status))

        if self.started_at.tzinfo is None or self.started_at.utcoffset() is None:
            raise ValueError("started_at must be timezone-aware (use UTC)")
        object.__setattr__(self, "started_at",
                           self.started_at.astimezone(timezone.utc))

        if self.duration_ms < 0:
            raise ValueError("duration_ms must be >= 0")

        error_fields = (self.error_type, self.error_message,
                        self.error_traceback)
        if self.status is Status.SUCCESS and any(f is not None for f in error_fields):
            raise ValueError(
                "error fields must be None when status is SUCCESS")
        if self.status is Status.ERROR:
            if self.error_type is None:
                raise ValueError("error_type is required when status is ERROR")
            if self.return_value is not None:
                raise ValueError(
                    "return_value must be None when status is ERROR")

    @staticmethod
    def error_fields(error: BaseException) -> dict[str, str]:
        """Build the error_* keyword arguments from an exception."""
        tb = "".join(
            _traceback.format_exception(
                type(error), error, error.__traceback__)
        )
        return {
            "error_type": type(error).__qualname__,
            "error_message": clean_text(str(error), 2000),
            "error_traceback": clean_text(tb, MAX_TRACEBACK_CHARS),
        }

    def to_dict(self) -> dict[str, Any]:
        """JSON-safe dict whose keys match the future database columns."""
        return {
            "id": self.id,
            "schema_version": self.schema_version,
            "function_name": self.function_name,
            "function_module": self.function_module,
            "args": self.args,
            "kwargs": self.kwargs,
            "return_value": self.return_value,
            "status": self.status.value,
            "error_type": self.error_type,
            "error_message": self.error_message,
            "error_traceback": self.error_traceback,
            "started_at": self.started_at.isoformat(),
            "duration_ms": self.duration_ms,
            "app_version": self.app_version,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Trace:
        data = dict(data)
        data["started_at"] = datetime.fromisoformat(data["started_at"])
        return cls(**data)
