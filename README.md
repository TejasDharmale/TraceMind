# TraceMind

*Record Python function executions and compare behaviour between application versions.*

[![PyPI](https://img.shields.io/pypi/v/tracemind-regression)](https://pypi.org/project/tracemind-regression/)
[![Python](https://img.shields.io/pypi/pyversions/tracemind-regression)](https://pypi.org/project/tracemind-regression/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE)

TraceMind is a Python SDK that records the inputs, outputs, errors, duration and application version of the functions you decorate. Because every trace carries a version label, you can run two versions of your code against the same inputs and see which functions now behave differently. An optional local LLM (through [Ollama](https://ollama.com)) can explain the differences.

It is aimed at code where a small change can silently alter results, such as pricing, discounts, tax and billing rules.

## Features

- One decorator, `@tracemind.track`, for sync and `async` functions.
- Records arguments, return value, exception details, UTC start time, duration and app version.
- Arguments are snapshotted **before** the call, so a function that mutates its inputs is still recorded correctly.
- Traces are immutable and JSON-safe (`Trace.to_dict()` / `Trace.from_dict()`).
- Bounded output: depth, collection size and string length are capped, cycles are cut, and `NaN`, `bytes` and memory addresses are normalised.
- Never raises into your code. Tracking failures are logged at debug level and your function's result or exception passes through unchanged.
- Optional explanations from a local Ollama model. Nothing leaves your machine.
- No dependencies. Python 3.10+.

## Installation

```shell
pip install "tracemind-regression>=0.1.2"
```

The distribution is named `tracemind-regression`; the import name is `tracemind`.

## Quick start

```python
import tracemind


@tracemind.track
def final_price(price, discount_percent):
    return price - price * discount_percent / 100


@tracemind.track
def divide(a, b):
    return a / b


final_price(200, 10)

try:
    divide(1, 0)
except ZeroDivisionError:
    pass

for trace in tracemind.get_records():
    print(trace.function_name, trace.status.value, trace.args, trace.return_value)
```

```text
final_price success [200, 10] 180.0
divide error [1, 0] None
```

Each record is a `Trace`. `trace.to_dict()` returns plain data:

```python
{
    'id': 'f93833137ec7449fa9f89367e66d737a',
    'schema_version': 1,
    'function_name': 'final_price',
    'function_module': '__main__',
    'args': [200, 10],
    'kwargs': {},
    'return_value': 180.0,
    'status': 'success',
    'error_type': None,
    'error_message': None,
    'error_traceback': None,
    'started_at': '2026-11-19T22:23:02.382133+00:00',
    'duration_ms': 0.003,
    'app_version': 'v1',
    'metadata': {},
}
```

## Usage

### Labelling the application version

Set `TRACEMIND_APP_VERSION` before starting your application. Traces from runs with different labels can then be compared.

```shell
# macOS / Linux
TRACEMIND_APP_VERSION=v1 python app.py

# Windows PowerShell
$env:TRACEMIND_APP_VERSION = "v1"; python app.py
```

Without it, traces are labelled `unknown`.

### Reading and clearing traces

```python
tracemind.get_records()    # list[Trace], a snapshot
tracemind.clear_records()  # empty the in-memory store (useful between tests)
```

### Comparing two versions

The SDK records traces; it does not include a comparison engine. [`examples/demo.py`](examples/demo.py) shows the workflow: run a workload under `v1`, save `trace.to_dict()` to disk, run it under `v2`, then match traces by function name and arguments and diff the results.

```shell
python examples/demo.py   # with TRACEMIND_APP_VERSION=v1, then =v2
```

### Explaining differences with a local LLM

`tracemind.llm_client` sends a list of differences to a local Ollama model and returns a plain language explanation.

```python
from tracemind.llm_client import explain_changes, OllamaError

changes = [
    "final_price[12.34, 15]: 10.49 -> 10.48",
    "final_price[20, 150]: -10.0 -> ERROR ValueError: discount cannot be more than 100%",
]

try:
    print(explain_changes(changes))
except OllamaError as error:
    print(f"No explanation: {error}")
```

`OllamaError` is raised if Ollama is not running, the model is not installed, the request times out, or the reply is unusable. Treat the explanation as optional. The model only sees the lines you pass it, so use it to summarise a diff, not as the source of truth for what changed.

Requires a running Ollama server with a model pulled, for example `ollama pull mistral`.

## Configuration

| Environment variable | Default | Purpose |
|---|---|---|
| `TRACEMIND_APP_VERSION` | `unknown` | Version label stored on every trace |
| `TRACEMIND_LLM_MODEL` | `mistral` | Ollama model used by `explain_changes` |
| `OLLAMA_HOST` | `http://localhost:11434` | Ollama server address |

## The `Trace` record

| Field | Type | Description |
|---|---|---|
| `id` | `str` | UUID4 hex, generated automatically |
| `schema_version` | `int` | Format version of the record |
| `function_name` | `str` | `__qualname__` of the decorated function |
| `function_module` | `str` | `__module__` of the decorated function |
| `args` / `kwargs` | `list` / `dict` | Arguments as they were before the call, JSON-safe |
| `return_value` | `Any` | JSON-safe return value, `None` on error |
| `status` | `Status` | `Status.SUCCESS` or `Status.ERROR` |
| `error_type` / `error_message` / `error_traceback` | `str \| None` | Set only when `status` is `ERROR` |
| `started_at` | `datetime` | Timezone-aware, UTC |
| `duration_ms` | `float` | Measured with `time.perf_counter()` |
| `app_version` | `str` | Value of `TRACEMIND_APP_VERSION` |
| `metadata` | `dict` | Free-form extra data |

`Trace` is a frozen dataclass and validates itself on creation: `started_at` must be timezone-aware, `duration_ms` cannot be negative, and success and error fields cannot be mixed.

## How it works

```text
@track  ->  tracker.py    observes the call: inputs, output, timing, errors
        ->  serialize.py  makes values JSON-safe and size-limited
        ->  models.py     builds an immutable Trace
        ->  collector.py  stores traces (thread-safe, in memory)
```

| Module | Responsibility |
|---|---|
| `tracker.py` | The `@track` decorator |
| `models.py` | `Trace` and `Status` |
| `serialize.py` | `to_jsonable()`: bounded, strict-JSON conversion |
| `collector.py` | `Collector` with an optional `max_records` cap |
| `llm_client.py` | Ollama client built on `urllib` |

Serialisation limits: depth 6, 50 items per collection, 1,000 characters per string, 8,000 characters per traceback.

## Limitations

- Traces are stored in memory only and are lost when the process exits. Persist them with `to_dict()` if you need them across runs.
- Arguments and return values are recorded as they are. There is no built-in redaction, so do not decorate functions that handle secrets or personal data.
- Only `Exception` is recorded. `BaseException` subclasses such as `asyncio.CancelledError` are not.
- For methods, `self` is recorded as `args[0]` and serialised like any other object.

## Development

```shell
git clone https://github.com/TejasDharmale/TraceMind.git
cd TraceMind
python -m venv .venv
# activate the environment, then:
pip install -e .
pip install pytest
python -m pytest
```

Contributions are welcome. Please open an issue before starting larger changes.

## License

[MIT](LICENSE)
