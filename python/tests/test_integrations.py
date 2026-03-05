# pyright: reportMissingImports=false

import asyncio
import builtins

import pytest

from evalforge.integrations.anthropic import AnthropicAgent, anthropic_judge_fn
from evalforge.integrations.openai import OpenAIAgent, openai_judge_fn


def test_openai_agent_build_messages():
    agent = OpenAIAgent(system_prompt="sys")
    msgs = agent._build_messages("hello")
    assert msgs[0]["role"] == "system"
    assert msgs[1]["role"] == "user"

    msgs = agent._build_messages({"messages": [{"role": "user", "content": "x"}]})
    assert msgs[-1]["content"] == "x"


def test_anthropic_agent_build_messages():
    agent = AnthropicAgent()
    assert agent._build_messages("hello")[0]["content"] == "hello"
    assert agent._build_messages([{"role": "user", "content": "x"}])[0]["content"] == "x"


def test_openai_import_errors(monkeypatch):
    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "openai":
            raise ImportError("missing openai")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    with pytest.raises(ImportError):
        asyncio.run(OpenAIAgent()("hello"))
    with pytest.raises(ImportError):
        asyncio.run(openai_judge_fn()("prompt", "exp", "act"))


def test_anthropic_import_errors(monkeypatch):
    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "anthropic":
            raise ImportError("missing anthropic")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    with pytest.raises(ImportError):
        asyncio.run(AnthropicAgent()("hello"))
    with pytest.raises(ImportError):
        asyncio.run(anthropic_judge_fn()("prompt", "exp", "act"))
