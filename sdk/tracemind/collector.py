from __future__ import annotations

from collections import deque
from threading import RLock
from typing import Iterator

from .models import Trace


class Collector:

    def __init__(self, max_records: int | None = None) -> None:
        if max_records is not None and max_records <= 0:
            raise ValueError("max_records must be a positive integer or None")
        self._records: deque[Trace] = deque(maxlen=max_records)
        self._lock = RLock()

    def collect(self, record: Trace) -> Trace:
        """Store *record* and return it for convenient tracker integration."""
        with self._lock:
            self._records.append(record)
        return record

    def records(self) -> list[Trace]:
        """Return a snapshot of all collected records."""
        with self._lock:
            return list(self._records)

    def clear(self) -> None:
        """Remove all collected records."""
        with self._lock:
            self._records.clear()

    def __iter__(self) -> Iterator[Trace]:
        return iter(self.records())

    def __len__(self) -> int:
        with self._lock:
            return len(self._records)


collector = Collector()


def collect(record: Trace) -> Trace:
    """Store a trace in the process-wide collector."""
    return collector.collect(record)


def get_records() -> list[Trace]:
    """Return traces stored in the process-wide collector."""
    return collector.records()


def clear_records() -> None:
    """Remove all traces from the process-wide collector."""
    collector.clear()
