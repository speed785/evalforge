/**
 * harness.ts - Top-level orchestrator for the TypeScript eval harness.
 *
 * EvalHarness wires together Runner, Scorer, Reporter and optionally
 * the RegressionTracker.
 *
 * Quick start:
 *
 *   import { EvalHarness, TestCase } from "evalforge";
 *   import { exactMatch } from "evalforge/scorer";
 *
 *   const harness = new EvalHarness({
 *     agent: async (input) => "Hello!",
 *     suiteName: "smoke",
 *   });
 *
 *   harness.add(new TestCase({
 *     id: "greet",
 *     input: "Say hello",
 *     expectedOutput: "Hello!",
 *     scoring: exactMatch(),
 *   }));
 *
 *   const result = await harness.run();
 */

import { RegressionTracker, printReport, saveHTML, saveJSON } from "./reporter.js";
import { Runner, AgentFn } from "./runner.js";
import { Scorer } from "./scorer.js";
import { SuiteResult, TestCase } from "./testCase.js";

export interface EvalHarnessOptions {
  /** The agent to evaluate. */
  agent: AgentFn;
  /** Suite display name. */
  suiteName?: string;
  /** Per-test timeout in ms. */
  defaultTimeoutMs?: number;
  /** Retries on error. */
  defaultRetries?: number;
  /** Parallel test concurrency. */
  concurrency?: number;
  /** Custom scorer. */
  scorer?: Scorer;
  /** Path for regression history JSONL file. */
  historyPath?: string;
  /** Print report to console. */
  verbose?: boolean;
  /** Callback after each result. */
  onResult?: (result: import("./testCase.js").TestResult) => void;
}

export interface RunOptions {
  /** If set, only run test cases with these tags. */
  tags?: string[];
  /** Extra metadata attached to the SuiteResult. */
  metadata?: Record<string, unknown>;
  /** Save JSON report to this path. */
  reportJson?: string;
  /** Save HTML report to this path. */
  reportHtml?: string;
}

export class EvalHarness {
  readonly testCases: TestCase[] = [];
  private runner: Runner;
  private tracker?: RegressionTracker;
  private verbose: boolean;

  constructor(opts: EvalHarnessOptions) {
    this.verbose = opts.verbose ?? true;

    this.runner = new Runner({
      agent: opts.agent,
      suiteName: opts.suiteName,
      defaultTimeoutMs: opts.defaultTimeoutMs,
      defaultRetries: opts.defaultRetries,
      concurrency: opts.concurrency,
      scorer: opts.scorer,
      onResult: opts.onResult,
    });

    if (opts.historyPath) {
      this.tracker = new RegressionTracker(opts.historyPath);
    }
  }

  // ------------------------------------------------------------------
  // Building the suite
  // ------------------------------------------------------------------

  add(tc: TestCase): this {
    this.testCases.push(tc);
    return this;
  }

  addMany(tcs: TestCase[]): this {
    this.testCases.push(...tcs);
    return this;
  }

  filter(tags: string[]): TestCase[] {
    return this.testCases.filter((tc) =>
      tags.some((t) => tc.tags.includes(t))
    );
  }

  // ------------------------------------------------------------------
  // Running
  // ------------------------------------------------------------------

  async run(opts: RunOptions = {}): Promise<SuiteResult> {
    const cases = opts.tags ? this.filter(opts.tags) : this.testCases;
    if (cases.length === 0) {
      console.warn("[evalforge] No test cases to run.");
    }

    const result = await this.runner.run(cases, opts.metadata);
    this.postRun(result, opts);
    return result;
  }

  // ------------------------------------------------------------------
  // Internal
  // ------------------------------------------------------------------

  private postRun(result: SuiteResult, opts: RunOptions): void {
    if (this.verbose) {
      printReport(result);
    }

    if (opts.reportJson) {
      saveJSON(result, opts.reportJson);
    }

    if (opts.reportHtml) {
      saveHTML(result, opts.reportHtml);
    }

    if (this.tracker) {
      const regressions = this.tracker.compareAndSave(result);
      if (regressions.length > 0) {
        console.warn(
          `\n⚠  Regressions detected: ${regressions.join(", ")}`
        );
      }
    }
  }
}
