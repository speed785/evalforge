"""
Runner - executes agents against test cases with async support,
timeouts, retries, and progress reporting.
"""

from __future__ import annotations

import asyncio
import inspect
import logging
import time
from typing import Any, Callable, Optional, cast

from .observability import EvalLogger
from .scorer import Scorer
from .test_case import ScoringCriteria, SuiteResult, TestCase, TestResult

logger = logging.getLogger(__name__)

AgentFn = Callable[[Any], Any]  # sync or async callable that takes input -> output


class Runner:
    """
    Runs a list of TestCases against an agent function and returns a SuiteResult.

    Usage::

        runner = Runner(agent=my_agent_fn, suite_name="My Suite")
        result = asyncio.run(runner.run(test_cases))
    """

    def __init__(
        self,
        agent: AgentFn,
        suite_name: str = "eval",
        default_timeout: float = 30.0,
        default_retries: int = 0,
        concurrency: int = 1,
        scorer: Optional[Scorer] = None,
        on_result: Optional[Callable[[TestResult], None]] = None,
        eval_logger: Optional[EvalLogger] = None,
        debug: bool = False,
    ):
        """
        Args:
            agent: The agent to evaluate. Can be sync or async.
                   Signature: ``agent(input) -> output``.
            suite_name: Name shown in reports.
            default_timeout: Seconds before a test case times out (per attempt).
            default_retries: Number of retries on error (per test case).
            concurrency: Max parallel test cases (default 1 = sequential).
            scorer: Scorer instance. Defaults to ``Scorer()`` (no LLM judge).
            on_result: Optional callback invoked after each TestResult is ready.
        """
        self.agent = agent
        self.suite_name = suite_name
        self.default_timeout = default_timeout
        self.default_retries = default_retries
        self.concurrency = concurrency
        self.scorer = scorer or Scorer()
        self.on_result = on_result
        self.eval_logger = eval_logger
        self.debug = debug

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def run(
        self,
        test_cases: list[TestCase],
        metadata: dict[str, Any] | None = None,
    ) -> SuiteResult:
        """Run all test cases and return a SuiteResult."""
        suite = SuiteResult(
            suite_name=self.suite_name,
            results=[],
            metadata=metadata or {},
            started_at=time.time(),
        )

        semaphore = asyncio.Semaphore(self.concurrency)

        async def _run_one(tc: TestCase) -> TestResult:
            async with semaphore:
                return await self._run_test_case(tc)

        tasks = [_run_one(tc) for tc in test_cases]
        results = await asyncio.gather(*tasks, return_exceptions=False)

        suite.results = list(results)
        suite.finished_at = time.time()
        return suite

    def run_sync(
        self,
        test_cases: list[TestCase],
        metadata: dict[str, Any] | None = None,
    ) -> SuiteResult:
        """Synchronous wrapper around :meth:`run`."""
        return asyncio.run(self.run(test_cases, metadata))

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    async def _run_test_case(self, tc: TestCase) -> TestResult:
        timeout = tc.timeout_seconds if tc.timeout_seconds is not None else self.default_timeout
        max_retries = tc.max_retries if tc.max_retries else self.default_retries
        retries = 0
        scorer_type = tc.scoring.strategy

        if self.eval_logger:
            self.eval_logger.test_started(test_name=tc.id, scorer_type=scorer_type)

        # Setup hook
        if tc.setup:
            try:
                result = tc.setup()
                if inspect.isawaitable(result):
                    await cast(Any, result)
            except Exception as exc:
                logger.warning("Setup failed for %s: %s", tc.id, exc)

        last_error: Optional[str] = None
        actual_output: Any = None
        latency_ms: Optional[float] = None

        while retries <= max_retries:
            try:
                start = time.perf_counter()
                actual_output = await asyncio.wait_for(
                    self._invoke_agent(tc.input),
                    timeout=timeout,
                )
                latency_ms = (time.perf_counter() - start) * 1000
                last_error = None
                break
            except asyncio.TimeoutError:
                last_error = f"Timed out after {timeout}s"
                retries += 1
                logger.debug("Test %s timed out (attempt %d)", tc.id, retries)
            except Exception as exc:
                last_error = f"{type(exc).__name__}: {exc}"
                retries += 1
                logger.debug("Test %s raised %s (attempt %d)", tc.id, exc, retries)

        # Teardown hook
        if tc.teardown:
            try:
                result = cast(Callable[[Any], Any], tc.teardown)(actual_output)
                if inspect.isawaitable(result):
                    await cast(Any, result)
            except Exception as exc:
                logger.warning("Teardown failed for %s: %s", tc.id, exc)

        if last_error:
            debug_breakdown = self._debug_breakdown(
                tc=tc,
                score=0.0,
                passed=False,
                reason=last_error,
            )
            test_result = TestResult(
                test_case_id=tc.id,
                passed=False,
                score=0.0,
                actual_output=actual_output,
                error=last_error,
                latency_ms=latency_ms,
                retries=retries - 1,
                metadata={
                    "scorer_type": scorer_type,
                    "debug_breakdown": debug_breakdown,
                },
            )
            if self.eval_logger:
                self.eval_logger.test_failed(
                    test_name=tc.id,
                    score=0.0,
                    latency_ms=latency_ms,
                    scorer_type=scorer_type,
                    error=last_error,
                    debug_breakdown=debug_breakdown,
                )
        else:
            score = await self._score(tc.scoring, tc.expected_output, actual_output)
            passed = score >= tc.scoring.threshold
            reason = (
                f"score {score:.3f} >= threshold {tc.scoring.threshold:.3f}"
                if passed
                else f"score {score:.3f} < threshold {tc.scoring.threshold:.3f}"
            )
            debug_breakdown = self._debug_breakdown(
                tc=tc,
                score=score,
                passed=passed,
                reason=reason,
            )
            test_result = TestResult(
                test_case_id=tc.id,
                passed=passed,
                score=score,
                actual_output=actual_output,
                latency_ms=latency_ms,
                retries=retries,
                metadata={
                    "scorer_type": scorer_type,
                    "debug_breakdown": debug_breakdown,
                },
            )
            if self.eval_logger:
                self.eval_logger.test_completed(
                    test_name=tc.id,
                    score=score,
                    passed=passed,
                    latency_ms=latency_ms,
                    scorer_type=scorer_type,
                    debug_breakdown=debug_breakdown,
                )
                if not passed:
                    self.eval_logger.test_failed(
                        test_name=tc.id,
                        score=score,
                        latency_ms=latency_ms,
                        scorer_type=scorer_type,
                        debug_breakdown=debug_breakdown,
                    )

        if self.on_result:
            self.on_result(test_result)

        return test_result

    async def _invoke_agent(self, input_data: Any) -> Any:
        """Call the agent, supporting both sync and async callables."""
        if inspect.iscoroutinefunction(self.agent):
            return await self.agent(input_data)
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.agent, input_data)

    async def _score(
        self,
        criteria: ScoringCriteria,
        expected: Any,
        actual: Any,
    ) -> float:
        try:
            return await self.scorer.score(criteria, expected, actual)
        except Exception as exc:
            logger.error("Scoring failed: %s", exc)
            return 0.0

    def _debug_breakdown(
        self,
        tc: TestCase,
        score: float,
        passed: bool,
        reason: str,
    ) -> dict[str, Any] | None:
        if not self.debug:
            return None
        return {
            "strategy": tc.scoring.strategy,
            "threshold": tc.scoring.threshold,
            "score": score,
            "passed": passed,
            "reason": reason,
            "expected": str(tc.expected_output),
        }
