"""
Harness - the top-level orchestrator.

EvalHarness is the main entry point for running eval suites.
It wires together the Runner, Scorer, Reporter, and optionally
the RegressionTracker.

Quick start::

    from evalforge import EvalHarness, TestCase
    from evalforge.scorer import fuzzy_match

    harness = EvalHarness(agent=my_agent, suite_name="smoke")

    harness.add(TestCase(
        id="hello",
        input="Say hello",
        expected_output="Hello!",
        scoring=fuzzy_match(threshold=0.7),
    ))

    result = harness.run()
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Any, Callable, Optional

from .observability import EvalLogger, EvalMetrics, WebhookNotifier
from .reporter import RegressionTracker, print_report, save_html, save_json
from .runner import Runner
from .scorer import Scorer
from .test_case import SuiteResult, TestCase

logger = logging.getLogger(__name__)


class EvalHarness:
    """
    Top-level harness for defining and running an eval suite.

    Attributes:
        test_cases: The list of TestCase objects in this harness.
    """

    def __init__(
        self,
        agent: Callable[..., Any],
        suite_name: str = "eval",
        *,
        default_timeout: float = 30.0,
        default_retries: int = 0,
        concurrency: int = 1,
        scorer: Optional[Scorer] = None,
        history_path: Optional[str | Path] = None,
        verbose: bool = True,
        on_result: Optional[Callable[..., Any]] = None,
        debug: bool = False,
        eval_logger: Optional[EvalLogger] = None,
        webhook_notifier: Optional[WebhookNotifier] = None,
        webhook_url: Optional[str] = None,
    ):
        """
        Args:
            agent: The agent to evaluate (sync or async callable).
            suite_name: Display name for the suite.
            default_timeout: Per-test timeout in seconds.
            default_retries: Number of retries on test error.
            concurrency: Parallel test execution limit.
            scorer: Custom Scorer (default uses built-in strategies).
            history_path: If set, persist results for regression tracking.
            verbose: Print report to console after each run.
            on_result: Callback after each TestResult.
        """
        self.suite_name = suite_name
        self.test_cases: list[TestCase] = []
        self.verbose = verbose
        self.debug = debug
        self._history_path = history_path
        self._eval_logger = eval_logger or EvalLogger(suite_name=suite_name)
        self._webhook_notifier = webhook_notifier or WebhookNotifier(webhook_url)

        self._runner = Runner(
            agent=agent,
            suite_name=suite_name,
            default_timeout=default_timeout,
            default_retries=default_retries,
            concurrency=concurrency,
            scorer=scorer or Scorer(),
            on_result=on_result,
            eval_logger=self._eval_logger,
            debug=debug,
        )

        self._tracker = RegressionTracker(history_path) if history_path else None

    # ------------------------------------------------------------------
    # Building the suite
    # ------------------------------------------------------------------

    def add(self, test_case: TestCase) -> "EvalHarness":
        """Add a single TestCase. Returns self for chaining."""
        self.test_cases.append(test_case)
        return self

    def add_many(self, test_cases: list[TestCase]) -> "EvalHarness":
        """Add multiple TestCases. Returns self for chaining."""
        self.test_cases.extend(test_cases)
        return self

    def filter(self, tags: list[str]) -> list[TestCase]:
        """Return test cases matching ANY of the given tags."""
        return [tc for tc in self.test_cases if any(t in tc.tags for t in tags)]

    # ------------------------------------------------------------------
    # Running
    # ------------------------------------------------------------------

    def run(
        self,
        tags: Optional[list[str]] = None,
        metadata: Optional[dict[str, Any]] = None,
        report_json: Optional[str | Path] = None,
        report_html: Optional[str | Path] = None,
    ) -> SuiteResult:
        """
        Run the eval suite synchronously.

        Args:
            tags: If provided, only run test cases with these tags.
            metadata: Extra metadata attached to the SuiteResult.
            report_json: Path to save JSON report (optional).
            report_html: Path to save HTML report (optional).

        Returns:
            SuiteResult with all individual TestResults.
        """
        cases = self.filter(tags) if tags else self.test_cases
        if not cases:
            logger.warning("No test cases to run.")

        self._eval_logger.suite_started(total_tests=len(cases), metadata=metadata)

        result = asyncio.run(self._runner.run(cases, metadata))
        self._post_run(result, report_json, report_html)
        return result

    async def run_async(
        self,
        tags: Optional[list[str]] = None,
        metadata: Optional[dict[str, Any]] = None,
        report_json: Optional[str | Path] = None,
        report_html: Optional[str | Path] = None,
    ) -> SuiteResult:
        """Async version of :meth:`run`."""
        cases = self.filter(tags) if tags else self.test_cases
        if not cases:
            logger.warning("No test cases to run.")

        self._eval_logger.suite_started(total_tests=len(cases), metadata=metadata)

        result = await self._runner.run(cases, metadata)
        self._post_run(result, report_json, report_html)
        return result

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _post_run(
        self,
        result: SuiteResult,
        report_json: Optional[str | Path],
        report_html: Optional[str | Path],
    ) -> None:
        regressions: list[str] = []

        if self.verbose:
            print_report(result)

        if self.debug:
            self._print_debug_breakdown(result)

        if report_json:
            path = save_json(result, report_json)
            logger.info("JSON report saved to %s", path)

        if report_html:
            path = save_html(result, report_html)
            logger.info("HTML report saved to %s", path)

        if self._tracker:
            regressions = self._tracker.compare_and_save(result)
            if regressions:
                logger.warning(
                    "%d regression(s) detected: %s",
                    len(regressions),
                    ", ".join(regressions),
                )
                if self.verbose:
                    print(f"\n⚠  Regressions detected: {', '.join(regressions)}")

        metrics = EvalMetrics.from_suite(
            result,
            total_runs=1,
            regression_count=len(regressions),
        )
        self._eval_logger.suite_completed(metrics)

        if regressions:
            self._eval_logger.regression_detected(regressions, metrics)
            _ = self._webhook_notifier.notify_regression(
                suite_name=result.suite_name,
                regressions=regressions,
                metrics=metrics,
            )

    def _print_debug_breakdown(self, result: SuiteResult) -> None:
        print("\n[evalforge debug] per-test scoring breakdown")
        for test_result in result.results:
            debug_breakdown = test_result.metadata.get("debug_breakdown") if test_result.metadata else None
            if not debug_breakdown:
                continue
            reason = debug_breakdown.get("reason", "")
            strategy = debug_breakdown.get("strategy", "unknown")
            threshold = debug_breakdown.get("threshold", "n/a")
            print(
                f"- {test_result.test_case_id}: strategy={strategy} score={test_result.score:.3f} "
                f"threshold={threshold} passed={test_result.passed} reason={reason}"
            )
