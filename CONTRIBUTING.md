# Contributing to evalforge

Thanks for your interest in improving evalforge.

## Development setup

```bash
# Python
pip install -e "python/[all]"
cd python && pytest --cov=evalforge

# TypeScript
cd ../typescript && npm install && npm run build
```

## Pull request guidelines

- Keep changes focused and small when possible.
- Add or update tests for behavior changes.
- Update docs and changelog entries when user-facing behavior changes.
- Ensure CI is green before requesting review.

## Adding a new scoring strategy

New scoring strategies are especially welcome.

1. Implement the strategy in Python at `python/evalforge/scorer.py` and expose it through existing scorer helpers.
2. Mirror the same strategy in TypeScript at `typescript/src/scorer.ts` so both SDKs stay aligned.
3. Add tests for both implementations under `python/tests/` and `typescript/tests/` (or the existing test location for scorer coverage).
4. Document usage in `README.md` and include when it should be used.
5. If the strategy affects CLI output or result schema, include regression/compatibility notes in your PR.

## Reporting issues

Use the issue templates for bug reports and feature requests. For security reports, follow `SECURITY.md`.
