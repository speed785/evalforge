# Changelog

All notable changes to this project will be documented in this file.

## v0.1.0

- Introduced `EvalHarness` for repeatable, measurable agent evaluations.
- Added 7 scoring strategies: `exact`, `fuzzy`, `contains`, `json_match`, `llm_judge`, `semantic`, and `custom`.
- Shipped CLI commands for `run`, `list`, and `compare` workflows.
- Added regression tracking across historical runs.
- Added webhook notifications for detected regressions.
- Added OpenAI and Anthropic integrations for agents and LLM judging.
- Added observability support with structured logs and metrics.
- Delivered Python and TypeScript API parity.
- Achieved 100% test coverage for core library behavior.
