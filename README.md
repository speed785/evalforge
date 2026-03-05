# evalforge ⚒

**Agent Evaluation Harness** — write repeatable, measurable evals for AI agents.

[![Python](https://img.shields.io/badge/python-3.10%2B-blue?logo=python)](python/)
[![TypeScript](https://img.shields.io/badge/typescript-5.4%2B-blue?logo=typescript)](typescript/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Status: Alpha](https://img.shields.io/badge/status-alpha-orange.svg)]()

---

## Why EvalForge?

Most eval tooling is either too coupled to a specific LLM provider, too
heavyweight, or treats evals as an afterthought bolted onto a chat app.

**EvalForge** is a standalone, provider-agnostic harness that lets you:

- Define test cases with input, expected output, and scoring criteria
- Run any agent (sync or async) against those cases
- Score results with exact match, fuzzy match, LLM-as-judge, or your own function
- Generate CLI tables, JSON, and HTML reports
- Track results over time and surface regressions automatically

No vendor lock-in. No hidden magic. Just clean, composable eval primitives.

---

## Quick start (Python)

```bash
pip install -e python/
# optional extras:
pip install "evalforge[all]"   # rapidfuzz + rich + openai + anthropic
```

```python
from evalforge import EvalHarness, TestCase
from evalforge.scorer import fuzzy_match, exact_match

def my_agent(prompt: str) -> str:
    return "The capital of France is Paris."

harness = EvalHarness(agent=my_agent, suite_name="geo-smoke")

harness.add(TestCase(
    id="france-capital",
    description="Knows EU capitals",
    input="What is the capital of France?",
    expected_output="Paris",
    scoring=fuzzy_match(threshold=0.8),
    tags=["geography"],
))

result = harness.run(report_html="reports/run.html")
# → prints a rich table to the terminal
# → saves an HTML report to reports/run.html
```

---

## Quick start (TypeScript)

```bash
cd typescript && npm install
```

```typescript
import { EvalHarness, TestCase } from "evalforge";
import { fuzzyMatch } from "evalforge/scorer";

const harness = new EvalHarness({
  agent: async (input) => "The capital of France is Paris.",
  suiteName: "geo-smoke",
});

harness.add(new TestCase({
  id: "france-capital",
  input: "What is the capital of France?",
  expectedOutput: "Paris",
  scoring: fuzzyMatch(0.8),
  tags: ["geography"],
}));

const result = await harness.run({ reportHtml: "reports/run.html" });
```

---

## Scoring strategies

| Strategy     | Description                                    |
|--------------|------------------------------------------------|
| `exact`      | Exact string equality (default)                |
| `fuzzy`      | Levenshtein / token similarity                 |
| `contains`   | Expected is a substring of actual              |
| `json_match` | Deep-compare JSON structures (with key ignore) |
| `llm_judge`  | Use an LLM to score correctness (0–1)          |
| `custom`     | Bring your own scoring function                |

```python
from evalforge.scorer import (
    exact_match, fuzzy_match, contains_match,
    json_match, llm_judge, custom_scorer,
)

# Exact match
scoring = exact_match()

# Fuzzy (requires rapidfuzz)
scoring = fuzzy_match(threshold=0.8)

# Expected is a substring
scoring = contains_match()

# JSON deep compare, ignore "timestamp" key
scoring = json_match(ignore_keys=["timestamp"])

# LLM as judge — pass a judge function
scoring = llm_judge(threshold=0.7)

# Fully custom
def my_scorer(expected, actual) -> float:
    return 1.0 if len(actual) > 10 else 0.0
scoring = custom_scorer(my_scorer, threshold=1.0)
```

---

## OpenAI & Anthropic integrations

```python
# OpenAI
from evalforge.integrations.openai import OpenAIAgent, openai_judge_fn
from evalforge import EvalHarness
from evalforge.scorer import Scorer, llm_judge

agent  = OpenAIAgent(model="gpt-4o")
scorer = Scorer(llm_judge_fn=openai_judge_fn(model="gpt-4o-mini"))
harness = EvalHarness(agent=agent, suite_name="gpt4o-suite", scorer=scorer)

# Anthropic
from evalforge.integrations.anthropic import AnthropicAgent, anthropic_judge_fn

agent  = AnthropicAgent(model="claude-3-5-haiku-20241022")
scorer = Scorer(llm_judge_fn=anthropic_judge_fn())
harness = EvalHarness(agent=agent, suite_name="claude-suite", scorer=scorer)
```

---

## Registry (reusable suites + agents)

```python
from evalforge.registry import registry
from evalforge import TestCase
from evalforge.scorer import contains_match

@registry.suite("support-faq")
def support_faq():
    return [
        TestCase(
            id="refund",
            input="What is your refund policy?",
            expected_output="30-day",
            scoring=contains_match(),
        ),
    ]

@registry.agent("support-bot")
async def support_bot(prompt):
    return "We offer a 30-day money back guarantee."

# Run by name
import asyncio
result = asyncio.run(registry.run("support-faq", "support-bot"))
```

---

## Regression tracking

```python
from evalforge import EvalHarness
from evalforge.reporter import RegressionTracker

# Pass history_path to EvalHarness:
harness = EvalHarness(
    agent=my_agent,
    suite_name="my-suite",
    history_path="eval_history.jsonl",   # appends every run
)
result = harness.run()

# Or use RegressionTracker directly:
tracker = RegressionTracker("eval_history.jsonl")
regressions = tracker.compare_and_save(result)
if regressions:
    print(f"Regressions: {regressions}")
```

---

## Reports

```python
# Console (rich table)
harness.run()   # verbose=True by default

# JSON
harness.run(report_json="out/results.json")

# HTML (self-contained, dark theme)
harness.run(report_html="out/results.html")
```

---

## Examples

| File | Description |
|------|-------------|
| [`examples/example_basic.py`](examples/example_basic.py) | Basic suite with all scoring strategies, mock agent |
| [`examples/example_regression.py`](examples/example_regression.py) | Regression tracking across v1/v2 agents |
| [`typescript/examples/example_basic.ts`](typescript/examples/example_basic.ts) | TypeScript version of the basic example |
| [`typescript/examples/example_regression.ts`](typescript/examples/example_regression.ts) | TypeScript regression tracking |

---

## Project structure

```
evalforge/
├── python/
│   ├── evalforge/
│   │   ├── __init__.py
│   │   ├── harness.py          # EvalHarness — main entry point
│   │   ├── test_case.py        # TestCase, ScoringCriteria, TestResult
│   │   ├── scorer.py           # Scoring strategies
│   │   ├── runner.py           # Async runner with timeout + retries
│   │   ├── reporter.py         # CLI, JSON, HTML, regression tracker
│   │   ├── registry.py         # Suite + agent registry
│   │   └── integrations/
│   │       ├── openai.py       # OpenAIAgent + openai_judge_fn
│   │       └── anthropic.py    # AnthropicAgent + anthropic_judge_fn
│   ├── setup.py
│   └── requirements.txt
├── typescript/
│   ├── src/
│   │   ├── index.ts
│   │   ├── harness.ts
│   │   ├── testCase.ts
│   │   ├── scorer.ts
│   │   ├── runner.ts
│   │   ├── reporter.ts
│   │   ├── registry.ts
│   │   └── integrations/
│   │       ├── openai.ts
│   │       └── anthropic.ts
│   ├── examples/
│   ├── package.json
│   └── tsconfig.json
└── examples/                   # Standalone Python examples
```

---

## Contributing

PRs welcome. Open an issue first for large changes.

```bash
# Python dev setup
pip install -e "python/[all]"

# TypeScript dev setup
cd typescript && npm install && npm run build
```

---

## License

MIT — see [LICENSE](LICENSE).
