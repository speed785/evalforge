"""
EvalForge - Agent Evaluation Harness
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

A framework for writing repeatable, measurable evals for agentic tasks.

Quick start::

    from evalforge import EvalHarness, TestCase
    from evalforge.scorer import fuzzy_match, exact_match

    def my_agent(input):
        return "Hello, world!"

    harness = EvalHarness(agent=my_agent, suite_name="smoke")
    harness.add(TestCase(
        id="greet",
        input="Say hello",
        expected_output="Hello, world!",
        scoring=exact_match(),
    ))
    result = harness.run()
"""

from .harness import EvalHarness
from .test_case import ScoringCriteria, SuiteResult, TestCase, TestResult
from .scorer import Scorer, exact_match, fuzzy_match, contains_match, json_match, llm_judge, custom_scorer
from .runner import Runner
from .reporter import print_report, to_json, save_json, to_html, save_html, RegressionTracker
from .registry import Registry, registry

__version__ = "0.1.0"

__all__ = [
    # Core
    "EvalHarness",
    "TestCase",
    "ScoringCriteria",
    "TestResult",
    "SuiteResult",
    # Scoring
    "Scorer",
    "exact_match",
    "fuzzy_match",
    "contains_match",
    "json_match",
    "llm_judge",
    "custom_scorer",
    # Runner
    "Runner",
    # Reporting
    "print_report",
    "to_json",
    "save_json",
    "to_html",
    "save_html",
    "RegressionTracker",
    # Registry
    "Registry",
    "registry",
]
