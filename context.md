# TraceMind: Project Context

Read this before helping with any TraceMind task.

## What TraceMind is

TraceMind is an open source Python SDK that helps developers catch behaviour changes in their software before those changes reach customers.

A developer adds a decorator (`@tracemind.track`) to the functions they care about. TraceMind records every call: inputs, output, errors, timing, and which app version ran it. Developers then run version A and version B of their app, and TraceMind shows which functions now behave differently. A local LLM (through Ollama) can explain what changed and why it might matter.

**Initial target users:** Python based SaaS companies whose business logic changes often (pricing, discounts, tax, billing rules), where a small code change can silently change results.

**One line pitch:** "Add one decorator, run two versions, see exactly what behaviour changed."

## How I work on this project

- I write the code myself. I use AI for guidance, explanations, design discussion, and code review.
- Do not write full files or complete solutions unless I explicitly ask for code.
- When reviewing my code: point out issues, explain why they matter, and suggest direction. Don't rewrite the whole file.
- Prefer small, testable steps. Tell me the next concrete step at the end.
- Keep explanations clear and practical. I'm comfortable with Python, so skip beginner basics unless I ask.
- Do not use em dashes or en dashes in your writing.

## Architecture

Data flow:

```
User's function (decorated with @track)
        |
   tracker.py      watches the call: inputs, output, timing, errors
        |
   models.py       builds a structured, immutable Trace object
        |
   collector.py    stores Trace objects (in memory for now)
        |
   comparison engine (planned)   compares traces between app versions
        |
   llm_client.py (planned)       asks a local Ollama model to explain differences
```

Each module has one responsibility. The tracker observes, the model defines structure, the collector stores. This lets storage be swapped (for example, in memory to PostgreSQL) without touching the decorator logic.

## Package layout

```
sdk/
  tracemind/
    __init__.py      public API only (track, get_records, clear_records)
    tracker.py       the @track decorator
    models.py        Trace dataclass and Status enum
    collector.py     Collector class plus a shared module level instance
    serialize.py     helpers like clean_text for safe, size limited values
    config.py        configuration (planned)
    llm_client.py    Ollama communication (planned)
```

Install locally with `pip install -e .` from the project root.

## Module details

### models.py (written)

- `Status`: a `str` Enum with `SUCCESS` and `ERROR`.
- `Trace`: a `@dataclass(frozen=True, slots=True)` representing one function execution.
  - Required fields: `function_name`, `function_module`, `status`, `app_version`, `duration_ms`.
  - Optional fields: `args`, `kwargs`, `return_value`, `error_type`, `error_message`, `error_traceback`, `started_at` (UTC, timezone aware), `metadata`, `id` (uuid hex, auto), `schema_version` (auto).
  - `__post_init__` validates: status normalised to the enum, `started_at` must be timezone aware and is converted to UTC, duration cannot be negative, success traces have no error fields, error traces need `error_type` and have no return value.
  - `Trace.error_fields(exception)` builds the `error_*` keyword arguments from an exception, cleaned and truncated.
  - `to_dict()` and `from_dict()` convert to and from plain dicts whose keys match future database columns.
- Constants: `SCHEMA_VERSION = 1`, `MAX_TRACEBACK_CHARS = 8000`.

Known follow ups: frozen is shallow (args, kwargs, metadata lists and dicts can still be mutated); `to_dict()` is only JSON safe if the tracker serializes args and return values first; consider including the module in `error_type` for non built in exceptions; NaN durations are not rejected yet.

### collector.py (written, being revised)

- `Collector` class holding records in a list, protected by a lock for thread safety.
- Methods: `collect(record)` (returns the record), `records()` (returns a copy), `clear()`, `__len__`, `__iter__` (iterates over a snapshot).
- A shared module level instance `collector`, plus module level `collect()` and `get_records()` shortcuts.

Planned fixes: type records as `Trace` instead of `Any`; remove duplicate alias names (`add`, `get_records` method); add a module level `clear_records()` to match `__init__.py`; make sure the file is named `collector.py`; return type of `__iter__` should be `Iterator`; consider an optional maximum size (for example a `deque` with `maxlen`); use 4 spaces, not tabs.

Later: lookups such as traces by function name or by app version, for the comparison engine.

### tracker.py (exists, being updated)

The `@track` decorator. It should record the real start time, measure duration with a high resolution timer, serialize inputs and outputs safely through `serialize.py`, build a `Trace` (using `Trace.error_fields()` on exceptions, then re raise the exception), and pass it to `collect()`.

### Planned

- **Comparison engine:** groups traces by function and app version, then detects changed outputs, new errors, and large timing changes.
- **llm_client.py:** sends trace differences to a local Ollama model for plain language explanations.
- **Persistent storage:** PostgreSQL, using `to_dict()` keys as columns and `schema_version` for migrations.
- **config.py:** app version label, sampling, size limits, enable or disable tracking.

## Design principles

1. One responsibility per module.
2. Traces are immutable records of the past.
3. Public API stays small; don't expose internals in `__init__.py`.
4. Safe by default: limit sizes, never crash the user's app because tracking failed, be careful with sensitive argument values.
5. Every trace carries an `app_version`, because comparison between versions is the core feature.
6. Build the smallest end to end version first, then add storage, comparison, and LLM layers one at a time.

## Current status and next steps

1. Fix the collector issues listed above.
2. Connect `tracker.py` so it builds a `Trace` and calls `collect()`.
3. Write tests with pytest: a valid success trace, an error trace via `Trace.error_fields()`, a `to_dict`/`from_dict` round trip, and one end to end test (decorate, call, check `get_records()`).
4. Then start the comparison engine.

## Tech stack

Python 3.10 or newer, standard library dataclasses and enums, pytest for tests, Ollama for the local LLM, PostgreSQL planned for storage.