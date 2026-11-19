"""Convert arbitrary Python values into strict, bounded, JSON-safe data.

Guarantees for the output of :func:`to_jsonable`:
  * only None/bool/int/finite float/str/list/dict (valid for Postgres JSONB)
  * no NUL characters (rejected by Postgres)
  * no memory addresses in reprs (identical behaviour -> identical output)
  * bounded depth, collection size and string length; cycles are cut
"""
from __future__ import annotations

import dataclasses
import json
import math
import re
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Any
from uuid import UUID

_ADDRESS = re.compile(r" at 0x[0-9a-fA-F]+")


def clean_text(text: str, max_len: int = 1000) -> str:
    """Strip NULs and truncate, marking how much was dropped."""
    text = text.replace("\x00", "")
    if len(text) > max_len:
        text = f"{text[:max_len]}...[truncated {len(text) - max_len} chars]"
    return text


def safe_repr(value: Any, max_len: int = 1000) -> str:
    try:
        text = repr(value)
    except Exception:
        text = f"<{type(value).__name__}>"
    return clean_text(_ADDRESS.sub("", text), max_len)


def to_jsonable(
    value: Any,
    *,
    max_depth: int = 6,
    max_items: int = 50,
    max_str: int = 1000,
) -> Any:
    # ids of containers on the current path (cycle guard)
    active: set[int] = set()

    def placeholder(v: Any, **extra: Any) -> dict[str, Any]:
        return {"__type__": type(v).__qualname__, **extra}

    def convert(v: Any, depth: int) -> Any:
        if v is None or isinstance(v, bool):
            return v
        if isinstance(v, Enum):  # before str/int: str-mixin enums are also str
            return convert(v.value, depth)
        if isinstance(v, int):
            return v
        if isinstance(v, float):
            return v if math.isfinite(v) else placeholder(v, repr=repr(v))
        if isinstance(v, str):
            return clean_text(v, max_str)
        if isinstance(v, (bytes, bytearray)):
            return placeholder(v, len=len(v), preview=bytes(v[:16]).hex())
        if isinstance(v, (datetime, date)):
            return v.isoformat()
        if isinstance(v, (UUID, Decimal)):
            return str(v)

        if depth >= max_depth:
            return placeholder(v, repr="<max depth>")
        if id(v) in active:
            return placeholder(v, repr="<cycle>")

        active.add(id(v))
        try:
            if isinstance(v, dict):
                out: dict[str, Any] = {}
                for i, (k, item) in enumerate(v.items()):
                    if i >= max_items:
                        out["__truncated__"] = len(v) - max_items
                        break
                    key = k if isinstance(k, str) else safe_repr(k, max_str)
                    out[clean_text(key, max_str)] = convert(item, depth + 1)
                return out
            if isinstance(v, (list, tuple)):
                items = [convert(x, depth + 1) for x in v[:max_items]]
                if len(v) > max_items:
                    items.append({"__truncated__": len(v) - max_items})
                return items
            if isinstance(v, (set, frozenset)):
                if len(v) > max_items:
                    return placeholder(v, len=len(v))
                items = [convert(x, depth + 1) for x in v]
                return sorted(items, key=lambda x: json.dumps(x, sort_keys=True))
            if dataclasses.is_dataclass(v) and not isinstance(v, type):
                return {
                    "__type__": type(v).__qualname__,
                    **{
                        f.name: convert(getattr(v, f.name, None), depth + 1)
                        for f in dataclasses.fields(v)[:max_items]
                    },
                }
        finally:
            active.discard(id(v))

        return placeholder(v, repr=safe_repr(v, max_str))

    return convert(value, 0)

# basically this code takes a python object and converts it into a JSON-safe representation, ensuring that the output is bounded in depth, size, and string length, while also handling cycles and special types like enums, dataclasses, and UUIDs.
# so that it is compatible with Postgres JSONB and other strict JSON consumers.
