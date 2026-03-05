from __future__ import annotations

import argparse
import asyncio
import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

from .registry import registry
from .reporter import RegressionTracker, print_report, to_html
from .runner import Runner


def _load_python_file(file_path: str) -> None:
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")

    module_name = f"evalforge_cli_{path.stem}"
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load module from {path}")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)


def _parse_tags(raw: str | None) -> list[str] | None:
    if not raw:
        return None
    tags = [tag.strip() for tag in raw.split(",") if tag.strip()]
    return tags or None


def _choose_one(name: str, choices: list[str], selected: str | None) -> str:
    if selected:
        if selected not in choices:
            raise ValueError(f"Unknown {name} '{selected}'. Available: {choices}")
        return selected
    if not choices:
        raise ValueError(f"No {name}s registered")
    if len(choices) > 1:
        raise ValueError(
            f"Multiple {name}s registered: {choices}. Use --{name} to select one."
        )
    return choices[0]


def _print_run(result: Any, output: str) -> None:
    if output == "cli":
        print_report(result)
    elif output == "json":
        print(json.dumps(result.to_dict(), indent=2, default=str))
    else:
        print(to_html(result))


def _cmd_list(args: argparse.Namespace) -> int:
    if args.file:
        _load_python_file(args.file)

    suites = sorted(registry.list_suites())
    agents = sorted(registry.list_agents())

    if args.output == "json":
        print(json.dumps({"suites": suites, "agents": agents}, indent=2))
        return 0

    print("Suites:")
    if suites:
        for suite in suites:
            print(f"  - {suite}")
    else:
        print("  (none)")

    print("Agents:")
    if agents:
        for agent in agents:
            print(f"  - {agent}")
    else:
        print("  (none)")
    return 0


def _cmd_run(args: argparse.Namespace) -> int:
    _load_python_file(args.file)

    suites = sorted(registry.list_suites())
    agents = sorted(registry.list_agents())
    suite_name = _choose_one("suite", suites, args.suite)
    agent_name = _choose_one("agent", agents, args.agent)

    cases = registry.get_suite(suite_name)
    tags = _parse_tags(args.tags)
    if tags:
        cases = [tc for tc in cases if any(tag in tc.tags for tag in tags)]

    runner = Runner(
        agent=registry.get_agent(agent_name),
        suite_name=suite_name,
        concurrency=args.concurrency,
        default_timeout=args.timeout,
    )
    result = asyncio.run(runner.run(cases))
    _print_run(result, args.output)
    return 0 if result.pass_rate == 1.0 else 1


def _cmd_compare(args: argparse.Namespace) -> int:
    tracker = RegressionTracker(args.history_file)
    if args.suite:
        runs = tracker.load_history(args.suite)
    else:
        lines = Path(args.history_file).read_text().splitlines() if Path(args.history_file).exists() else []
        parsed = [json.loads(line) for line in lines if line.strip()]
        if not parsed:
            print("No runs found in history file")
            return 1
        last_suite = parsed[-1].get("suite_name")
        runs = [r for r in parsed if r.get("suite_name") == last_suite]

    if len(runs) < 2:
        print("Need at least two runs to compare")
        return 1

    prev = runs[-2]
    curr = runs[-1]
    prev_pass = {r["test_case_id"] for r in prev["results"] if r.get("passed")}
    curr_fail = {r["test_case_id"] for r in curr["results"] if not r.get("passed")}
    regressions = sorted(prev_pass.intersection(curr_fail))

    payload = {
        "suite_name": curr.get("suite_name"),
        "previous_run_id": prev.get("run_id"),
        "current_run_id": curr.get("run_id"),
        "previous_pass_rate": prev.get("pass_rate"),
        "current_pass_rate": curr.get("pass_rate"),
        "regressions": regressions,
    }

    if args.output == "json":
        print(json.dumps(payload, indent=2))
    else:
        print(f"Suite: {payload['suite_name']}")
        print(f"Previous run: {payload['previous_run_id']} ({payload['previous_pass_rate']:.1%})")
        print(f"Current run : {payload['current_run_id']} ({payload['current_pass_rate']:.1%})")
        if regressions:
            print("Regressions:")
            for case_id in regressions:
                print(f"  - {case_id}")
        else:
            print("Regressions: none")

    return 1 if regressions else 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="evalforge", description="EvalForge CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser("run", help="Run eval suite from a Python file")
    run_parser.add_argument("file", help="Python file that registers suites/agents")
    run_parser.add_argument("--suite", help="Registered suite name")
    run_parser.add_argument("--agent", help="Registered agent name")
    run_parser.add_argument("--tags", help="Comma-separated list of tags")
    run_parser.add_argument("--concurrency", type=int, default=1)
    run_parser.add_argument("--output", choices=["json", "html", "cli"], default="cli")
    run_parser.add_argument("--timeout", type=float, default=30.0)
    run_parser.set_defaults(func=_cmd_run)

    list_parser = subparsers.add_parser("list", help="List registered suites and agents")
    list_parser.add_argument("file", nargs="?", help="Optional Python file to load before listing")
    list_parser.add_argument("--output", choices=["json", "cli"], default="cli")
    list_parser.set_defaults(func=_cmd_list)

    compare_parser = subparsers.add_parser("compare", help="Compare latest two runs from history JSONL")
    compare_parser.add_argument("history_file", help="Path to regression history JSONL")
    compare_parser.add_argument("--suite", help="Optional suite name")
    compare_parser.add_argument("--output", choices=["json", "cli"], default="cli")
    compare_parser.add_argument("--tags", help="Unused compatibility flag", default=None)
    compare_parser.add_argument("--concurrency", type=int, default=1)
    compare_parser.add_argument("--timeout", type=float, default=30.0)
    compare_parser.set_defaults(func=_cmd_compare)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.func(args))
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
