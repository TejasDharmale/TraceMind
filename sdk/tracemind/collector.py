"""Storage for records produced by the TraceMind tracker."""

from __future__ import annotations

from threading import RLock
from typing import Any, Iterable


class Collector:
	"""Collect execution records in memory until they are requested."""

	def __init__(self) -> None:
		self._records: list[Any] = []
		self._lock = RLock()

	def collect(self, record: Any) -> Any:
		"""Store *record* and return it for convenient tracker integration."""
		with self._lock:
			self._records.append(record)
		return record

	add = collect

	def records(self) -> list[Any]:
		"""Return a snapshot of all collected records."""
		with self._lock:
			return list(self._records)

	get_records = records

	def __iter__(self) -> Iterable[Any]:
		return iter(self.records())

	def clear(self) -> None:
		"""Remove all collected records."""
		with self._lock:
			self._records.clear()

	def __len__(self) -> int:
		with self._lock:
			return len(self._records)


collector = Collector()


def collect(record: Any) -> Any:
	"""Store a record in the process-wide collector."""
	return collector.collect(record)


def get_records() -> list[Any]:
	"""Return records stored in the process-wide collector."""
	return collector.records()
