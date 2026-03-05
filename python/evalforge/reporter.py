"""
Reporter - generates eval reports in multiple formats:
  - CLI table (via rich or plain text fallback)
  - JSON
  - HTML
  - Regression tracking (compare against prior runs)
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Optional

from .test_case import SuiteResult, TestResult

# ---------------------------------------------------------------------------
# CLI / Console reporter
# ---------------------------------------------------------------------------


def print_report(suite: SuiteResult, show_details: bool = True) -> None:
    """Print a formatted report to stdout."""
    try:
        _rich_report(suite, show_details)
    except ImportError:
        _plain_report(suite, show_details)


def _rich_report(suite: SuiteResult, show_details: bool) -> None:
    from rich.console import Console
    from rich.table import Table
    from rich import box

    console = Console()
    duration = ""
    if suite.finished_at:
        duration = f" ({suite.finished_at - suite.started_at:.1f}s)"

    console.print(f"\n[bold cyan]EvalForge Report[/bold cyan] — [bold]{suite.suite_name}[/bold]{duration}")
    console.print(f"Run ID: [dim]{suite.run_id}[/dim]")
    console.print()

    # Summary bar
    pass_pct = suite.pass_rate * 100
    color = "green" if pass_pct >= 80 else ("yellow" if pass_pct >= 50 else "red")
    console.print(
        f"[{color}]●[/{color}] {suite.passed}/{suite.total} passed "
        f"([{color}]{pass_pct:.1f}%[/{color}]) "
        f"• avg score [bold]{suite.avg_score:.3f}[/bold]"
        + (f" • avg latency [bold]{suite.avg_latency_ms:.0f}ms[/bold]" if suite.avg_latency_ms else "")
    )
    console.print()

    if show_details:
        table = Table(box=box.ROUNDED, show_header=True, header_style="bold dim")
        table.add_column("ID", style="dim", width=12)
        table.add_column("Status", width=8)
        table.add_column("Score", width=7)
        table.add_column("Latency", width=9)
        table.add_column("Output / Error")

        for r in suite.results:
            status_str = (
                "[green]PASS[/green]"
                if r.passed
                else ("[red]ERROR[/red]" if r.error else "[yellow]FAIL[/yellow]")
            )
            output = str(r.error or r.actual_output or "")[:80]
            latency = f"{r.latency_ms:.0f}ms" if r.latency_ms else "—"
            table.add_row(
                r.test_case_id,
                status_str,
                f"{r.score:.3f}",
                latency,
                output,
            )

        console.print(table)


def _plain_report(suite: SuiteResult, show_details: bool) -> None:
    duration = ""
    if suite.finished_at:
        duration = f" ({suite.finished_at - suite.started_at:.1f}s)"

    print(f"\n=== EvalForge: {suite.suite_name}{duration} ===")
    print(f"Run ID: {suite.run_id}")
    print(f"Results: {suite.passed}/{suite.total} passed ({suite.pass_rate * 100:.1f}%) | avg score {suite.avg_score:.3f}")
    if suite.avg_latency_ms:
        print(f"Avg latency: {suite.avg_latency_ms:.0f}ms")
    print()

    if show_details:
        header = f"{'ID':<14} {'Status':<8} {'Score':<7} {'Latency':<10} Output"
        print(header)
        print("-" * 70)
        for r in suite.results:
            status = "PASS" if r.passed else ("ERROR" if r.error else "FAIL")
            output = str(r.error or r.actual_output or "")[:50]
            latency = f"{r.latency_ms:.0f}ms" if r.latency_ms else "—"
            print(f"{r.test_case_id:<14} {status:<8} {r.score:<7.3f} {latency:<10} {output}")

    print()


# ---------------------------------------------------------------------------
# JSON reporter
# ---------------------------------------------------------------------------


def to_json(suite: SuiteResult, indent: int = 2) -> str:
    """Serialise SuiteResult to JSON string."""
    return json.dumps(suite.to_dict(), indent=indent, default=str)


def save_json(suite: SuiteResult, path: str | Path) -> Path:
    """Save JSON report to disk."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(to_json(suite))
    return p


# ---------------------------------------------------------------------------
# HTML reporter
# ---------------------------------------------------------------------------


def to_html(suite: SuiteResult) -> str:
    """Generate a self-contained HTML report."""
    rows = ""
    for r in suite.results:
        status_class = "pass" if r.passed else ("error" if r.error else "fail")
        status_label = "PASS" if r.passed else ("ERROR" if r.error else "FAIL")
        output = str(r.error or r.actual_output or "")[:200]
        latency = f"{r.latency_ms:.0f}ms" if r.latency_ms else "—"
        rows += f"""
        <tr class="{status_class}">
          <td>{r.test_case_id}</td>
          <td><span class="badge {status_class}">{status_label}</span></td>
          <td>{r.score:.3f}</td>
          <td>{latency}</td>
          <td class="output">{output}</td>
        </tr>"""

    pass_pct = suite.pass_rate * 100
    gauge_color = "#22c55e" if pass_pct >= 80 else ("#f59e0b" if pass_pct >= 50 else "#ef4444")

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>EvalForge — {suite.suite_name}</title>
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: #0f172a; color: #e2e8f0; padding: 2rem; }}
    h1 {{ font-size: 1.5rem; color: #38bdf8; margin-bottom: 0.25rem; }}
    .meta {{ color: #94a3b8; font-size: 0.85rem; margin-bottom: 1.5rem; }}
    .summary {{ display: flex; gap: 1.5rem; margin-bottom: 2rem; flex-wrap: wrap; }}
    .card {{ background: #1e293b; border-radius: 0.75rem; padding: 1rem 1.5rem; min-width: 140px; }}
    .card .label {{ font-size: 0.75rem; color: #64748b; text-transform: uppercase; letter-spacing: 0.05em; }}
    .card .value {{ font-size: 1.75rem; font-weight: 700; color: #f1f5f9; margin-top: 0.25rem; }}
    .pass-rate {{ color: {gauge_color} !important; }}
    table {{ width: 100%; border-collapse: collapse; background: #1e293b; border-radius: 0.75rem; overflow: hidden; }}
    th {{ background: #0f172a; padding: 0.75rem 1rem; text-align: left; font-size: 0.75rem; text-transform: uppercase; letter-spacing: 0.05em; color: #64748b; }}
    td {{ padding: 0.6rem 1rem; border-bottom: 1px solid #0f172a; font-size: 0.875rem; }}
    tr:last-child td {{ border-bottom: none; }}
    tr.pass {{ background: rgba(34,197,94,0.05); }}
    tr.fail {{ background: rgba(234,179,8,0.05); }}
    tr.error {{ background: rgba(239,68,68,0.08); }}
    .badge {{ display: inline-block; padding: 0.15rem 0.5rem; border-radius: 9999px; font-size: 0.7rem; font-weight: 700; }}
    .badge.pass {{ background: #14532d; color: #86efac; }}
    .badge.fail {{ background: #713f12; color: #fde68a; }}
    .badge.error {{ background: #7f1d1d; color: #fca5a5; }}
    .output {{ font-family: monospace; color: #94a3b8; max-width: 400px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }}
  </style>
</head>
<body>
  <h1>EvalForge — {suite.suite_name}</h1>
  <div class="meta">Run ID: {suite.run_id} &nbsp;|&nbsp; {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(suite.started_at))}</div>
  <div class="summary">
    <div class="card"><div class="label">Pass Rate</div><div class="value pass-rate">{pass_pct:.1f}%</div></div>
    <div class="card"><div class="label">Passed</div><div class="value">{suite.passed}/{suite.total}</div></div>
    <div class="card"><div class="label">Avg Score</div><div class="value">{suite.avg_score:.3f}</div></div>
    <div class="card"><div class="label">Avg Latency</div><div class="value">{f"{suite.avg_latency_ms:.0f}ms" if suite.avg_latency_ms else "—"}</div></div>
  </div>
  <table>
    <thead>
      <tr><th>ID</th><th>Status</th><th>Score</th><th>Latency</th><th>Output / Error</th></tr>
    </thead>
    <tbody>{rows}
    </tbody>
  </table>
</body>
</html>"""


def save_html(suite: SuiteResult, path: str | Path) -> Path:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(to_html(suite))
    return p


# ---------------------------------------------------------------------------
# Regression tracker
# ---------------------------------------------------------------------------


class RegressionTracker:
    """
    Persists run history to a JSONL file and surfaces regressions
    (test cases that previously passed but now fail).

    Usage::

        tracker = RegressionTracker("eval_history.jsonl")
        regressions = tracker.compare_and_save(current_result)
        if regressions:
            print(f"⚠ {len(regressions)} regressions detected!")
    """

    def __init__(self, history_path: str | Path = "eval_history.jsonl"):
        self.history_path = Path(history_path)

    def compare_and_save(self, suite: SuiteResult) -> list[str]:
        """
        Compare against the most recent run.
        Returns a list of test_case_ids that regressed.
        """
        prior = self._load_last_run(suite.suite_name)
        regressions: list[str] = []

        if prior:
            prior_pass = {r["test_case_id"] for r in prior["results"] if r["passed"]}
            for r in suite.results:
                if not r.passed and r.test_case_id in prior_pass:
                    regressions.append(r.test_case_id)

        self._append(suite)
        return regressions

    def load_history(self, suite_name: str) -> list[dict]:
        """Load all historical runs for a suite."""
        if not self.history_path.exists():
            return []
        runs = []
        for line in self.history_path.read_text().splitlines():
            if not line.strip():
                continue
            try:
                entry = json.loads(line)
                if entry.get("suite_name") == suite_name:
                    runs.append(entry)
            except json.JSONDecodeError:
                continue
        return runs

    def _load_last_run(self, suite_name: str) -> Optional[dict]:
        history = self.load_history(suite_name)
        return history[-1] if history else None

    def _append(self, suite: SuiteResult) -> None:
        self.history_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.history_path, "a") as f:
            f.write(json.dumps(suite.to_dict(), default=str) + "\n")
