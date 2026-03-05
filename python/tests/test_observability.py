import asyncio
import io
import json
import logging
from typing import Any
from urllib.error import URLError

from evalforge.harness import EvalHarness
from evalforge.observability import EvalLogger, EvalMetrics, WebhookNotifier
from evalforge.runner import Runner
from evalforge.scorer import contains_match, exact_match
from evalforge.test_case import SuiteResult, TestCase, TestResult


def test_eval_metrics_export_prometheus():
    suite = SuiteResult(
        suite_name="demo",
        results=[
            TestResult(test_case_id="a", passed=True, score=1.0, latency_ms=10, metadata={"scorer_type": "exact"}),
            TestResult(test_case_id="b", passed=False, score=0.2, latency_ms=20, metadata={"scorer_type": "llm_judge"}),
        ],
    )

    metrics = EvalMetrics.from_suite(suite, regression_count=1)
    output = metrics.export_prometheus()
    assert "evalforge_pass_rate" in output
    assert "evalforge_p95_latency_ms" in output
    assert "evalforge_strategy_pass_rate{scorer_type=\"exact\"}" in output
    assert metrics.llm_judge_calls == 1
    assert metrics.regression_count == 1


def test_runner_emits_lifecycle_json_logs_and_debug_metadata():
    stream = io.StringIO()
    logger = logging.getLogger("evalforge.test.observability")
    logger.handlers = []
    logger.propagate = False
    logger.setLevel(logging.INFO)
    logger.addHandler(logging.StreamHandler(stream))

    eval_logger = EvalLogger("obs", logger=logger)

    async def agent(_prompt: str) -> str:
        return "ok"

    runner = Runner(agent=agent, suite_name="obs", eval_logger=eval_logger, debug=True)
    case = TestCase(id="t1", input="ping", expected_output="ok", scoring=exact_match())
    result = asyncio.run(runner.run([case]))

    logs = [json.loads(line) for line in stream.getvalue().splitlines() if line.strip()]
    events = {line["event"] for line in logs}
    assert "test_started" in events
    assert "test_completed" in events
    assert result.results[0].metadata["debug_breakdown"]["reason"].startswith("score")


def test_harness_triggers_webhook_when_regression_detected(tmp_path):
    class StubNotifier(WebhookNotifier):
        def __init__(self):
            super().__init__(webhook_url=None)
            self.calls = []

        def notify_regression(self, suite_name, regressions, metrics):
            self.calls.append((suite_name, regressions, metrics))
            return True

    responses = {"prompt": "ok"}

    def agent(prompt: str) -> str:
        return responses[prompt]

    notifier = StubNotifier()
    harness = EvalHarness(
        agent=agent,
        suite_name="regression-suite",
        history_path=tmp_path / "history.jsonl",
        verbose=False,
        webhook_notifier=notifier,
        debug=True,
    )
    harness.add(TestCase(id="case", input="prompt", expected_output="ok", scoring=contains_match()))

    first = harness.run()
    assert first.pass_rate == 1.0

    responses["prompt"] = "bad"
    second = harness.run()
    assert second.pass_rate == 0.0
    assert len(notifier.calls) == 1
    suite_name, regressions, _metrics = notifier.calls[0]
    assert suite_name == "regression-suite"
    assert regressions == ["case"]


def test_webhook_notifier_success_and_error_paths(monkeypatch):
    metrics = EvalMetrics(
        total_runs=1,
        total_tests=1,
        pass_rate=0.5,
        avg_latency_ms=1.0,
        p95_latency_ms=1.0,
        regression_count=1,
        llm_judge_calls=0,
        llm_judge_cost_estimate=0.0,
    )

    captured: dict[str, Any] = {"request": None}

    class _Ctx:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    def fake_urlopen(req, timeout):
        captured["request"] = (req, timeout)
        return _Ctx()

    monkeypatch.setattr("evalforge.observability.urlopen", fake_urlopen)

    notifier = WebhookNotifier("https://example.com/webhook", timeout_seconds=2.5)
    assert notifier.enabled is True
    assert notifier.notify_regression("suite", ["a"], metrics) is True
    assert captured["request"][1] == 2.5

    monkeypatch.setattr("evalforge.observability.urlopen", lambda *_args, **_kwargs: (_ for _ in ()).throw(URLError("down")))
    assert notifier.notify_regression("suite", ["a"], metrics) is False

    disabled = WebhookNotifier(None)
    assert disabled.enabled is False
    assert disabled.notify_regression("suite", ["a"], metrics) is False


def test_percentile_single_value_branch():
    from evalforge import observability as obs

    assert obs._percentile([], 95.0) == 0.0
    assert obs._percentile([7.0], 95.0) == 7.0
