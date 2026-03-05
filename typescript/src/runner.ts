/**
 * runner.ts - Executes agents against test cases with timeouts,
 * retries, concurrency control, and progress callbacks.
 */

import { randomUUID } from "crypto";
import { Scorer } from "./scorer.js";
import {
  SuiteResult,
  TestCase,
  TestResult,
} from "./testCase.js";

export type AgentFn = (input: unknown) => unknown | Promise<unknown>;

export interface RunnerOptions {
  /** The agent to evaluate. */
  agent: AgentFn;
  /** Display name for the suite. */
  suiteName?: string;
  /** Per-test timeout in milliseconds. */
  defaultTimeoutMs?: number;
  /** Default number of retries on error. */
  defaultRetries?: number;
  /** Max parallel test cases. */
  concurrency?: number;
  /** Scorer instance. */
  scorer?: Scorer;
  /** Callback after each result. */
  onResult?: (result: TestResult) => void;
}

export class Runner {
  private agent: AgentFn;
  private suiteName: string;
  private defaultTimeoutMs: number;
  private defaultRetries: number;
  private concurrency: number;
  private scorer: Scorer;
  private onResult?: (result: TestResult) => void;

  constructor(opts: RunnerOptions) {
    this.agent = opts.agent;
    this.suiteName = opts.suiteName ?? "eval";
    this.defaultTimeoutMs = opts.defaultTimeoutMs ?? 30_000;
    this.defaultRetries = opts.defaultRetries ?? 0;
    this.concurrency = opts.concurrency ?? 1;
    this.scorer = opts.scorer ?? new Scorer();
    this.onResult = opts.onResult;
  }

  async run(
    testCases: TestCase[],
    metadata: Record<string, unknown> = {}
  ): Promise<SuiteResult> {
    const suite: SuiteResult = {
      suiteName: this.suiteName,
      runId: randomUUID().slice(0, 12),
      startedAt: Date.now(),
      results: [],
      metadata,
    };

    // Process with concurrency control
    const results = await this.runWithConcurrency(testCases);
    suite.results = results;
    suite.finishedAt = Date.now();
    return suite;
  }

  private async runWithConcurrency(testCases: TestCase[]): Promise<TestResult[]> {
    const results: TestResult[] = new Array(testCases.length);
    let index = 0;

    const workers = Array.from({ length: this.concurrency }, async () => {
      while (true) {
        const i = index++;
        if (i >= testCases.length) break;
        results[i] = await this.runTestCase(testCases[i]);
      }
    });

    await Promise.all(workers);
    return results;
  }

  private async runTestCase(tc: TestCase): Promise<TestResult> {
    const timeoutMs = tc.timeoutMs ?? this.defaultTimeoutMs;
    const maxRetries = tc.maxRetries ?? this.defaultRetries;
    let retries = 0;
    let lastError: string | undefined;
    let actualOutput: unknown;
    let latencyMs: number | undefined;

    // Setup hook
    if (tc.setup) {
      try {
        await Promise.resolve(tc.setup());
      } catch (err) {
        console.warn(`[evalforge] setup failed for ${tc.id}:`, err);
      }
    }

    while (retries <= maxRetries) {
      try {
        const start = performance.now();
        actualOutput = await withTimeout(
          Promise.resolve(this.agent(tc.input)),
          timeoutMs
        );
        latencyMs = performance.now() - start;
        lastError = undefined;
        break;
      } catch (err: unknown) {
        lastError = err instanceof Error ? `${err.constructor.name}: ${err.message}` : String(err);
        retries++;
      }
    }

    // Teardown hook
    if (tc.teardown) {
      try {
        await Promise.resolve(tc.teardown(actualOutput));
      } catch (err) {
        console.warn(`[evalforge] teardown failed for ${tc.id}:`, err);
      }
    }

    let result: TestResult;
    if (lastError) {
      result = {
        testCaseId: tc.id,
        passed: false,
        score: 0,
        actualOutput,
        error: lastError,
        latencyMs,
        retries: retries - 1,
        timestamp: Date.now(),
        metadata: {},
      };
    } else {
      const score = await this.scoreResult(tc, actualOutput);
      const threshold = tc.scoring.threshold ?? 1.0;
      result = {
        testCaseId: tc.id,
        passed: score >= threshold,
        score,
        actualOutput,
        latencyMs,
        retries,
        timestamp: Date.now(),
        metadata: {},
      };
    }

    this.onResult?.(result);
    return result;
  }

  private async scoreResult(tc: TestCase, actual: unknown): Promise<number> {
    try {
      return await this.scorer.score(tc.scoring, tc.expectedOutput, actual);
    } catch (err) {
      console.error(`[evalforge] scoring failed for ${tc.id}:`, err);
      return 0;
    }
  }
}

function withTimeout<T>(promise: Promise<T>, ms: number): Promise<T> {
  return new Promise<T>((resolve, reject) => {
    const timer = setTimeout(
      () => reject(new Error(`Timed out after ${ms}ms`)),
      ms
    );
    promise.then(
      (v) => { clearTimeout(timer); resolve(v); },
      (e) => { clearTimeout(timer); reject(e); }
    );
  });
}
