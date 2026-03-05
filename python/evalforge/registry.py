"""
Registry - a central store for reusable test suites and named agents.

Allows you to build up a library of evals and agents, then compose them
without passing objects around manually.

Usage::

    from evalforge.registry import registry

    @registry.suite("math-basic")
    def math_suite():
        return [TestCase(...), TestCase(...)]

    @registry.agent("gpt-4o")
    async def gpt4o_agent(input):
        ...

    suite_cases = registry.get_suite("math-basic")
    agent_fn    = registry.get_agent("gpt-4o")
"""

from __future__ import annotations

from typing import Any, Callable, Optional

from .test_case import TestCase


class Registry:
    """Central registry for test suites and agent callables."""

    def __init__(self):
        self._suites: dict[str, Callable[[], list[TestCase]]] = {}
        self._agents: dict[str, Callable] = {}

    # ------------------------------------------------------------------
    # Suites
    # ------------------------------------------------------------------

    def suite(self, name: str):
        """Decorator that registers a function returning a list of TestCases."""

        def decorator(fn: Callable[[], list[TestCase]]):
            self._suites[name] = fn
            return fn

        return decorator

    def register_suite(self, name: str, fn: Callable[[], list[TestCase]]) -> None:
        """Programmatically register a suite factory."""
        self._suites[name] = fn

    def get_suite(self, name: str) -> list[TestCase]:
        """Retrieve and instantiate a registered suite by name."""
        if name not in self._suites:
            available = list(self._suites.keys())
            raise KeyError(f"Suite {name!r} not found. Available: {available}")
        return self._suites[name]()

    def list_suites(self) -> list[str]:
        return list(self._suites.keys())

    # ------------------------------------------------------------------
    # Agents
    # ------------------------------------------------------------------

    def agent(self, name: str):
        """Decorator that registers an agent callable."""

        def decorator(fn: Callable):
            self._agents[name] = fn
            return fn

        return decorator

    def register_agent(self, name: str, fn: Callable) -> None:
        """Programmatically register an agent."""
        self._agents[name] = fn

    def get_agent(self, name: str) -> Callable:
        if name not in self._agents:
            available = list(self._agents.keys())
            raise KeyError(f"Agent {name!r} not found. Available: {available}")
        return self._agents[name]

    def list_agents(self) -> list[str]:
        return list(self._agents.keys())

    # ------------------------------------------------------------------
    # Convenience: run a named suite against a named agent
    # ------------------------------------------------------------------

    async def run(
        self,
        suite_name: str,
        agent_name: str,
        **runner_kwargs: Any,
    ):
        """
        Shortcut: load suite + agent from the registry and run them.

        Returns a SuiteResult.
        """
        from .runner import Runner

        test_cases = self.get_suite(suite_name)
        agent_fn = self.get_agent(agent_name)
        runner = Runner(
            agent=agent_fn,
            suite_name=suite_name,
            **runner_kwargs,
        )
        return await runner.run(test_cases)


# Module-level singleton — import and use directly
registry = Registry()
