from __future__ import annotations

import json
import logging
import math
import statistics
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from urllib.error import URLError
from urllib.request import Request, urlopen

from .test_case import SuiteResult


def _iso_timestamp(ts: float | None = None) -> str:
    dt = datetime.fromtimestamp(ts or time.time(), tz=timezone.utc)
    return dt.isoformat()


class EvalLogger:
    def __init__(self, suite_name: str, logger: logging.Logger | None = None):
        self.suite_name = suite_name
        self._logger = logger or logging.getLogger("evalforge.observability")

    def log_event(self, event: str, **payload: Any) -> None:
        message = {
            "event": event,
            "timestamp": _iso_timestamp(),
            "suite_name": self.suite_name,
            **payload,
        }
        self._logger.info(json.dumps(message, default=str, sort_keys=True))

    def suite_started(self, total_tests: int, metadata: dict[str, Any] | None = None) -> None:
        self.log_event("suite_started", total_tests=total_tests, metadata=metadata or {})

    def test_started(self, test_name: str, scorer_type: str) -> None:
        self.log_event(
            "test_started",
            test_name=test_name,
            score=None,
            passed=None,
            latency_ms=None,
            scorer_type=scorer_type,
        )

    def test_completed(
        self,
        test_name: str,
        score: float,
        passed: bool,
        latency_ms: float | None,
        scorer_type: str,
        debug_breakdown: dict[str, Any] | None = None,
    ) -> None:
        self.log_event(
            "test_completed",
            test_name=test_name,
            score=score,
            passed=passed,
            latency_ms=latency_ms,
            scorer_type=scorer_type,
            debug_breakdown=debug_breakdown,
        )

    def test_failed(
        self,
        test_name: str,
        score: float,
        latency_ms: float | None,
        scorer_type: str,
        error: str | None = None,
        debug_breakdown: dict[str, Any] | None = None,
    ) -> None:
        self.log_event(
            "test_failed",
            test_name=test_name,
            score=score,
            passed=False,
            latency_ms=latency_ms,
            scorer_type=scorer_type,
            error=error,
            debug_breakdown=debug_breakdown,
        )

    def suite_completed(self, metrics: "EvalMetrics") -> None:
        self.log_event(
            "suite_completed",
            test_name=None,
            score=None,
            passed=metrics.pass_rate,
            latency_ms=metrics.avg_latency_ms,
            scorer_type=None,
            metrics=metrics.to_dict(),
        )

    def regression_detected(self, regressions: list[str], metrics: "EvalMetrics") -> None:
        self.log_event(
            "regression_detected",
            test_name=None,
            score=None,
            passed=False,
            latency_ms=metrics.avg_latency_ms,
            scorer_type=None,
            regressions=regressions,
            regression_count=len(regressions),
        )


@dataclass
class EvalMetrics:
    total_runs: int
    total_tests: int
    pass_rate: float
    avg_latency_ms: float
    p95_latency_ms: float
    regression_count: int
    llm_judge_calls: int
    llm_judge_cost_estimate: float
    strategy_pass_rates: dict[str, float] = field(default_factory=dict)
    strategy_p95_latency_ms: dict[str, float] = field(default_factory=dict)

    @classmethod
    def from_suite(
        cls,
        suite: SuiteResult,
        *,
        total_runs: int = 1,
        regression_count: int = 0,
        llm_cost_per_call: float = 0.002,
    ) -> "EvalMetrics":
        latencies = [r.latency_ms for r in suite.results if r.latency_ms is not None]
        p95 = _percentile(latencies, 95.0)
        avg = statistics.fmean(latencies) if latencies else 0.0

        strategy_buckets: dict[str, list[Any]] = {}
        llm_calls = 0
        for result in suite.results:
            scorer_type = str(result.metadata.get("scorer_type", "unknown"))
            strategy_buckets.setdefault(scorer_type, []).append(result)
            if scorer_type == "llm_judge":
                llm_calls += 1

        strategy_pass_rates: dict[str, float] = {}
        strategy_p95: dict[str, float] = {}
        for scorer_type, grouped in strategy_buckets.items():
            total = len(grouped)
            passed = sum(1 for r in grouped if r.passed)
            strategy_pass_rates[scorer_type] = (passed / total) if total else 0.0
            strategy_latencies = [r.latency_ms for r in grouped if r.latency_ms is not None]
            strategy_p95[scorer_type] = _percentile(strategy_latencies, 95.0)

        return cls(
            total_runs=total_runs,
            total_tests=suite.total,
            pass_rate=suite.pass_rate,
            avg_latency_ms=float(avg),
            p95_latency_ms=float(p95),
            regression_count=regression_count,
            llm_judge_calls=llm_calls,
            llm_judge_cost_estimate=llm_calls * llm_cost_per_call,
            strategy_pass_rates=strategy_pass_rates,
            strategy_p95_latency_ms=strategy_p95,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_runs": self.total_runs,
            "total_tests": self.total_tests,
            "pass_rate": self.pass_rate,
            "avg_latency_ms": self.avg_latency_ms,
            "p95_latency_ms": self.p95_latency_ms,
            "regression_count": self.regression_count,
            "llm_judge_calls": self.llm_judge_calls,
            "llm_judge_cost_estimate": self.llm_judge_cost_estimate,
            "strategy_pass_rates": self.strategy_pass_rates,
            "strategy_p95_latency_ms": self.strategy_p95_latency_ms,
        }

    def export_prometheus(self) -> str:
        lines = [
            "# HELP evalforge_total_runs Total suite runs measured.",
            "# TYPE evalforge_total_runs gauge",
            f"evalforge_total_runs {self.total_runs}",
            "# HELP evalforge_total_tests Total tests executed.",
            "# TYPE evalforge_total_tests gauge",
            f"evalforge_total_tests {self.total_tests}",
            "# HELP evalforge_pass_rate Pass rate of latest suite run.",
            "# TYPE evalforge_pass_rate gauge",
            f"evalforge_pass_rate {self.pass_rate}",
            "# HELP evalforge_avg_latency_ms Average latency in milliseconds.",
            "# TYPE evalforge_avg_latency_ms gauge",
            f"evalforge_avg_latency_ms {self.avg_latency_ms}",
            "# HELP evalforge_p95_latency_ms p95 latency in milliseconds.",
            "# TYPE evalforge_p95_latency_ms gauge",
            f"evalforge_p95_latency_ms {self.p95_latency_ms}",
            "# HELP evalforge_regression_count Number of detected regressions.",
            "# TYPE evalforge_regression_count gauge",
            f"evalforge_regression_count {self.regression_count}",
            "# HELP evalforge_llm_judge_calls Number of llm_judge scoring calls.",
            "# TYPE evalforge_llm_judge_calls gauge",
            f"evalforge_llm_judge_calls {self.llm_judge_calls}",
            "# HELP evalforge_llm_judge_cost_estimate Estimated llm_judge cost.",
            "# TYPE evalforge_llm_judge_cost_estimate gauge",
            f"evalforge_llm_judge_cost_estimate {self.llm_judge_cost_estimate}",
        ]
        for scorer_type, value in sorted(self.strategy_pass_rates.items()):
            lines.append(f'evalforge_strategy_pass_rate{{scorer_type="{scorer_type}"}} {value}')
        for scorer_type, value in sorted(self.strategy_p95_latency_ms.items()):
            lines.append(f'evalforge_strategy_p95_latency_ms{{scorer_type="{scorer_type}"}} {value}')
        return "\n".join(lines) + "\n"


class WebhookNotifier:
    def __init__(self, webhook_url: str | None, timeout_seconds: float = 5.0):
        self.webhook_url = webhook_url
        self.timeout_seconds = timeout_seconds
        self._logger = logging.getLogger("evalforge.webhook")

    @property
    def enabled(self) -> bool:
        return bool(self.webhook_url)

    def notify_regression(
        self,
        suite_name: str,
        regressions: list[str],
        metrics: EvalMetrics,
    ) -> bool:
        if not self.enabled or not self.webhook_url:
            return False

        payload = {
            "text": (
                f"EvalForge regression detected for suite '{suite_name}': "
                f"{len(regressions)} failing previously passing test(s)."
            ),
            "blocks": [
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": (
                            f"*EvalForge regression detected*\n"
                            f"Suite: `{suite_name}`\n"
                            f"Regressions: {', '.join(regressions)}\n"
                            f"Pass rate: {metrics.pass_rate:.1%}"
                        ),
                    },
                }
            ],
        }

        body = json.dumps(payload).encode("utf-8")
        request = Request(
            self.webhook_url,
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urlopen(request, timeout=self.timeout_seconds):
                return True
        except URLError as exc:
            self._logger.warning("Regression webhook failed: %s", exc)
            return False


def _percentile(values: list[float], percentile: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    rank = (percentile / 100.0) * (len(ordered) - 1)
    lo = math.floor(rank)
    hi = math.ceil(rank)
    if lo == hi:
        return float(ordered[lo])
    ratio = rank - lo
    return float(ordered[lo] * (1.0 - ratio) + ordered[hi] * ratio)
