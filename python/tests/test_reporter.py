import json
import types
from typing import Any, cast

from evalforge import reporter
from evalforge.reporter import RegressionTracker, save_html, save_json, to_html, to_json
from evalforge.test_case import SuiteResult, TestResult


def _suite() -> SuiteResult:
    return SuiteResult(
        suite_name="demo",
        results=[
            TestResult(test_case_id="a", passed=True, score=1.0, actual_output="ok"),
            TestResult(test_case_id="b", passed=False, score=0.0, actual_output="no"),
        ],
        started_at=1.0,
        finished_at=2.0,
    )


def test_json_and_html_reporters(tmp_path):
    suite = _suite()
    payload = json.loads(to_json(suite))
    assert payload["suite_name"] == "demo"
    assert payload["total"] == 2

    html = to_html(suite)
    assert "EvalForge" in html
    assert "demo" in html

    json_path = save_json(suite, tmp_path / "out.json")
    html_path = save_html(suite, tmp_path / "out.html")
    assert json_path.exists()
    assert html_path.exists()


def test_plain_cli_report(capsys, monkeypatch):
    monkeypatch.setattr(reporter, "_rich_report", lambda *_args, **_kwargs: (_ for _ in ()).throw(ImportError()))
    reporter.print_report(_suite())
    output = capsys.readouterr().out
    assert "EvalForge" in output
    assert "passed" in output


def test_plain_report_with_latency(capsys):
    suite = SuiteResult(
        suite_name="lat",
        results=[TestResult(test_case_id="a", passed=True, score=1.0, latency_ms=12)],
    )
    reporter._plain_report(suite, show_details=False)
    output = capsys.readouterr().out
    assert "Avg latency" in output


def test_regression_tracker_detects_regressions(tmp_path):
    tracker = RegressionTracker(tmp_path / "history.jsonl")
    first = SuiteResult(
        suite_name="demo",
        results=[TestResult(test_case_id="x", passed=True, score=1.0)],
    )
    second = SuiteResult(
        suite_name="demo",
        results=[TestResult(test_case_id="x", passed=False, score=0.0)],
    )
    assert tracker.compare_and_save(first) == []
    assert tracker.compare_and_save(second) == ["x"]


def test_html_edge_cases_and_tracker_invalid_lines(tmp_path):
    empty_suite = SuiteResult(suite_name="empty", results=[])
    html_empty = to_html(empty_suite)
    assert "0.0%" in html_empty

    all_fail = SuiteResult(
        suite_name="all-fail",
        results=[TestResult(test_case_id="f", passed=False, score=0.0, actual_output="bad")],
    )
    html_fail = to_html(all_fail)
    assert "badge fail" in html_fail

    all_pass = SuiteResult(
        suite_name="all-pass",
        results=[TestResult(test_case_id="p", passed=True, score=1.0, latency_ms=10)],
    )
    html_pass = to_html(all_pass)
    assert "badge pass" in html_pass

    history = tmp_path / "history.jsonl"
    history.write_text("not-json\n\n" + json.dumps({"suite_name": "s", "results": []}) + "\n")
    tracker = RegressionTracker(history)
    assert tracker.load_history("s")


def test_rich_report_path(monkeypatch):
    captured = []

    class FakeConsole:
        def print(self, value=""):
            captured.append(value)

    class FakeTable:
        def __init__(self, **_kwargs):
            self.rows = []

        def add_column(self, *_args, **_kwargs):
            return None

        def add_row(self, *args):
            self.rows.append(args)

    fake_rich = cast(Any, types.ModuleType("rich"))
    fake_rich.box = types.SimpleNamespace(ROUNDED="rounded")
    fake_console_mod = types.ModuleType("rich.console")
    cast(Any, fake_console_mod).Console = FakeConsole
    fake_table_mod = types.ModuleType("rich.table")
    cast(Any, fake_table_mod).Table = FakeTable

    monkeypatch.setitem(__import__("sys").modules, "rich", fake_rich)
    monkeypatch.setitem(__import__("sys").modules, "rich.console", fake_console_mod)
    monkeypatch.setitem(__import__("sys").modules, "rich.table", fake_table_mod)

    suite = _suite()
    reporter.print_report(suite)
    assert any("EvalForge Report" in str(item) for item in captured)
