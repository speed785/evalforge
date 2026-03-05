"""
Scorer - multiple strategies for evaluating agent outputs.

Supports exact match, fuzzy match, contains, JSON deep-compare,
LLM-as-judge, and custom scoring functions.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Callable, Optional

from .test_case import ScoringCriteria

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Base
# ---------------------------------------------------------------------------


class Scorer:
    """Dispatches to the correct scoring strategy based on ScoringCriteria."""

    def __init__(self, llm_judge_fn: Optional[Callable] = None):
        """
        Args:
            llm_judge_fn: An async callable ``(prompt, expected, actual) -> float``
                          used when strategy is 'llm_judge'.
        """
        self._llm_judge_fn = llm_judge_fn

    async def score(
        self,
        criteria: ScoringCriteria,
        expected: Any,
        actual: Any,
    ) -> float:
        """Return a score in [0.0, 1.0]."""
        strategy = criteria.strategy

        if strategy == "exact":
            return _exact(expected, actual)
        elif strategy == "fuzzy":
            return _fuzzy(expected, actual, criteria.fuzzy_method)
        elif strategy == "contains":
            return _contains(expected, actual)
        elif strategy == "json_match":
            return _json_match(expected, actual, criteria.json_ignore_keys)
        elif strategy == "llm_judge":
            return await self._llm_judge(criteria, expected, actual)
        elif strategy == "custom":
            if criteria.scorer_fn is None:
                raise ValueError("ScoringCriteria.scorer_fn must be set for 'custom' strategy")
            result = criteria.scorer_fn(expected, actual)
            # Support sync functions that return a float
            if hasattr(result, "__await__"):
                result = await result
            return float(result)
        else:
            raise ValueError(f"Unknown scoring strategy: {strategy!r}")

    async def _llm_judge(
        self,
        criteria: ScoringCriteria,
        expected: Any,
        actual: Any,
    ) -> float:
        if self._llm_judge_fn is None:
            raise RuntimeError(
                "llm_judge strategy requires a llm_judge_fn passed to Scorer(). "
                "Use Scorer(llm_judge_fn=my_async_judge) or use an integration."
            )
        prompt = criteria.llm_judge_prompt or _default_judge_prompt(expected, actual)
        return await self._llm_judge_fn(prompt, expected, actual)


# ---------------------------------------------------------------------------
# Strategy implementations
# ---------------------------------------------------------------------------


def _exact(expected: Any, actual: Any) -> float:
    """Exact equality check."""
    if isinstance(expected, str) and isinstance(actual, str):
        return 1.0 if expected.strip() == actual.strip() else 0.0
    return 1.0 if expected == actual else 0.0


def _fuzzy(expected: Any, actual: Any, method: str = "token_sort_ratio") -> float:
    """Fuzzy string similarity using rapidfuzz (falls back to exact if unavailable)."""
    try:
        from rapidfuzz import fuzz

        scorer_fn = getattr(fuzz, method, fuzz.token_sort_ratio)
        score = scorer_fn(str(expected), str(actual))
        return score / 100.0
    except ImportError:
        logger.warning(
            "rapidfuzz not installed — falling back to exact match for fuzzy scoring. "
            "Install with: pip install rapidfuzz"
        )
        return _exact(expected, actual)


def _contains(expected: Any, actual: Any) -> float:
    """Check whether expected is contained within actual."""
    return 1.0 if str(expected).strip() in str(actual) else 0.0


def _json_match(
    expected: Any,
    actual: Any,
    ignore_keys: list[str] | None = None,
) -> float:
    """
    Deep-compare two JSON-serialisable structures.
    Returns a score proportional to the fraction of matching leaf values.
    """
    ignore = set(ignore_keys or [])

    def _flatten(obj: Any, prefix: str = "") -> dict[str, Any]:
        items: dict[str, Any] = {}
        if isinstance(obj, dict):
            for k, v in obj.items():
                if k in ignore:
                    continue
                items.update(_flatten(v, f"{prefix}.{k}" if prefix else k))
        elif isinstance(obj, list):
            for i, v in enumerate(obj):
                items.update(_flatten(v, f"{prefix}[{i}]"))
        else:
            items[prefix] = obj
        return items

    # Allow raw strings to be parsed as JSON
    if isinstance(expected, str):
        try:
            expected = json.loads(expected)
        except json.JSONDecodeError:
            pass
    if isinstance(actual, str):
        try:
            actual = json.loads(actual)
        except json.JSONDecodeError:
            pass

    exp_flat = _flatten(expected)
    act_flat = _flatten(actual)

    if not exp_flat:
        return 1.0 if not act_flat else 0.0

    matches = sum(1 for k, v in exp_flat.items() if act_flat.get(k) == v)
    return matches / len(exp_flat)


def _default_judge_prompt(expected: Any, actual: Any) -> str:
    return (
        "You are an impartial evaluator. Score the following agent response "
        "on a scale of 0.0 to 1.0 where 1.0 is a perfect answer.\n\n"
        f"Expected answer:\n{expected}\n\n"
        f"Agent response:\n{actual}\n\n"
        "Reply with ONLY a decimal number between 0.0 and 1.0."
    )


# ---------------------------------------------------------------------------
# Convenience constructors
# ---------------------------------------------------------------------------


def exact_match() -> ScoringCriteria:
    return ScoringCriteria(strategy="exact", threshold=1.0)


def fuzzy_match(threshold: float = 0.8, method: str = "token_sort_ratio") -> ScoringCriteria:
    return ScoringCriteria(strategy="fuzzy", threshold=threshold, fuzzy_method=method)


def contains_match(threshold: float = 1.0) -> ScoringCriteria:
    return ScoringCriteria(strategy="contains", threshold=threshold)


def json_match(ignore_keys: list[str] | None = None, threshold: float = 1.0) -> ScoringCriteria:
    return ScoringCriteria(
        strategy="json_match",
        threshold=threshold,
        json_ignore_keys=ignore_keys or [],
    )


def llm_judge(prompt: str | None = None, threshold: float = 0.7) -> ScoringCriteria:
    return ScoringCriteria(
        strategy="llm_judge",
        threshold=threshold,
        llm_judge_prompt=prompt,
    )


def custom_scorer(fn: Callable[[Any, Any], float], threshold: float = 0.5) -> ScoringCriteria:
    return ScoringCriteria(strategy="custom", threshold=threshold, scorer_fn=fn)
