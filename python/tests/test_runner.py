# pyright: reportMissingImports=false

import asyncio
import time
from typing import Any, cast

from evalforge.scorer import Scorer
from evalforge.runner import Runner
from evalforge.test_case import ScoringCriteria
from evalforge.test_case import TestCase


def test_runner_concurrency():
    state = {"in_flight": 0, "max_in_flight": 0}

    async def agent(_input):
        state["in_flight"] += 1
        state["max_in_flight"] = max(state["max_in_flight"], state["in_flight"])
        await asyncio.sleep(0.05)
        state["in_flight"] -= 1
        return "ok"

    cases = [
        TestCase(id=f"c{i}", input=str(i), expected_output="ok")
        for i in range(6)
    ]
    runner = Runner(agent=agent, concurrency=3)
    started = time.perf_counter()
    result = asyncio.run(runner.run(cases))
    elapsed = time.perf_counter() - started

    assert result.total == 6
    assert result.passed == 6
    assert state["max_in_flight"] >= 2
    assert elapsed < 0.25


def test_runner_timeout():
    async def slow_agent(_input):
        await asyncio.sleep(0.2)
        return "late"

    case = TestCase(id="timeout", input="x", expected_output="late", timeout_seconds=0.01)
    result = asyncio.run(Runner(agent=slow_agent).run([case]))

    assert result.total == 1
    assert result.results[0].error is not None
    assert "Timed out" in result.results[0].error


def test_runner_retries_then_succeeds():
    calls = {"count": 0}

    async def flaky(_input):
        calls["count"] += 1
        if calls["count"] == 1:
            raise RuntimeError("boom")
        return "ok"

    case = TestCase(id="retry", input="x", expected_output="ok", max_retries=1)
    result = asyncio.run(Runner(agent=flaky).run([case]))

    assert result.results[0].passed
    assert result.results[0].retries == 1


def test_runner_sync_setup_teardown_on_result_and_scoring_error():
    state: dict[str, Any] = {"calls": 0, "seen": [], "setup": 0, "teardown": 0}

    def setup():
        state["setup"] += 1
        raise RuntimeError("setup-fail")

    def teardown(_output):
        state["teardown"] += 1
        raise RuntimeError("teardown-fail")

    async def agent(_input):
        state["calls"] += 1
        if state["calls"] == 1:
            raise RuntimeError("boom")
        return "ok"

    class BrokenScorer(Scorer):
        async def score(self, criteria, expected, actual):
            raise RuntimeError("score-fail")

    case = TestCase(
        id="edge",
        input="x",
        expected_output="ok",
        scoring=ScoringCriteria(strategy="exact", threshold=1.0),
        max_retries=1,
        setup=setup,
        teardown=teardown,
    )

    runner = Runner(
        agent=agent,
        scorer=BrokenScorer(),
        on_result=lambda res: state["seen"].append(res.test_case_id),
    )
    result = runner.run_sync([case])

    assert result.total == 1
    assert result.results[0].score == 0.0
    assert result.results[0].passed is False
    assert result.results[0].retries == 1
    assert state["seen"] == ["edge"]
    assert state["setup"] == 1
    assert state["teardown"] == 1


def test_runner_timeout_failure_emits_failed_event():
    class StubLogger:
        def __init__(self):
            self.failed = 0

        def test_started(self, **_kwargs):
            return None

        def test_failed(self, **_kwargs):
            self.failed += 1

        def test_completed(self, **_kwargs):
            return None

    async def slow_agent(_input):
        await asyncio.sleep(0.05)
        return "late"

    logger = StubLogger()
    case = TestCase(id="timeout2", input="x", expected_output="late", timeout_seconds=0.001)
    result = asyncio.run(Runner(agent=slow_agent, eval_logger=cast(Any, logger)).run([case]))

    assert result.results[0].error is not None
    assert logger.failed == 1


def test_runner_awaits_async_setup_and_teardown():
    state = {"setup": 0, "teardown": 0}

    async def setup():
        state["setup"] += 1

    async def teardown(_output):
        state["teardown"] += 1

    async def agent(_input):
        return "ok"

    case = TestCase(
        id="async-hooks",
        input="x",
        expected_output="ok",
        setup=setup,
        teardown=cast(Any, teardown),
    )
    result = asyncio.run(Runner(agent=agent).run([case]))

    assert result.results[0].passed is True
    assert state["setup"] == 1
    assert state["teardown"] == 1
