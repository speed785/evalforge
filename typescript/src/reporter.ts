/**
 * reporter.ts - CLI table, JSON, HTML reporting and regression tracking.
 */

import { appendFileSync, mkdirSync, readFileSync, writeFileSync } from "fs";
import { dirname } from "path";
import {
  SuiteResult,
  TestResult,
  resultStatus,
  suiteStats,
  suiteToDict,
} from "./testCase.js";

// ---------------------------------------------------------------------------
// Console reporter
// ---------------------------------------------------------------------------

export function printReport(suite: SuiteResult, showDetails = true): void {
  const stats = suiteStats(suite);
  const duration = suite.finishedAt
    ? ` (${((suite.finishedAt - suite.startedAt) / 1000).toFixed(1)}s)`
    : "";

  const passPct = (stats.passRate * 100).toFixed(1);
  const indicator = stats.passRate >= 0.8 ? "✓" : stats.passRate >= 0.5 ? "~" : "✗";

  console.log(`\n${"─".repeat(60)}`);
  console.log(`EvalForge — ${suite.suiteName}${duration}`);
  console.log(`Run ID: ${suite.runId}`);
  console.log(`─${"─".repeat(59)}`);
  console.log(
    `${indicator} ${stats.passed}/${stats.total} passed (${passPct}%)` +
      `  avg score ${stats.avgScore.toFixed(3)}` +
      (stats.avgLatencyMs !== undefined
        ? `  avg latency ${stats.avgLatencyMs.toFixed(0)}ms`
        : "")
  );

  if (showDetails) {
    console.log();
    const header = `${"ID".padEnd(14)} ${"Status".padEnd(8)} ${"Score".padEnd(7)} ${"Latency".padEnd(10)} Output`;
    console.log(header);
    console.log("─".repeat(70));

    for (const r of suite.results) {
      const status = resultStatus(r).toUpperCase().padEnd(8);
      const score = r.score.toFixed(3).padEnd(7);
      const latency = (
        r.latencyMs !== undefined ? `${r.latencyMs.toFixed(0)}ms` : "—"
      ).padEnd(10);
      const output = String(r.error ?? r.actualOutput ?? "").slice(0, 50);
      console.log(`${r.testCaseId.padEnd(14)} ${status} ${score} ${latency} ${output}`);
    }
  }
  console.log();
}

// ---------------------------------------------------------------------------
// JSON reporter
// ---------------------------------------------------------------------------

export function toJSON(suite: SuiteResult, indent = 2): string {
  return JSON.stringify(suiteToDict(suite), null, indent);
}

export function saveJSON(suite: SuiteResult, path: string): void {
  mkdirSync(dirname(path), { recursive: true });
  writeFileSync(path, toJSON(suite), "utf-8");
}

// ---------------------------------------------------------------------------
// HTML reporter
// ---------------------------------------------------------------------------

export function toHTML(suite: SuiteResult): string {
  const stats = suiteStats(suite);
  const passPct = (stats.passRate * 100).toFixed(1);
  const gaugeColor =
    stats.passRate >= 0.8
      ? "#22c55e"
      : stats.passRate >= 0.5
      ? "#f59e0b"
      : "#ef4444";

  const rows = suite.results
    .map((r) => {
      const status = resultStatus(r);
      const label = status.toUpperCase();
      const output = String(r.error ?? r.actualOutput ?? "").slice(0, 200);
      const latency = r.latencyMs !== undefined ? `${r.latencyMs.toFixed(0)}ms` : "—";
      return `
        <tr class="${status}">
          <td>${r.testCaseId}</td>
          <td><span class="badge ${status}">${label}</span></td>
          <td>${r.score.toFixed(3)}</td>
          <td>${latency}</td>
          <td class="output">${escapeHtml(output)}</td>
        </tr>`;
    })
    .join("\n");

  const ts = new Date(suite.startedAt).toISOString().replace("T", " ").slice(0, 19);

  return `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>EvalForge — ${suite.suiteName}</title>
  <style>
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: #0f172a; color: #e2e8f0; padding: 2rem; }
    h1 { font-size: 1.5rem; color: #38bdf8; margin-bottom: 0.25rem; }
    .meta { color: #94a3b8; font-size: 0.85rem; margin-bottom: 1.5rem; }
    .summary { display: flex; gap: 1.5rem; margin-bottom: 2rem; flex-wrap: wrap; }
    .card { background: #1e293b; border-radius: 0.75rem; padding: 1rem 1.5rem; min-width: 140px; }
    .card .label { font-size: 0.75rem; color: #64748b; text-transform: uppercase; letter-spacing: 0.05em; }
    .card .value { font-size: 1.75rem; font-weight: 700; color: #f1f5f9; margin-top: 0.25rem; }
    .pass-rate { color: ${gaugeColor} !important; }
    table { width: 100%; border-collapse: collapse; background: #1e293b; border-radius: 0.75rem; overflow: hidden; }
    th { background: #0f172a; padding: 0.75rem 1rem; text-align: left; font-size: 0.75rem; text-transform: uppercase; letter-spacing: 0.05em; color: #64748b; }
    td { padding: 0.6rem 1rem; border-bottom: 1px solid #0f172a; font-size: 0.875rem; }
    tr:last-child td { border-bottom: none; }
    tr.pass { background: rgba(34,197,94,0.05); }
    tr.fail { background: rgba(234,179,8,0.05); }
    tr.error { background: rgba(239,68,68,0.08); }
    .badge { display: inline-block; padding: 0.15rem 0.5rem; border-radius: 9999px; font-size: 0.7rem; font-weight: 700; }
    .badge.pass { background: #14532d; color: #86efac; }
    .badge.fail { background: #713f12; color: #fde68a; }
    .badge.error { background: #7f1d1d; color: #fca5a5; }
    .output { font-family: monospace; color: #94a3b8; max-width: 400px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  </style>
</head>
<body>
  <h1>EvalForge — ${suite.suiteName}</h1>
  <div class="meta">Run ID: ${suite.runId} &nbsp;|&nbsp; ${ts}</div>
  <div class="summary">
    <div class="card"><div class="label">Pass Rate</div><div class="value pass-rate">${passPct}%</div></div>
    <div class="card"><div class="label">Passed</div><div class="value">${stats.passed}/${stats.total}</div></div>
    <div class="card"><div class="label">Avg Score</div><div class="value">${stats.avgScore.toFixed(3)}</div></div>
    <div class="card"><div class="label">Avg Latency</div><div class="value">${stats.avgLatencyMs !== undefined ? `${stats.avgLatencyMs.toFixed(0)}ms` : "—"}</div></div>
  </div>
  <table>
    <thead>
      <tr><th>ID</th><th>Status</th><th>Score</th><th>Latency</th><th>Output / Error</th></tr>
    </thead>
    <tbody>${rows}
    </tbody>
  </table>
</body>
</html>`;
}

export function saveHTML(suite: SuiteResult, path: string): void {
  mkdirSync(dirname(path), { recursive: true });
  writeFileSync(path, toHTML(suite), "utf-8");
}

function escapeHtml(s: string): string {
  return s
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

// ---------------------------------------------------------------------------
// Regression tracker
// ---------------------------------------------------------------------------

export class RegressionTracker {
  constructor(private historyPath = "eval_history.jsonl") {}

  compareAndSave(suite: SuiteResult): string[] {
    const prior = this.loadLastRun(suite.suiteName);
    const regressions: string[] = [];

    if (prior) {
      const priorPass = new Set(
        prior.results.filter((r: TestResult) => r.passed).map((r: TestResult) => r.testCaseId)
      );
      for (const r of suite.results) {
        if (!r.passed && priorPass.has(r.testCaseId)) {
          regressions.push(r.testCaseId);
        }
      }
    }

    this.append(suite);
    return regressions;
  }

  loadHistory(suiteName: string): SuiteResult[] {
    try {
      const content = readFileSync(this.historyPath, "utf-8");
      return content
        .split("\n")
        .filter((l) => l.trim())
        .map((l) => JSON.parse(l) as SuiteResult)
        .filter((r) => r.suiteName === suiteName);
    } catch {
      return [];
    }
  }

  private loadLastRun(suiteName: string): SuiteResult | undefined {
    const history = this.loadHistory(suiteName);
    return history[history.length - 1];
  }

  private append(suite: SuiteResult): void {
    mkdirSync(dirname(this.historyPath), { recursive: true });
    appendFileSync(this.historyPath, JSON.stringify(suiteToDict(suite)) + "\n");
  }
}
