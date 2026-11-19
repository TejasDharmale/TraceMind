import pytest

from tracemind import clear_records


@pytest.fixture(autouse=True)
def _clean_collector():
    """Start and finish every test with an empty shared collector."""
    clear_records()
    yield
    clear_records()
