"""Shared test setup.

1. saucedemo.com marks elements with data-test="...", but Playwright's get_by_test_id()
   looks for data-testid by default. Tell Playwright which attribute to use.
2. When a test fails, save the page's URL and HTML, so the triage agent can see the
   page instead of guessing from the error message alone.
"""
import hashlib
import re
from pathlib import Path

import pytest

SNAPSHOTS = Path(__file__).resolve().parent.parent / "test-results" / "dom"


def snapshot_path(nodeid: str) -> Path:
    # Same naming rule as agent/graph.py, so the agent can find the file.
    return SNAPSHOTS / (hashlib.md5(nodeid.encode()).hexdigest()[:16] + ".txt")


@pytest.fixture(scope="session", autouse=True)
def _use_data_test_attribute(playwright):
    playwright.selectors.set_test_id_attribute("data-test")


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    report = outcome.get_result()
    setattr(item, f"rep_{report.when}", report)


@pytest.fixture(autouse=True)
def _save_page_on_failure(request):
    # Get the page during setup: fixtures can't be requested during teardown.
    page = request.getfixturevalue("page") if "page" in request.fixturenames else None
    yield
    if page is None:
        return
    report = getattr(request.node, "rep_call", None) or getattr(request.node, "rep_setup", None)
    if not (report and report.failed):
        return
    try:
        html = page.content()
    except Exception as exc:  # page already closed or crashed
        html = f"(could not read page: {exc})"
    # Drop scripts, styles and inline SVG; keep the structure the triage needs.
    html = re.sub(r"<(script|style|svg)\b.*?</\1>", "", html, flags=re.S | re.I)
    html = re.sub(r"\s+", " ", html)
    SNAPSHOTS.mkdir(parents=True, exist_ok=True)
    snapshot_path(request.node.nodeid).write_text(f"URL: {page.url}\n\nHTML:\n{html}")
