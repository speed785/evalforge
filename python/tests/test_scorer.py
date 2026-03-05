# pyright: reportMissingImports=false

import asyncio
import builtins
import types
from typing import Any, cast

import pytest

from evalforge.scorer import (
    Scorer,
    contains_match,
    custom_scorer,
    exact_match,
    fuzzy_match,
    json_match,
    llm_judge,
    semantic_match,
)
from evalforge.test_case import ScoringCriteria


def test_exact_contains_and_json_match():
    scorer = Scorer()
    assert asyncio.run(scorer.score(exact_match(), "x", "x")) == 1.0
    assert asyncio.run(scorer.score(contains_match(), "Paris", "The capital is Paris")) == 1.0
    assert (
        asyncio.run(
            scorer.score(
                json_match(ignore_keys=["ts"]),
                {"a": 1, "ts": 2},
                {"a": 1, "ts": 9},
            )
        )
        == 1.0
    )


def test_custom_scorer_and_llm_judge():
    async def judge(_prompt, _expected, _actual):
        return 0.77

    scorer = Scorer(llm_judge_fn=judge)
    assert asyncio.run(scorer.score(llm_judge(), "a", "b")) == 0.77
    assert (
        asyncio.run(
            scorer.score(custom_scorer(lambda _e, a: 1.0 if a == "ok" else 0.0), "", "ok")
        )
        == 1.0
    )


def test_fuzzy_warns_when_rapidfuzz_missing(monkeypatch):
    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "rapidfuzz":
            raise ImportError("rapidfuzz missing")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    scorer = Scorer()
    with pytest.warns(RuntimeWarning, match="rapidfuzz not installed"):
        score = asyncio.run(scorer.score(fuzzy_match(), "abc", "abc"))
    assert score == 1.0


def test_semantic_score_with_openai_mock_and_cache(monkeypatch):
    class FakeEmbeddings:
        def __init__(self):
            self.calls = 0

        async def create(self, model, input):
            self.calls += 1
            if "Paris" in input:
                vector = [1.0, 0.0]
            else:
                vector = [0.0, 1.0]
            return types.SimpleNamespace(data=[types.SimpleNamespace(embedding=vector)])

    class FakeClient:
        def __init__(self, *args, **kwargs):
            self.embeddings = embeddings

    embeddings = FakeEmbeddings()
    fake_module = types.SimpleNamespace(AsyncOpenAI=FakeClient)
    monkeypatch.setitem(__import__("sys").modules, "openai", fake_module)

    scorer = Scorer()
    criteria = semantic_match()
    first = asyncio.run(scorer.score(criteria, "Paris", "Paris"))
    second = asyncio.run(scorer.score(criteria, "Paris", "Paris"))

    assert first == pytest.approx(1.0)
    assert second == pytest.approx(1.0)
    assert embeddings.calls == 1


def test_semantic_gracefully_warns_without_openai(monkeypatch):
    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "openai":
            raise ImportError("openai missing")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    scorer = Scorer()
    with pytest.warns(RuntimeWarning, match="openai not installed"):
        score = asyncio.run(scorer.score(semantic_match(), "a", "b"))
    assert score == 0.0


def test_scorer_edge_paths(monkeypatch):
    scorer = Scorer()

    with pytest.raises(ValueError, match="scorer_fn"):
        asyncio.run(
            scorer.score(ScoringCriteria(strategy="custom", threshold=0.5, scorer_fn=None), "x", "y")
        )

    def async_custom(_expected: Any, _actual: Any) -> Any:
        async def _inner() -> float:
            return 0.4

        return _inner()

    criteria = custom_scorer(cast(Any, async_custom))
    assert asyncio.run(scorer.score(criteria, "x", "y")) == 0.4

    bad_criteria = exact_match()
    bad_criteria.strategy = "not-real"
    with pytest.raises(ValueError, match="Unknown scoring strategy"):
        asyncio.run(scorer.score(bad_criteria, "x", "x"))

    with pytest.raises(RuntimeError, match="llm_judge strategy requires"):
        asyncio.run(scorer.score(llm_judge(), "e", "a"))


def test_fuzzy_import_success_path(monkeypatch):
    class FakeFuzz:
        @staticmethod
        def token_sort_ratio(_a, _b):
            return 88

    fake_module = types.SimpleNamespace(fuzz=FakeFuzz)
    monkeypatch.setattr("importlib.import_module", lambda name: fake_module if name == "rapidfuzz" else __import__(name))

    scorer = Scorer()
    assert asyncio.run(scorer.score(fuzzy_match(), "a", "b")) == pytest.approx(0.88)


def test_json_match_and_cosine_edge_paths():
    scorer = Scorer()

    assert asyncio.run(scorer.score(exact_match(), 5, 5)) == 1.0

    assert asyncio.run(scorer.score(json_match(), "not-json", "also-not-json")) == 0.0
    assert asyncio.run(scorer.score(json_match(), "[]", "[1]")) == 0.0

    expected = {"arr": [1, 2]}
    actual = {"arr": [1, 9]}
    assert asyncio.run(scorer.score(json_match(), expected, actual)) == 0.5

    from evalforge import scorer as scorer_module

    assert scorer_module._cosine_similarity([1.0], [1.0, 2.0]) == 0.0
    assert scorer_module._cosine_similarity([0.0, 0.0], [1.0, 1.0]) == 0.0


def test_semantic_empty_embedding_returns_zero(monkeypatch):
    class FakeClient:
        def __init__(self, *args, **kwargs):
            self.embeddings = self

        async def create(self, model, input):
            vector = [] if input == "a" else [1.0, 0.0]
            return types.SimpleNamespace(data=[types.SimpleNamespace(embedding=vector)])

    fake_module = types.SimpleNamespace(AsyncOpenAI=FakeClient)
    monkeypatch.setitem(__import__("sys").modules, "openai", fake_module)

    scorer = Scorer()
    assert asyncio.run(scorer.score(semantic_match(), "a", "b")) == 0.0
