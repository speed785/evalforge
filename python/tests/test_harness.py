import asyncio
import logging

from evalforge import EvalHarness, TestCase
from evalforge.test_case import SuiteResult, TestResult
from evalforge.scorer import contains_match, exact_match


def test_harness_end_to_end(tmp_path):
    def agent(prompt: str) -> str:
        mapping = {
            "capital": "Paris is the capital of France",
            "math": "4",
        }
        return mapping.get(prompt, "unknown")

    harness = EvalHarness(
        agent=agent,
        suite_name="e2e",
        history_path=tmp_path / "history.jsonl",
        verbose=False,
    )
    harness.add_many(
        [
            TestCase(id="capital", input="capital", expected_output="Paris", scoring=contains_match()),
            TestCase(id="math", input="math", expected_output="4", scoring=exact_match()),
        ]
    )

    result = harness.run(report_json=tmp_path / "report.json", report_html=tmp_path / "report.html")
    assert result.total == 2
    assert result.passed == 2
    assert (tmp_path / "report.json").exists()
    assert (tmp_path / "report.html").exists()


def test_harness_run_async_and_filtering():
    async def agent(prompt: str) -> str:
        return f"resp:{prompt}"

    harness = EvalHarness(agent=agent, suite_name="async", verbose=False)
    harness.add(TestCase(id="a", input="one", expected_output="one", scoring=contains_match(), tags=["x"]))
    harness.add(TestCase(id="b", input="two", expected_output="two", scoring=contains_match(), tags=["y"]))

    result = asyncio.run(harness.run_async(tags=["y"]))
    assert result.total == 1
    assert result.results[0].test_case_id == "b"


def test_harness_empty_cases_and_debug_output(caplog, capsys):
    async def agent(_prompt: str) -> str:
        return "ok"

    harness = EvalHarness(agent=agent, suite_name="empty", verbose=True, debug=True)

    caplog.set_level(logging.WARNING)
    sync_result = harness.run()
    assert sync_result.total == 0
    assert any("No test cases to run" in rec.message for rec in caplog.records)

    caplog.clear()
    async_result = asyncio.run(harness.run_async())
    assert async_result.total == 0
    assert any("No test cases to run" in rec.message for rec in caplog.records)

    fake_result = SuiteResult(
        suite_name="empty",
        results=[TestResult(test_case_id="x", passed=True, score=1.0, metadata={})],
    )
    harness._print_debug_breakdown(fake_result)
    output = capsys.readouterr().out
    assert "per-test scoring breakdown" in output


def test_harness_verbose_regression_message(tmp_path, capsys):
    responses = {"prompt": "ok"}

    def agent(prompt: str) -> str:
        return responses[prompt]

    harness = EvalHarness(
        agent=agent,
        suite_name="reg",
        history_path=tmp_path / "history.jsonl",
        verbose=True,
    )
    harness.add(TestCase(id="x", input="prompt", expected_output="ok", scoring=contains_match()))

    harness.run()
    responses["prompt"] = "bad"
    harness.run()

    output = capsys.readouterr().out
    assert "Regressions detected" in output
