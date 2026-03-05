/**
 * testCase.ts - TestCase types and result structures.
 *
 * The TestCase is the atomic unit of an eval suite. It defines what to
 * send to the agent, what to expect back, and how to score the answer.
 */

import { randomUUID } from "crypto";

// ---------------------------------------------------------------------------
// Scoring criteria
// ---------------------------------------------------------------------------

export type ScoringStrategy =
  | "exact"
  | "fuzzy"
  | "contains"
  | "json_match"
  | "llm_judge"
  | "custom";

export interface ScoringCriteria {
  /** Which scoring strategy to use. */
  strategy: ScoringStrategy;
  /** Minimum score [0–1] to consider the test passed. */
  threshold?: number;
  /** Custom scoring function (strategy = "custom"). */
  scorerFn?: (expected: unknown, actual: unknown) => number | Promise<number>;
  /** Prompt override for LLM judge strategy. */
  llmJudgePrompt?: string;
  /** Keys to ignore when comparing JSON (json_match strategy). */
  jsonIgnoreKeys?: string[];
  /** Fuzzy similarity threshold method hint (not used in TS — uses built-in). */
  fuzzyMethod?: string;
}

// ---------------------------------------------------------------------------
// TestCase
// ---------------------------------------------------------------------------

export interface TestCaseOptions {
  /** Unique identifier (auto-generated if omitted). */
  id?: string;
  /** Human-readable description. */
  description?: string;
  /** Input passed to the agent. */
  input: unknown;
  /** Expected agent output. */
  expectedOutput: unknown;
  /** How to score the response. */
  scoring?: ScoringCriteria;
  /** Tags for filtering / grouping. */
  tags?: string[];
  /** Arbitrary metadata. */
  metadata?: Record<string, unknown>;
  /** Per-test timeout in ms (overrides suite default). */
  timeoutMs?: number;
  /** Number of retries on error. */
  maxRetries?: number;
  /** Optional setup hook called before the agent is invoked. */
  setup?: () => unknown | Promise<unknown>;
  /** Optional teardown hook called after the agent responds. */
  teardown?: (result: unknown) => unknown | Promise<unknown>;
}

export class TestCase {
  readonly id: string;
  readonly description: string;
  readonly input: unknown;
  readonly expectedOutput: unknown;
  readonly scoring: ScoringCriteria;
  readonly tags: string[];
  readonly metadata: Record<string, unknown>;
  readonly timeoutMs?: number;
  readonly maxRetries: number;
  readonly setup?: () => unknown | Promise<unknown>;
  readonly teardown?: (result: unknown) => unknown | Promise<unknown>;

  constructor(opts: TestCaseOptions) {
    this.id = opts.id ?? randomUUID().slice(0, 8);
    this.description = opts.description ?? "";
    this.input = opts.input;
    this.expectedOutput = opts.expectedOutput;
    this.scoring = opts.scoring ?? { strategy: "exact", threshold: 1.0 };
    this.tags = opts.tags ?? [];
    this.metadata = opts.metadata ?? {};
    this.timeoutMs = opts.timeoutMs;
    this.maxRetries = opts.maxRetries ?? 0;
    this.setup = opts.setup;
    this.teardown = opts.teardown;
  }
}

// ---------------------------------------------------------------------------
// TestResult
// ---------------------------------------------------------------------------

export interface TestResult {
  testCaseId: string;
  passed: boolean;
  score: number;
  actualOutput?: unknown;
  error?: string;
  latencyMs?: number;
  retries: number;
  timestamp: number;
  metadata: Record<string, unknown>;
}

export function resultStatus(r: TestResult): "pass" | "fail" | "error" {
  if (r.error) return "error";
  return r.passed ? "pass" : "fail";
}

// ---------------------------------------------------------------------------
// SuiteResult
// ---------------------------------------------------------------------------

export interface SuiteResult {
  suiteName: string;
  runId: string;
  startedAt: number;
  finishedAt?: number;
  results: TestResult[];
  metadata: Record<string, unknown>;
}

export function suiteStats(suite: SuiteResult) {
  const total = suite.results.length;
  const passed = suite.results.filter((r) => r.passed).length;
  const failed = suite.results.filter((r) => !r.passed && !r.error).length;
  const errors = suite.results.filter((r) => !!r.error).length;
  const passRate = total ? passed / total : 0;
  const scores = suite.results.map((r) => r.score);
  const avgScore = scores.length ? scores.reduce((a, b) => a + b, 0) / scores.length : 0;
  const latencies = suite.results
    .map((r) => r.latencyMs)
    .filter((l): l is number => l !== undefined);
  const avgLatencyMs = latencies.length
    ? latencies.reduce((a, b) => a + b, 0) / latencies.length
    : undefined;

  return { total, passed, failed, errors, passRate, avgScore, avgLatencyMs };
}

export function suiteToDict(suite: SuiteResult): Record<string, unknown> {
  const stats = suiteStats(suite);
  return { ...suite, ...stats };
}
