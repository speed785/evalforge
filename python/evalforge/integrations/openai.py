"""
OpenAI integration - pre-built runner and LLM judge for OpenAI models.

Usage::

    from evalforge.integrations.openai import OpenAIAgent, openai_judge_fn
    from evalforge import EvalHarness, TestCase
    from evalforge.scorer import llm_judge, Scorer

    agent = OpenAIAgent(model="gpt-4o")
    scorer = Scorer(llm_judge_fn=openai_judge_fn(model="gpt-4o-mini"))

    harness = EvalHarness(agent=agent, suite_name="my-suite", scorer=scorer)
    harness.add(TestCase(
        input={"messages": [{"role": "user", "content": "What is 2+2?"}]},
        expected_output="4",
        scoring=llm_judge(threshold=0.8),
    ))
    result = harness.run()
"""

from __future__ import annotations

import logging
import os
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)


class OpenAIAgent:
    """
    A simple agent that calls an OpenAI chat completion model.

    The agent accepts input in one of two forms:
    - A string (converted to a single user message)
    - A dict with a ``messages`` key (passed directly to the API)

    Returns the content of the first assistant message.
    """

    def __init__(
        self,
        model: str = "gpt-4o-mini",
        api_key: Optional[str] = None,
        system_prompt: Optional[str] = None,
        temperature: float = 0.0,
        max_tokens: int = 1024,
        **extra_kwargs: Any,
    ):
        self.model = model
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY")
        self.system_prompt = system_prompt
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.extra_kwargs = extra_kwargs

    async def __call__(self, input_data: Any) -> str:
        try:
            from openai import AsyncOpenAI
        except ImportError:
            raise ImportError(
                "openai package required for OpenAIAgent. "
                "Install with: pip install openai"
            )

        client = AsyncOpenAI(api_key=self.api_key)

        messages = self._build_messages(input_data)

        response = await client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
            **self.extra_kwargs,
        )

        return response.choices[0].message.content or ""

    def _build_messages(self, input_data: Any) -> list[dict]:
        messages = []

        if self.system_prompt:
            messages.append({"role": "system", "content": self.system_prompt})

        if isinstance(input_data, str):
            messages.append({"role": "user", "content": input_data})
        elif isinstance(input_data, dict) and "messages" in input_data:
            messages.extend(input_data["messages"])
        elif isinstance(input_data, list):
            messages.extend(input_data)
        else:
            messages.append({"role": "user", "content": str(input_data)})

        return messages


def openai_judge_fn(
    model: str = "gpt-4o-mini",
    api_key: Optional[str] = None,
) -> Callable:
    """
    Returns an async LLM judge function backed by an OpenAI model.

    The judge receives the prompt and returns a float in [0, 1].

    Usage::

        from evalforge.scorer import Scorer
        scorer = Scorer(llm_judge_fn=openai_judge_fn("gpt-4o-mini"))
    """

    async def judge(prompt: str, expected: Any, actual: Any) -> float:
        try:
            from openai import AsyncOpenAI
        except ImportError:
            raise ImportError("pip install openai")

        resolved_key = api_key or os.environ.get("OPENAI_API_KEY")
        client = AsyncOpenAI(api_key=resolved_key)

        response = await client.chat.completions.create(
            model=model,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are an impartial evaluator. "
                        "Respond with ONLY a decimal number between 0.0 and 1.0."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            temperature=0.0,
            max_tokens=10,
        )

        raw = (response.choices[0].message.content or "0").strip()
        try:
            score = float(raw)
            return max(0.0, min(1.0, score))
        except ValueError:
            logger.warning("LLM judge returned non-numeric value: %r", raw)
            return 0.0

    return judge
