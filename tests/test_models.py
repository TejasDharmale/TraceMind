import json
from datetime import timezone

from tracemind.models import Status, Trace


def test_valid_success_trace():
    trace = Trace(
        function_name="price",
        function_module="shop.pricing",
        status=Status.SUCCESS,
        app_version="v1",
        duration_ms=1.5,
        args=[100],
        return_value=90,
    )

    assert trace.status is Status.SUCCESS
    assert trace.return_value == 90
    assert trace.error_type is None
    assert trace.error_message is None
    assert trace.error_traceback is None
    assert len(trace.id) == 32
    assert trace.started_at.tzinfo is not None
    assert trace.started_at.utcoffset() == timezone.utc.utcoffset(None)
    assert trace.metadata == {}


def test_error_trace_from_exception():
    try:
        1 / 0
    except ZeroDivisionError as error:
        trace = Trace(
            function_name="divide",
            function_module="shop.math",
            status=Status.ERROR,
            app_version="v1",
            duration_ms=0.2,
            **Trace.error_fields(error),
        )

    assert trace.status is Status.ERROR
    assert trace.error_type == "ZeroDivisionError"
    assert "division by zero" in trace.error_message
    assert "ZeroDivisionError" in trace.error_traceback
    assert trace.return_value is None


def test_to_dict_from_dict_round_trip():
    trace = Trace(
        function_name="price",
        function_module="shop.pricing",
        status=Status.SUCCESS,
        app_version="v2",
        duration_ms=3.25,
        args=[100, {"coupon": "SAVE10"}],
        kwargs={"region": "EU"},
        return_value={"total": 90.0},
        metadata={"env": "test"},
    )

    data = trace.to_dict()
    restored = Trace.from_dict(json.loads(json.dumps(data)))  # must survive JSON

    assert data["status"] == "success"
    assert restored == trace
