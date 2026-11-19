from __future__ import annotations

import inspect
import logging
import os
import time
from datetime import datetime, timezone
from functools import wraps
from typing import Any, Callable

from .collector import collect
from .models import Status, Trace
from .serialize import to_jsonable

logger = logging.getLogger("tracemind")

# Temporary home for the version label until config.py exists.
APP_VERSION = os.environ.get("TRACEMIND_APP_VERSION", "unknown")


def _snapshot(args: tuple[Any, ...], kwargs: dict[str, Any]) -> tuple[list[Any], dict[str, Any]]:
    """Serialize inputs BEFORE the call, so later mutation cannot change them."""
    try:
        return to_jsonable(list(args)), to_jsonable(kwargs)
    except Exception:
        logger.debug("tracemind: could not snapshot inputs", exc_info=True)
        return [], {}


def track(func: Callable[..., Any]) -> Callable[..., Any]:
    """Record execution time, inputs, outputs, and failures for ``func``."""

    def save(started_at: datetime, start: float, args: list[Any], kwargs: dict[str, Any],
             result: Any = None, error: BaseException | None = None) -> None:
        # Take the duration first so serialization time is not counted.
        duration_ms = round((time.perf_counter() - start) * 1000, 3)
        try:
            common = dict(
                function_name=func.__qualname__,
                function_module=func.__module__,
                app_version=APP_VERSION,
                duration_ms=duration_ms,
                args=args,
                kwargs=kwargs,
                started_at=started_at,
            )
            if error is None:
                trace = Trace(status=Status.SUCCESS,
                              return_value=to_jsonable(result), **common)
            else:
                trace = Trace(status=Status.ERROR,
                              **Trace.error_fields(error), **common)
            collect(trace)
        except Exception:
            # Tracking must never break the user's app.
            logger.debug("tracemind: failed to record trace", exc_info=True)

    if inspect.iscoroutinefunction(func):
        @wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            args_snap, kwargs_snap = _snapshot(args, kwargs)
            started_at = datetime.now(timezone.utc)
            start = time.perf_counter()
            try:
                result = await func(*args, **kwargs)
            except Exception as error:
                save(started_at, start, args_snap, kwargs_snap, error=error)
                raise
            save(started_at, start, args_snap, kwargs_snap, result=result)
            return result

        return async_wrapper

    @wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        args_snap, kwargs_snap = _snapshot(args, kwargs)
        started_at = datetime.now(timezone.utc)
        start = time.perf_counter()
        try:
            result = func(*args, **kwargs)
        except Exception as error:
            save(started_at, start, args_snap, kwargs_snap, error=error)
            raise
        save(started_at, start, args_snap, kwargs_snap, result=result)
        return result

    return wrapper
