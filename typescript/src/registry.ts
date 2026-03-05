/**
 * registry.ts - Central store for reusable test suites and named agents.
 *
 * Usage:
 *   import { registry } from "evalforge";
 *
 *   registry.registerSuite("math", () => [...]);
 *   registry.registerAgent("gpt-4o", async (input) => { ... });
 *
 *   const result = await registry.run("math", "gpt-4o");
 */

import { Runner, AgentFn, RunnerOptions } from "./runner.js";
import { SuiteResult, TestCase } from "./testCase.js";

type SuiteFactory = () => TestCase[];

export class Registry {
  private suites = new Map<string, SuiteFactory>();
  private agents = new Map<string, AgentFn>();

  // ------------------------------------------------------------------
  // Suites
  // ------------------------------------------------------------------

  registerSuite(name: string, factory: SuiteFactory): this {
    this.suites.set(name, factory);
    return this;
  }

  getSuite(name: string): TestCase[] {
    const factory = this.suites.get(name);
    if (!factory) {
      throw new Error(
        `Suite "${name}" not found. Available: ${[...this.suites.keys()].join(", ")}`
      );
    }
    return factory();
  }

  listSuites(): string[] {
    return [...this.suites.keys()];
  }

  // ------------------------------------------------------------------
  // Agents
  // ------------------------------------------------------------------

  registerAgent(name: string, fn: AgentFn): this {
    this.agents.set(name, fn);
    return this;
  }

  getAgent(name: string): AgentFn {
    const fn = this.agents.get(name);
    if (!fn) {
      throw new Error(
        `Agent "${name}" not found. Available: ${[...this.agents.keys()].join(", ")}`
      );
    }
    return fn;
  }

  listAgents(): string[] {
    return [...this.agents.keys()];
  }

  // ------------------------------------------------------------------
  // Convenience: run named suite against named agent
  // ------------------------------------------------------------------

  async run(
    suiteName: string,
    agentName: string,
    runnerOpts: Omit<RunnerOptions, "agent" | "suiteName"> = {}
  ): Promise<SuiteResult> {
    const testCases = this.getSuite(suiteName);
    const agent = this.getAgent(agentName);
    const runner = new Runner({ agent, suiteName, ...runnerOpts });
    return runner.run(testCases);
  }
}

/** Module-level singleton. */
export const registry = new Registry();
