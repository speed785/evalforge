import asyncio

import pytest

from evalforge.registry import Registry
from evalforge.scorer import exact_match
from evalforge.test_case import TestCase


def test_registry_register_get_and_run():
    reg = Registry()
    reg.register_suite("s", lambda: [TestCase(id="a", input="x", expected_output="ok", scoring=exact_match())])
    reg.register_agent("a", lambda _x: "ok")

    assert reg.list_suites() == ["s"]
    assert reg.list_agents() == ["a"]

    result = asyncio.run(reg.run("s", "a"))
    assert result.passed == 1


def test_registry_missing_items_raise():
    reg = Registry()
    with pytest.raises(KeyError):
        reg.get_suite("missing")
    with pytest.raises(KeyError):
        reg.get_agent("missing")
