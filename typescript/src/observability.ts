import { SuiteResult, suiteStats, TestResult } from "./testCase.js";

export type EvalEvent =
  | "suite_started"
  | "test_started"
  | "test_completed"
  | "test_failed"
  | "suite_completed"
  | "regression_detected";

export interface EvalMetrics {
  totalRuns: number;
  totalTests: number;
  passRate: number;
  avgLatencyMs: number;
  p95LatencyMs: number;
  regressionCount: number;
  llmJudgeCalls: number;
  llmJudgeCostEstimate: number;
  strategyPassRates: Record<string, number>;
  strategyP95LatencyMs: Record<string, number>;
}

export class EvalLogger {
  constructor(private suiteName: string, private sink: (line: string) => void = console.info) {}

  logEvent(event: EvalEvent, payload: Record<string, unknown> = {}): void {
    this.sink(
      JSON.stringify({
        event,
        timestamp: new Date().toISOString(),
        suite_name: this.suiteName,
        ...payload,
      })
    );
  }
}

export function buildEvalMetrics(
  suite: SuiteResult,
  opts: { totalRuns?: number; regressionCount?: number; llmCostPerCall?: number } = {}
): EvalMetrics {
  const stats = suiteStats(suite);
  const latencies = suite.results
    .map((r) => r.latencyMs)
    .filter((v): v is number => v !== undefined);

  const strategyBuckets = new Map<string, TestResult[]>();
  let llmJudgeCalls = 0;
  for (const result of suite.results) {
    const scorerType = String(result.metadata?.scorer_type ?? "unknown");
    const bucket = strategyBuckets.get(scorerType) ?? [];
    bucket.push(result);
    strategyBuckets.set(scorerType, bucket);
    if (scorerType === "llm_judge") {
      llmJudgeCalls += 1;
    }
  }

  const strategyPassRates: Record<string, number> = {};
  const strategyP95LatencyMs: Record<string, number> = {};

  for (const [scorerType, grouped] of strategyBuckets.entries()) {
    strategyPassRates[scorerType] = grouped.filter((r) => r.passed).length / grouped.length;
    const groupedLatencies = grouped
      .map((r) => r.latencyMs)
      .filter((v): v is number => v !== undefined);
    strategyP95LatencyMs[scorerType] = percentile(groupedLatencies, 95);
  }

  return {
    totalRuns: opts.totalRuns ?? 1,
    totalTests: stats.total,
    passRate: stats.passRate,
    avgLatencyMs: stats.avgLatencyMs ?? 0,
    p95LatencyMs: percentile(latencies, 95),
    regressionCount: opts.regressionCount ?? 0,
    llmJudgeCalls,
    llmJudgeCostEstimate: llmJudgeCalls * (opts.llmCostPerCall ?? 0.002),
    strategyPassRates,
    strategyP95LatencyMs,
  };
}

export function exportPrometheus(metrics: EvalMetrics): string {
  const lines = [
    `evalforge_total_runs ${metrics.totalRuns}`,
    `evalforge_total_tests ${metrics.totalTests}`,
    `evalforge_pass_rate ${metrics.passRate}`,
    `evalforge_avg_latency_ms ${metrics.avgLatencyMs}`,
    `evalforge_p95_latency_ms ${metrics.p95LatencyMs}`,
    `evalforge_regression_count ${metrics.regressionCount}`,
    `evalforge_llm_judge_calls ${metrics.llmJudgeCalls}`,
    `evalforge_llm_judge_cost_estimate ${metrics.llmJudgeCostEstimate}`,
  ];

  for (const [scorerType, value] of Object.entries(metrics.strategyPassRates)) {
    lines.push(`evalforge_strategy_pass_rate{scorer_type="${scorerType}"} ${value}`);
  }
  for (const [scorerType, value] of Object.entries(metrics.strategyP95LatencyMs)) {
    lines.push(`evalforge_strategy_p95_latency_ms{scorer_type="${scorerType}"} ${value}`);
  }

  return `${lines.join("\n")}\n`;
}

export class WebhookNotifier {
  constructor(private webhookUrl?: string) {}

  async notifyRegression(
    suiteName: string,
    regressions: string[],
    metrics: EvalMetrics
  ): Promise<boolean> {
    if (!this.webhookUrl) {
      return false;
    }

    const payload = {
      text: `EvalForge regression detected for suite '${suiteName}' (${regressions.length} cases).`,
      blocks: [
        {
          type: "section",
          text: {
            type: "mrkdwn",
            text:
              `*EvalForge regression detected*\n` +
              `Suite: \`${suiteName}\`\n` +
              `Regressions: ${regressions.join(", ")}\n` +
              `Pass rate: ${(metrics.passRate * 100).toFixed(1)}%`,
          },
        },
      ],
    };

    try {
      const response = await fetch(this.webhookUrl, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      return response.ok;
    } catch {
      return false;
    }
  }
}

function percentile(values: number[], p: number): number {
  if (values.length === 0) {
    return 0;
  }
  const ordered = [...values].sort((a, b) => a - b);
  const rank = (p / 100) * (ordered.length - 1);
  const lo = Math.floor(rank);
  const hi = Math.ceil(rank);
  if (lo === hi) {
    return ordered[lo];
  }
  const ratio = rank - lo;
  return ordered[lo] * (1 - ratio) + ordered[hi] * ratio;
}
