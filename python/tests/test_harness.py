import asyncio

from evalforge import EvalHarness, TestCase
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
