"""TraceMind demo: run a pricing function as "v1" and "v2" and see what changed.

Run it twice, once per version (from the project root):

    Windows PowerShell:
        $env:PYTHONPATH = "sdk"
        $env:TRACEMIND_APP_VERSION = "v1"; python examples/demo.py
        $env:TRACEMIND_APP_VERSION = "v2"; python examples/demo.py

    macOS / Linux:
        PYTHONPATH=sdk TRACEMIND_APP_VERSION=v1 python examples/demo.py
        PYTHONPATH=sdk TRACEMIND_APP_VERSION=v2 python examples/demo.py

(Skip PYTHONPATH if you ran `pip install -e .`.)

The function below behaves differently in v2, the way a "small cleanup"
might in a real app. TraceMind has no comparison engine yet, so this demo
saves each run to a JSON file and does a tiny side-by-side check itself.

After the v2 run, the differences are sent to a local Ollama model for a
plain language explanation. Ollama is optional: if it is not running, the
demo still finishes and tells you why there is no explanation.
Pick the model with TRACEMIND_LLM_MODEL (default: mistral).
"""
import json
import os
import sys
from pathlib import Path

# Allow running this example directly from a checkout without requiring
# PYTHONPATH to be configured in the editor or shell.
sys.path.insert(0, str(Path(__file__).parent.parent / "sdk"))
import tracemind  # type: ignore[import-not-found]
from tracemind.llm_client import (  # type: ignore[import-not-found]
    DEFAULT_MODEL,
    OllamaError,
    explain_changes,
)

VERSION = os.environ.get("TRACEMIND_APP_VERSION", "unknown")
OUTPUT_DIR = Path(__file__).parent / "demo_output"


@tracemind.track
def final_price(price, discount_percent):
    """Price after a percentage discount, in dollars."""
    if VERSION == "v2":
        # v2 "tidy up": adds validation and truncates cents instead of rounding.
        if discount_percent > 100:
            raise ValueError("discount cannot be more than 100%")
        return int(price * (100 - discount_percent)) / 100
    return round(price * (100 - discount_percent) / 100, 2)


def run_workload():
    """A few sample calls, like a test suite or a day of traffic."""
    cases = [(100, 10), (12.34, 15), (50, 0), (20, 150)]
    for price, discount in cases:
        try:
            final_price(price, discount)
        except ValueError:
            pass  # the app's own error handling would go here


def save(traces):
    OUTPUT_DIR.mkdir(exist_ok=True)
    path = OUTPUT_DIR / f"traces_{VERSION}.json"
    path.write_text(json.dumps([t.to_dict() for t in traces], indent=2))
    return path


def describe(trace):
    if trace["status"] == "error":
        return f"ERROR {trace['error_type']}: {trace['error_message']}"
    return str(trace["return_value"])


def compare(old_version, new_version):
    """A tiny stand-in for the planned comparison engine."""
    def load(version):
        path = OUTPUT_DIR / f"traces_{version}.json"
        return {
            (t["function_name"], json.dumps(t["args"])): t
            for t in json.loads(path.read_text())
        }

    old, new = load(old_version), load(new_version)
    print(f"\nWhat changed between {old_version} and {new_version}:")
    changes = []
    for key in sorted(old.keys() & new.keys()):  # sorted: same order every run
        before, after = describe(old[key]), describe(new[key])
        if before != after:
            changes.append(f"{key[0]}{key[1]}: {before} -> {after}")
    for line in changes:
        print(f"  {line}")
    if not changes:
        print("  nothing, behaviour is identical for these inputs")
    return changes


def explain(changes):
    """Ask the local model to explain the changes. Optional: never fatal."""
    model = os.environ.get("TRACEMIND_LLM_MODEL", DEFAULT_MODEL)
    print(f"\nAsking local model '{model}' to explain (this can take a minute)...")
    try:
        print(f"\n{explain_changes(changes)}")
    except OllamaError as error:
        print(f"\n(No AI explanation: {error})")


def main():
    run_workload()
    traces = tracemind.get_records()

    print(f"App version: {VERSION}")
    print(f"Recorded {len(traces)} calls:\n")
    for trace in traces:
        print(f"  {trace.function_name}{tuple(trace.args)} -> "
              f"{describe(trace.to_dict())}  ({trace.duration_ms} ms)")

    print(f"\nSaved to {save(traces)}")

    # Compare automatically once both versions have been run.
    if (OUTPUT_DIR / "traces_v1.json").exists() and (OUTPUT_DIR / "traces_v2.json").exists():
        changes = compare("v1", "v2")
        if changes:
            explain(changes)
    else:
        print("\nRun the other version too, and the differences will be listed.")


if __name__ == "__main__":
    main()
