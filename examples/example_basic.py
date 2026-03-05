"""
Example 1: Basic eval suite — no external APIs required.

Demonstrates:
  - Defining test cases inline
  - Multiple scoring strategies (exact, fuzzy, contains, custom, json)
  - Running the harness synchronously
  - Saving reports

Run:
    cd examples
    pip install -e ../python
    python example_basic.py
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "python"))

from evalforge import EvalHarness, TestCase
from evalforge.scorer import (
    exact_match,
    fuzzy_match,
    contains_match,
    json_match,
    custom_scorer,
)


# ---------------------------------------------------------------------------
# Define the "agent" we're evaluating
# This is a simple mock; in real usage this would call your LLM or system.
# ---------------------------------------------------------------------------

def echo_agent(input_data: str) -> str:
    """A trivial agent that echoes back a response based on input."""
    responses = {
        "What is 2 + 2?": "4",
        "What is the capital of France?": "The capital of France is Paris.",
        "Tell me a joke": "Why did the chicken cross the road? To get to the other side!",
        "Say hello": "Hello! How can I help you today?",
        "Return JSON": '{"name": "Alice", "age": 30, "city": "NYC"}',
    }
    return responses.get(input_data, "I don't know.")


# ---------------------------------------------------------------------------
# Define the test suite
# ---------------------------------------------------------------------------

def make_test_suite() -> list[TestCase]:
    def score_contains_number(expected, actual) -> float:
        """Custom scorer: check if the actual output contains any digit."""
        return 1.0 if any(c.isdigit() for c in str(actual)) else 0.0

    return [
        TestCase(
            id="math-basic",
            description="Simple arithmetic",
            input="What is 2 + 2?",
            expected_output="4",
            scoring=exact_match(),
            tags=["math", "basic"],
        ),
        TestCase(
            id="geography-capital",
            description="Capital city lookup",
            input="What is the capital of France?",
            expected_output="Paris",
            scoring=contains_match(),
            tags=["geography"],
        ),
        TestCase(
            id="greeting-fuzzy",
            description="Greeting should be warm",
            input="Say hello",
            expected_output="Hello! How can I help?",
            scoring=fuzzy_match(threshold=0.7),
            tags=["greeting"],
        ),
        TestCase(
            id="json-output",
            description="Agent returns valid JSON with expected fields",
            input="Return JSON",
            expected_output={"name": "Alice", "age": 30},
            scoring=json_match(ignore_keys=["city"], threshold=1.0),
            tags=["structured"],
        ),
        TestCase(
            id="custom-number-check",
            description="Response must contain a number",
            input="What is 2 + 2?",
            expected_output="4",
            scoring=custom_scorer(score_contains_number, threshold=1.0),
            tags=["math", "custom"],
        ),
        TestCase(
            id="unknown-input",
            description="Agent gracefully handles unknown queries",
            input="xyzzy-unknown-prompt",
            expected_output="I don't know.",
            scoring=exact_match(),
            tags=["edge-case"],
        ),
    ]


# ---------------------------------------------------------------------------
# Run
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    harness = EvalHarness(
        agent=echo_agent,
        suite_name="basic-echo-suite",
        default_timeout=5.0,
        verbose=True,
    )

    harness.add_many(make_test_suite())

    result = harness.run(
        report_json="reports/basic_report.json",
        report_html="reports/basic_report.html",
    )

    # Programmatic access
    print(f"\nProgrammatic access: pass_rate={result.pass_rate:.1%}, avg_score={result.avg_score:.3f}")

    # Exit non-zero if any tests failed
    sys.exit(0 if result.pass_rate == 1.0 else 1)
