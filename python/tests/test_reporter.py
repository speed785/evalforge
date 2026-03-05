import json

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
