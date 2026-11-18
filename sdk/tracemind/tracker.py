from __future__ import annotations


import inspect
import threading
import time
from functools import wraps
from typing import Any, Callable


_records: list[dict[str, Any]] = []
_records_lock = threading.Lock()


def _safe_repr(value: Any) -> str:
	try:
		return repr(value)
	except Exception:
		return f"<{type(value).__name__}>"


def _record(event: dict[str, Any]) -> None:
	with _records_lock:
		_records.append(event)


def get_records() -> list[dict[str, Any]]:
	"""Return a snapshot of all tracked endpoint calls."""
	with _records_lock:
		return [record.copy() for record in _records]


def clear_records() -> None:
	"""Remove all recorded endpoint calls."""
	with _records_lock:
		_records.clear()


def track(func: Callable[..., Any]) -> Callable[..., Any]:
	"""Record execution time, inputs, outputs, and failures for ``func``."""

	def save(start: float, args: tuple[Any, ...], kwargs: dict[str, Any],
			 result: Any = None, error: BaseException | None = None) -> None:
		event = {
			"endpoint": f"{func.__module__}.{func.__qualname__}",
			"timestamp": time.time(),
			"duration_ms": round((time.perf_counter() - start) * 1000, 3),
			"args": _safe_repr(args),
			"kwargs": _safe_repr(kwargs),
			"status": "error" if error else "success",
			"result": _safe_repr(result) if error is None else None,
			"error": _safe_repr(error) if error else None,
		}
		_record(event)

	if inspect.iscoroutinefunction(func):
		@wraps(func)
		async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
			start = time.perf_counter()
			try:
				result = await func(*args, **kwargs)
			except Exception as error:
				save(start, args, kwargs, error=error)
				raise
			save(start, args, kwargs, result=result)
			return result

		return async_wrapper

	@wraps(func)
	def wrapper(*args: Any, **kwargs: Any) -> Any:
		start = time.perf_counter()
		try:
			result = func(*args, **kwargs)
		except Exception as error:
			save(start, args, kwargs, error=error)
			raise
		save(start, args, kwargs, result=result)
		return result

	return wrapper
