"""
Example 2: Regression tracking across multiple runs.

Demonstrates:
  - Using the Registry to define reusable suites and agents
  - Tracking eval history in a JSONL file
  - Detecting regressions between runs
  - Simulating an agent that degrades over "versions"

Run:
    cd examples
    pip install -e ../python
    python example_regression.py
"""

import sys
import os
import asyncio

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "python"))

from evalforge import EvalHarness, TestCase, registry
from evalforge.reporter import RegressionTracker, print_report
from evalforge.scorer import fuzzy_match, contains_match


# ---------------------------------------------------------------------------
# Register test suite
# ---------------------------------------------------------------------------

@registry.suite("customer-support")
def customer_support_suite():
    return [
        TestCase(
            id="refund-policy",
            description="Agent knows refund policy",
            input="What is your refund policy?",
            expected_output="30-day",
            scoring=contains_match(),
            tags=["policy"],
        ),
        TestCase(
            id="shipping-time",
            description="Agent knows shipping times",
            input="How long does shipping take?",
            expected_output="3-5 business days",
            scoring=contains_match(),
            tags=["shipping"],
        ),
        TestCase(
            id="contact-support",
            description="Agent can direct to support",
            input="How do I contact support?",
            expected_output="support@example.com",
            scoring=contains_match(),
            tags=["contact"],
        ),
        TestCase(
            id="greeting",
            description="Agent greets politely",
            input="Hello!",
            expected_output="Hello! How can I help you today?",
            scoring=fuzzy_match(threshold=0.6),
            tags=["greeting"],
        ),
    ]


# ---------------------------------------------------------------------------
# Two "versions" of the agent — v2 is worse on some cases
# ---------------------------------------------------------------------------

RESPONSES_V1 = {
    "What is your refund policy?": "We offer a 30-day money back guarantee.",
    "How long does shipping take?": "Standard shipping takes 3-5 business days.",
    "How do I contact support?": "Email us at support@example.com",
    "Hello!": "Hello! How can I help you today?",
}

RESPONSES_V2 = {
    "What is your refund policy?": "Please check our website.",       # regression!
    "How long does shipping take?": "Shipping takes 3-5 business days.",
    "How do I contact support?": "Contact support@example.com",
    "Hello!": "Hi there!",                                             # borderline
}


@registry.agent("support-bot-v1")
async def support_bot_v1(prompt: str) -> str:
    await asyncio.sleep(0.01)  # simulate latency
    return RESPONSES_V1.get(prompt, "I don't have that information.")


@registry.agent("support-bot-v2")
async def support_bot_v2(prompt: str) -> str:
    await asyncio.sleep(0.01)
    return RESPONSES_V2.get(prompt, "I don't have that information.")


# ---------------------------------------------------------------------------
# Run both versions and compare
# ---------------------------------------------------------------------------

async def main():
    tracker = RegressionTracker("reports/regression_history.jsonl")
    test_cases = registry.get_suite("customer-support")

    print("=" * 60)
    print("  Running v1 (baseline)")
    print("=" * 60)

    harness_v1 = EvalHarness(
        agent=registry.get_agent("support-bot-v1"),
        suite_name="customer-support",
        verbose=True,
    )
    harness_v1.add_many(test_cases)
    result_v1 = await harness_v1.run_async(
        report_html="reports/v1_report.html",
    )
    regressions_v1 = tracker.compare_and_save(result_v1)
    print(f"v1 regressions (vs prior): {regressions_v1 or 'none (first run)'}\n")

    print("=" * 60)
    print("  Running v2 (degraded agent)")
    print("=" * 60)

    harness_v2 = EvalHarness(
        agent=registry.get_agent("support-bot-v2"),
        suite_name="customer-support",
        verbose=True,
    )
    harness_v2.add_many(test_cases)
    result_v2 = await harness_v2.run_async(
        report_html="reports/v2_report.html",
    )
    regressions_v2 = tracker.compare_and_save(result_v2)

    if regressions_v2:
        print(f"\n⚠  REGRESSIONS DETECTED in v2: {', '.join(regressions_v2)}")
        print("   These test cases passed in v1 but failed in v2!\n")
    else:
        print("\n✓ No regressions detected.\n")

    # Show historical pass rates
    history = tracker.load_history("customer-support")
    print(f"History ({len(history)} runs):")
    for h in history:
        print(f"  run_id={h['run_id']}  pass_rate={h['pass_rate']:.1%}  passed={h['passed']}/{h['total']}")

    return 0 if result_v2.pass_rate >= 0.75 else 1


if __name__ == "__main__":
    os.makedirs("reports", exist_ok=True)
    sys.exit(asyncio.run(main()))
