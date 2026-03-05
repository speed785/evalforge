# pyright: reportMissingImports=false

import asyncio
import builtins
import types

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

    msgs = agent._build_messages(123)
    assert msgs[-1]["content"] == "123"


def test_anthropic_agent_build_messages():
    agent = AnthropicAgent()
    assert agent._build_messages("hello")[0]["content"] == "hello"
    assert agent._build_messages([{"role": "user", "content": "x"}])[0]["content"] == "x"
    assert agent._build_messages(123)[0]["content"] == "123"


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


def test_openai_agent_and_judge_success_paths(monkeypatch):
    captured = {"chat_kwargs": [], "judge_kwargs": []}

    class FakeCompletions:
        async def create(self, **kwargs):
            if kwargs.get("max_tokens") == 10:
                captured["judge_kwargs"].append(kwargs)
                value = "not-a-number" if kwargs["messages"][1]["content"] == "bad" else "1.7"
            else:
                captured["chat_kwargs"].append(kwargs)
                value = "assistant-output"
            return types.SimpleNamespace(
                choices=[types.SimpleNamespace(message=types.SimpleNamespace(content=value))]
            )

    class FakeClient:
        def __init__(self, *args, **kwargs):
            self.chat = types.SimpleNamespace(completions=FakeCompletions())

    monkeypatch.setitem(__import__("sys").modules, "openai", types.SimpleNamespace(AsyncOpenAI=FakeClient))

    agent = OpenAIAgent(system_prompt="sys")
    assert asyncio.run(agent([{"role": "user", "content": "x"}])) == "assistant-output"
    assert captured["chat_kwargs"][0]["messages"][0]["role"] == "system"

    judge = openai_judge_fn(model="gpt-test")
    assert asyncio.run(judge("ok", "e", "a")) == 1.0
    assert asyncio.run(judge("bad", "e", "a")) == 0.0


def test_anthropic_agent_and_judge_success_paths(monkeypatch):
    captured = {"agent_kwargs": [], "judge_kwargs": []}

    class FakeMessages:
        async def create(self, **kwargs):
            if kwargs.get("max_tokens") == 10:
                captured["judge_kwargs"].append(kwargs)
                value = "0.2" if kwargs["messages"][0]["content"] == "ok" else "bad"
                content = [types.SimpleNamespace(text=value)]
            else:
                captured["agent_kwargs"].append(kwargs)
                content = [types.SimpleNamespace(type="text"), types.SimpleNamespace(text="anthropic-output")]
            return types.SimpleNamespace(content=content)

    class FakeAnthropicClient:
        def __init__(self, *args, **kwargs):
            self.messages = FakeMessages()

    monkeypatch.setitem(
        __import__("sys").modules,
        "anthropic",
        types.SimpleNamespace(AsyncAnthropic=FakeAnthropicClient),
    )

    agent = AnthropicAgent(system_prompt="sys")
    assert asyncio.run(agent({"messages": [{"role": "user", "content": "hi"}]})) == "anthropic-output"
    assert "system" in captured["agent_kwargs"][0]

    judge = anthropic_judge_fn(model="claude-test")
    assert asyncio.run(judge("ok", "e", "a")) == 0.2
    assert asyncio.run(judge("bad", "e", "a")) == 0.0


def test_anthropic_agent_returns_empty_when_no_text_blocks(monkeypatch):
    class FakeMessages:
        async def create(self, **_kwargs):
            return types.SimpleNamespace(content=[types.SimpleNamespace(type="tool")])

    class FakeAnthropicClient:
        def __init__(self, *args, **kwargs):
            self.messages = FakeMessages()

    monkeypatch.setitem(
        __import__("sys").modules,
        "anthropic",
        types.SimpleNamespace(AsyncAnthropic=FakeAnthropicClient),
    )

    agent = AnthropicAgent()
    assert asyncio.run(agent("hello")) == ""
