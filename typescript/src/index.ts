/**
 * evalforge - Agent Evaluation Harness (TypeScript)
 *
 * Main entry point.
 */

export { EvalHarness } from "./harness.js";
export type { EvalHarnessOptions, RunOptions } from "./harness.js";

export { TestCase } from "./testCase.js";
export type {
  TestCaseOptions,
  ScoringCriteria,
  ScoringStrategy,
  TestResult,
  SuiteResult,
} from "./testCase.js";
export { resultStatus, suiteStats, suiteToDict } from "./testCase.js";

export { Scorer } from "./scorer.js";
export type { LLMJudgeFn } from "./scorer.js";
export {
  exactMatch,
  fuzzyMatch,
  containsMatch,
  jsonMatch,
  llmJudge,
  semanticMatch,
  customScorer,
} from "./scorer.js";

export { Runner } from "./runner.js";
export type { RunnerOptions, AgentFn } from "./runner.js";

export {
  printReport,
  toJSON,
  saveJSON,
  toHTML,
  saveHTML,
  RegressionTracker,
} from "./reporter.js";

export { Registry, registry } from "./registry.js";

export {
  EvalLogger,
  WebhookNotifier,
  buildEvalMetrics,
  exportPrometheus,
} from "./observability.js";
export type { EvalEvent, EvalMetrics } from "./observability.js";
