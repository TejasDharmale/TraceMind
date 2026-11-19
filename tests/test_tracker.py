import pytest

import tracemind  # pyright: ignore[reportMissingImports]
from tracemind.models import Status  # pyright: ignore[reportMissingImports]


def test_decorate_call_and_get_records():
    @tracemind.track
    def apply_discount(price, percent=10):
        return price - price * percent / 100

    result = apply_discount(200, percent=25)

    assert result == 150  # the decorated function still behaves normally

    records = tracemind.get_records()
    assert len(records) == 1

    trace = records[0]
    assert trace.function_name.endswith("apply_discount")
    assert trace.function_module == __name__
    assert trace.status is Status.SUCCESS
    assert trace.args == [200]
    assert trace.kwargs == {"percent": 25}
    assert trace.return_value == 150
    assert trace.duration_ms >= 0
    assert trace.started_at.tzinfo is not None


def test_error_is_recorded_and_reraised():
    @tracemind.track
    def charge(amount):
        raise ValueError("card declined")

    # the user's own exception must still reach the caller, unchanged
    with pytest.raises(ValueError, match="card declined"):
        charge(50)

    records = tracemind.get_records()
    assert len(records) == 1

    trace = records[0]
    assert trace.status is Status.ERROR
    assert trace.error_type == "ValueError"
    assert trace.error_message == "card declined"
    assert "ValueError" in trace.error_traceback
    assert trace.return_value is None
    assert trace.args == [50]  # inputs are still recorded on failure


def test_inputs_are_snapshotted_before_the_call():
    @tracemind.track
    def add_item(items, extra):
        items.append(99)  # the function mutates its own arguments
        extra["seen"] = True
        return len(items)

    items = [1]
    extra = {"seen": False}

    result = add_item(items, extra=extra)

    # the function really did mutate the caller's objects...
    assert result == 2
    assert items == [1, 99]
    assert extra == {"seen": True}

    # ...but the trace holds what the function was CALLED with
    trace = tracemind.get_records()[0]
    assert trace.args == [[1]]
    assert trace.kwargs == {"extra": {"seen": False}}
    assert trace.return_value == 2
