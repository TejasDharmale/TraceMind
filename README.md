<div align="center">

# TraceMind

**Add one decorator. Run two versions. See exactly what behaviour changed.**

[![PyPI](https://img.shields.io/pypi/v/tracemind-regression)](https://pypi.org/project/tracemind-regression/)
[![Python](https://img.shields.io/pypi/pyversions/tracemind-regression)](https://pypi.org/project/tracemind-regression/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE)

</div>

---

## What is TraceMind? (the plain English version)

Imagine you take a photo of your kitchen every day. If something goes missing, you can compare today's photo with yesterday's and spot it straight away.

**TraceMind does the same thing for software.** It quietly records what your functions do: what went in, what came out, how long it took, and whether it failed. Later, you can line up what version 1 of your app did next to what version 2 did, and see what changed.

That matters because software can break **without anyone noticing**. A small edit to a discount rule, a tax calculation or a billing function can pass every test and still give customers different answers. TraceMind is built to catch that.

> **Status:** TraceMind is young. Recording works today. Comparing versions and AI explanations are being built. See [What works today](#what-works-today).

---

## A real example

Your shop has a function that works out the price after a discount:

```python
def final_price(price, discount_percent):
    return price - price * discount_percent / 100
```

A teammate "tidies it up" and accidentally changes the rounding. Your tests still pass, because nobody wrote a test for that exact case. But now some customers are charged a few cents more. Nobody notices for weeks.

With TraceMind, both versions leave a record of what they returned for the same inputs. Comparing the two records shows the difference **before** customers do.

---

## What works today

| Feature | Status |
|---|---|
| Record function calls: inputs, result, errors, timing, app version | Available |
| Works with normal and `async` functions | Available |
| Safe by default: big or odd values are shortened, a tracking problem never breaks your app | Available |
| Read the recorded traces from Python, or turn them into plain data (JSON friendly) | Available |
| Save traces to disk, so version 1 and version 2 can be run separately | Planned |
| Compare two versions and list what changed | Planned |
| Plain language explanations from a local AI model (through [Ollama](https://ollama.com)) | Planned |
| Store traces in PostgreSQL | Planned |

These are honest statuses. The "Planned" rows are not built yet.

---

## Quick start

### 1. Install

```bash
pip install "tracemind-regression>=0.1.2"
```

You need Python 3.10 or newer. TraceMind has **no dependencies**, so it will not pull extra packages into your project.

You install `tracemind-regression`, but you import it as `tracemind`.

### 2. Add the decorator

```python
import tracemind


@tracemind.track
def final_price(price, discount_percent):
    return price - price * discount_percent / 100


@tracemind.track
def divide(a, b):
    return a / b
```

Your functions behave exactly as before. Return values are unchanged, and your own errors are raised as usual.

### 3. Call them and look at what was recorded

```python
final_price(200, 10)

try:
    divide(1, 0)
except ZeroDivisionError:
    pass

for trace in tracemind.get_records():
    print(trace.function_name, trace.status.value, trace.args, trace.return_value)
```

Output:

```text
final_price success [200, 10] 180.0
divide error [1, 0] None
```

Each record is a `Trace` object. Call `.to_dict()` to turn it into plain data:

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

### 4. Label your app version

Comparing versions only works if each trace knows which version made it. Set the label with an environment variable before you start your app:

```bash
# macOS / Linux
TRACEMIND_APP_VERSION=v1 python your_app.py

# Windows PowerShell
$env:TRACEMIND_APP_VERSION = "v1"; python your_app.py
```

If you do not set it, traces are labelled `unknown`.

---

## Using TraceMind in your own open source project

1. **Install it** as a development tool, for example with `pip install tracemind-regression`, or add `tracemind-regression>=0.1.2` to your dev requirements.
2. **Pick the functions that matter most.** Good candidates are the ones where a silent change would hurt: pricing, discounts, tax, scoring, parsing, permissions. You do not need to track everything.
3. **Add `@tracemind.track`** above each one. That is the whole change to your code.
4. **Set `TRACEMIND_APP_VERSION`** when you run each release or branch, for example to your version number or git commit.
5. **Run your tests or a sample workload.** The recorded calls become the "photo" of that version's behaviour.
6. **Read the traces** with `tracemind.get_records()`.

Use `tracemind.clear_records()` to empty the store, which is handy between test cases.

> TraceMind keeps traces in memory for now. Saving them to a file and comparing two versions are the next things on the roadmap.

---

## What gets recorded

| Field | What it holds |
|---|---|
| `function_name`, `function_module` | Which function ran |
| `args`, `kwargs` | What it was called with, as they were **before** the call |
| `return_value` | What it returned |
| `status` | `success` or `error` |
| `error_type`, `error_message`, `error_traceback` | What went wrong, if anything |
| `started_at` | When the call started, in UTC |
| `duration_ms` | How long it took, in milliseconds |
| `app_version` | The version label you set |
| `metadata` | A free space for extra notes |
| `id`, `schema_version` | A unique id and the record format version |

Traces are **immutable**. Once a trace is created it describes the past and is not edited.

---

## Safe by default

- **It never breaks your app.** If recording fails for any reason, your function still returns its result. Your own exceptions are always re-raised unchanged.
- **Inputs are saved before your function runs.** If a function changes its own arguments, the trace still shows what it was originally given.
- **Values are kept small and clean.** Long text is shortened, large lists are trimmed, loops in data are cut, and odd values (such as `NaN`, raw bytes or memory addresses) are turned into safe text.
- **Everything stays on your machine.** TraceMind does not send data anywhere.

### Please be careful with sensitive data

Arguments and return values are recorded as they are. **Automatic redaction of secrets (passwords, tokens, personal data) is not built yet.** Until it is, do not decorate functions that receive secrets or personal data.

---

## How it works

```text
Your function (decorated with @track)
        |
   tracker.py      watches the call: inputs, output, timing, errors
        |
   models.py       builds a structured, immutable Trace
        |
   collector.py    stores the traces (in memory for now)
        |
   comparison engine (planned)   compares traces between app versions
        |
   llm_client.py (planned)       asks a local Ollama model to explain the differences
```

Each part has one job, so storage can later move from memory to PostgreSQL without touching the decorator.

---

## Frequently asked questions

**Do I need to know AI or machine learning?**
No. Recording works with plain Python. The AI explanations are planned and will be optional.

**Will it slow down my app?**
The decorator adds a small amount of work to each tracked call, so track the functions that matter, not everything. Planned settings will let you sample calls or turn tracking off.

**Does it send my data to the cloud?**
No. Traces stay in your process. The planned AI explanations use a model running on your own computer through Ollama.

**Is this a replacement for tests?**
No. Tests check what you expected. TraceMind shows what *changed*, including things you did not think to test.

**Does it work with `async` code?**
Yes. `async def` functions are tracked the same way.

---

## Roadmap

- [x] Function execution tracking (`@tracemind.track`)
- [x] Immutable, JSON friendly trace records
- [x] In-memory collector with an optional size limit
- [x] Automated tests
- [ ] Configuration (`config.py`): app version, sampling, size limits, on/off switch
- [ ] Save and load traces
- [ ] Version comparison engine
- [ ] Local AI explanations through Ollama
- [ ] PostgreSQL storage
- [ ] Automatic redaction of sensitive values

---

## Contributing

Contributions, ideas and bug reports are welcome. Please open an issue first for larger changes.

To work on TraceMind itself:

```bash
git clone https://github.com/TejasDharmale/TraceMind.git
cd TraceMind
python -m venv .venv
# activate it, then:
pip install -e .
pip install pytest
python -m pytest
```

The code lives in `sdk/tracemind/`:

| File | Job |
|---|---|
| `tracker.py` | The `@track` decorator |
| `models.py` | The `Trace` record and `Status` |
| `collector.py` | Stores traces |
| `serialize.py` | Makes values safe and small |
| `config.py` | Settings (planned) |

---

## License

MIT. See [LICENSE](LICENSE).
