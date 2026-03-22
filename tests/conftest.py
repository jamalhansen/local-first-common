import os
import pytest


@pytest.fixture(autouse=True, scope="session")
def _isolate_tracking_db(tmp_path_factory):
    """Redirect the tracking DB to a temp path so tests never write to the real DB."""
    db = tmp_path_factory.mktemp("tracking") / "test_tracking.duckdb"
    os.environ["LOCAL_FIRST_TRACKING_DB"] = str(db)
    yield
    os.environ.pop("LOCAL_FIRST_TRACKING_DB", None)

