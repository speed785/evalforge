import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "python"))

from evalforge import EvalHarness, TestCase
from evalforge.observability import EvalMetrics
from evalforge.scorer import contains_match, exact_match


def support_agent(prompt: str) -> str:
    responses = {
        "refund": "We offer a 30-day refund policy.",
        "shipping": "Shipping takes 3-5 business days.",
        "support": "Contact support@example.com",
    }
    return responses.get(prompt, "Unknown")


def main() -> int:
    harness = EvalHarness(
        agent=support_agent,
        suite_name="observability-demo",
        history_path="reports/observability_history.jsonl",
        verbose=True,
        debug=True,
        webhook_url=os.environ.get("EVALFORGE_WEBHOOK_URL"),
    )

    harness.add_many(
        [
            TestCase(id="refund", input="refund", expected_output="30-day", scoring=contains_match()),
            TestCase(id="shipping", input="shipping", expected_output="3-5 business days", scoring=exact_match()),
            TestCase(id="support", input="support", expected_output="support@example.com", scoring=contains_match()),
        ]
    )

    result = harness.run(report_json="reports/observability_report.json")
    metrics = EvalMetrics.from_suite(result)
    print("\nPrometheus metrics:\n")
    print(metrics.export_prometheus())
    return 0 if result.pass_rate == 1.0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
