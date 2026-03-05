# pyright: reportMissingImports=false

import asyncio
import time

from evalforge.runner import Runner
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
