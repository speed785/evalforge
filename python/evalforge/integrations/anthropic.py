"""
Anthropic integration - pre-built runner and LLM judge for Claude models.

Usage::

    from evalforge.integrations.anthropic import AnthropicAgent, anthropic_judge_fn
    from evalforge import EvalHarness, TestCase
    from evalforge.scorer import llm_judge, Scorer

    agent = AnthropicAgent(model="claude-3-5-haiku-20241022")
    scorer = Scorer(llm_judge_fn=anthropic_judge_fn())

    harness = EvalHarness(agent=agent, suite_name="my-suite", scorer=scorer)
    harness.add(TestCase(
        input="Explain async/await in one sentence.",
        expected_output="<contains key concept of awaiting futures>",
        scoring=llm_judge(threshold=0.7),
    ))
    result = harness.run()
"""

from __future__ import annotations

import logging
import os
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)


class AnthropicAgent:
    """
    A simple agent that calls a Claude model via the Anthropic API.

    Input formats accepted:
    - A plain string (becomes a single user turn)
    - A dict with ``messages`` key (list of {role, content} dicts)
    - A list of message dicts

    Returns the text of the first content block.
    """

    def __init__(
        self,
        model: str = "claude-3-5-haiku-20241022",
        api_key: Optional[str] = None,
        system_prompt: Optional[str] = None,
        max_tokens: int = 1024,
        temperature: float = 0.0,
        **extra_kwargs: Any,
    ):
        self.model = model
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        self.system_prompt = system_prompt
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.extra_kwargs = extra_kwargs

    async def __call__(self, input_data: Any) -> str:
        try:
            import anthropic
        except ImportError:
            raise ImportError(
                "anthropic package required for AnthropicAgent. "
                "Install with: pip install anthropic"
            )

        client = anthropic.AsyncAnthropic(api_key=self.api_key)
        messages = self._build_messages(input_data)

        kwargs: dict[str, Any] = dict(
            model=self.model,
            messages=messages,
            max_tokens=self.max_tokens,
            **self.extra_kwargs,
        )
        if self.system_prompt:
            kwargs["system"] = self.system_prompt

        response = await client.messages.create(**kwargs)

        # Extract text from first content block
        for block in response.content:
            if hasattr(block, "text"):
                return block.text
        return ""

    def _build_messages(self, input_data: Any) -> list[dict]:
        if isinstance(input_data, str):
            return [{"role": "user", "content": input_data}]
        elif isinstance(input_data, dict) and "messages" in input_data:
            return input_data["messages"]
        elif isinstance(input_data, list):
            return input_data
        else:
            return [{"role": "user", "content": str(input_data)}]


def anthropic_judge_fn(
    model: str = "claude-3-5-haiku-20241022",
    api_key: Optional[str] = None,
) -> Callable:
    """
    Returns an async LLM judge function backed by a Claude model.

    Usage::

        from evalforge.scorer import Scorer
        scorer = Scorer(llm_judge_fn=anthropic_judge_fn())
    """

    async def judge(prompt: str, expected: Any, actual: Any) -> float:
        try:
            import anthropic
        except ImportError:
            raise ImportError("pip install anthropic")

        resolved_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        client = anthropic.AsyncAnthropic(api_key=resolved_key)

        response = await client.messages.create(
            model=model,
            max_tokens=10,
            system=(
                "You are an impartial evaluator. "
                "Respond with ONLY a decimal number between 0.0 and 1.0."
            ),
            messages=[{"role": "user", "content": prompt}],
        )

        raw = ""
        for block in response.content:
            if hasattr(block, "text"):
                raw = block.text.strip()
                break

        try:
            score = float(raw)
            return max(0.0, min(1.0, score))
        except ValueError:
            logger.warning("LLM judge returned non-numeric value: %r", raw)
            return 0.0

    return judge
