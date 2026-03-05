"""
TestCase - the atomic unit of an eval suite.

A TestCase defines what input to give an agent, what output to expect,
how to score the result, and metadata for tracking/filtering.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable, Optional


@dataclass
class ScoringCriteria:
    """Defines how a test case result should be scored."""

    strategy: str = "exact"
    """
    Scoring strategy. One of:
      - 'exact'       : exact string match
      - 'fuzzy'       : fuzzy string similarity (requires rapidfuzz)
      - 'contains'    : expected is a substring of actual
      - 'llm_judge'   : use an LLM to judge correctness
      - 'custom'      : provide a custom scorer_fn
      - 'json_match'  : deep compare JSON structures
      - 'semantic'    : embedding cosine similarity (optional openai)
    """

    threshold: float = 1.0
    """Minimum score [0.0–1.0] to consider the test passed."""

    scorer_fn: Optional[Callable[[Any, Any], float]] = None
    """Custom scoring function: (expected, actual) -> float in [0, 1]."""

    llm_judge_prompt: Optional[str] = None
    """System prompt override when using 'llm_judge' strategy."""

    fuzzy_method: str = "token_sort_ratio"
    """rapidfuzz method to use for fuzzy matching."""

    json_ignore_keys: list[str] = field(default_factory=list)
    """Keys to ignore when comparing JSON structures."""

    semantic_model: str = "text-embedding-3-small"
    """Embedding model to use for semantic similarity scoring."""


@dataclass
class TestCase:
    """
    A single evaluation test case.

    Example::

        case = TestCase(
            id="greet-001",
            description="Agent should greet user by name",
            input={"messages": [{"role": "user", "content": "Hi, I'm Alice"}]},
            expected_output="Hello, Alice!",
            scoring=ScoringCriteria(strategy="fuzzy", threshold=0.8),
            tags=["greeting", "basic"],
        )
    """

    input: Any
    """The input to pass to the agent under evaluation."""

    expected_output: Any
    """The expected output from the agent."""

    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    """Unique identifier for this test case."""

    description: str = ""
    """Human-readable description of what is being tested."""

    scoring: ScoringCriteria = field(default_factory=ScoringCriteria)
    """How to score the agent's response."""

    tags: list[str] = field(default_factory=list)
    """Tags for filtering and grouping test cases."""

    metadata: dict[str, Any] = field(default_factory=dict)
    """Arbitrary metadata (model, version, dataset source, etc.)."""

    timeout_seconds: Optional[float] = None
    """Per-test timeout override (None inherits suite default)."""

    max_retries: int = 0
    """Number of times to retry on failure before recording a failure."""

    setup: Optional[Callable[[], Any]] = None
    """Optional setup callable run before the agent is invoked."""

    teardown: Optional[Callable[[Any], None]] = None
    """Optional teardown callable run after the agent responds."""


@dataclass
class TestResult:
    """The outcome of running a single TestCase."""

    test_case_id: str
    passed: bool
    score: float

    actual_output: Any = None
    error: Optional[str] = None
    latency_ms: Optional[float] = None
    retries: int = 0
    timestamp: float = field(default_factory=time.time)
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def status(self) -> str:
        if self.error:
            return "error"
        return "pass" if self.passed else "fail"

    def to_dict(self) -> dict[str, Any]:
        return {
            "test_case_id": self.test_case_id,
            "status": self.status,
            "passed": self.passed,
            "score": self.score,
            "actual_output": self.actual_output,
            "error": self.error,
            "latency_ms": self.latency_ms,
            "retries": self.retries,
            "timestamp": self.timestamp,
            "metadata": self.metadata,
        }


@dataclass
class SuiteResult:
    """Aggregated results for a full eval suite run."""

    suite_name: str
    results: list[TestResult]
    run_id: str = field(default_factory=lambda: str(uuid.uuid4())[:12])
    started_at: float = field(default_factory=time.time)
    finished_at: Optional[float] = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def total(self) -> int:
        return len(self.results)

    @property
    def passed(self) -> int:
        return sum(1 for r in self.results if r.passed)

    @property
    def failed(self) -> int:
        return sum(1 for r in self.results if not r.passed and not r.error)

    @property
    def errors(self) -> int:
        return sum(1 for r in self.results if r.error)

    @property
    def pass_rate(self) -> float:
        return self.passed / self.total if self.total else 0.0

    @property
    def avg_score(self) -> float:
        scores = [r.score for r in self.results]
        return sum(scores) / len(scores) if scores else 0.0

    @property
    def avg_latency_ms(self) -> Optional[float]:
        lats = [r.latency_ms for r in self.results if r.latency_ms is not None]
        return sum(lats) / len(lats) if lats else None

    def to_dict(self) -> dict[str, Any]:
        return {
            "suite_name": self.suite_name,
            "run_id": self.run_id,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "total": self.total,
            "passed": self.passed,
            "failed": self.failed,
            "errors": self.errors,
            "pass_rate": self.pass_rate,
            "avg_score": self.avg_score,
            "avg_latency_ms": self.avg_latency_ms,
            "metadata": self.metadata,
            "results": [r.to_dict() for r in self.results],
        }
