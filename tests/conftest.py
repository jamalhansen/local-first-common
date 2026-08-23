import os
import pytest


@pytest.fixture(autouse=True, scope="session")
def _isolate_tracking_db(tmp_path_factory):
    """Redirect the tracking DB to a temp path so tests never write to the real DB."""
    db = tmp_path_factory.mktemp("tracking") / "test_tracking.duckdb"
    os.environ["LOCAL_FIRST_TRACKING_DB"] = str(db)
    yield
    os.environ.pop("LOCAL_FIRST_TRACKING_DB", None)


@pytest.fixture(autouse=True)
def no_real_network(monkeypatch, request):
    """Fail loudly rather than silently reaching the network.

    This library wraps several live APIs (Readwise, article fetching, LLM
    providers) that every local-first tool depends on. Downstream, a test with
    an incomplete mock reached the real Readwise account through content-discovery-
    agent on 2026-08-23 because a routing flag defaulted to whatever the live
    config happened to say. Blocking `requests` here catches the same class of
    mistake at the source, for every tool that imports this package's test
    utilities.

    Any test that genuinely needs an HTTP call marks itself with
    `@pytest.mark.allow_network`.
    """
    if request.node.get_closest_marker("allow_network"):
        return

    def blocked(*args, **kwargs):
        raise AssertionError(
            "A test attempted a real HTTP request. Patch the caller, or mark the "
            "test with @pytest.mark.allow_network if the call is intended."
        )

    import requests

    for verb in ("get", "post", "patch", "put", "delete", "request"):
        monkeypatch.setattr(requests, verb, blocked, raising=False)

