/**
 * Example 1: Basic eval suite (TypeScript) — no external APIs required.
 *
 * Run:
 *   cd typescript
 *   npm install
 *   npx ts-node --esm examples/example_basic.ts
 */

import { EvalHarness, TestCase } from "../dist/index.js";
import {
  exactMatch,
  fuzzyMatch,
  containsMatch,
  jsonMatch,
  customScorer,
} from "../dist/scorer.js";

// ---------------------------------------------------------------------------
// Mock agent
// ---------------------------------------------------------------------------

const RESPONSES: Record<string, string> = {
  "What is 2 + 2?": "4",
  "What is the capital of France?": "The capital of France is Paris.",
  "Tell me a joke": "Why did the chicken cross the road? To get to the other side!",
  "Say hello": "Hello! How can I help you today?",
  "Return JSON": '{"name": "Alice", "age": 30, "city": "NYC"}',
};

async function echoAgent(input: unknown): Promise<string> {
  await new Promise((r) => setTimeout(r, 5)); // simulate latency
  return RESPONSES[String(input)] ?? "I don't know.";
}

// ---------------------------------------------------------------------------
// Test suite
// ---------------------------------------------------------------------------

function makeTestSuite(): TestCase[] {
  const containsDigit = (_expected: unknown, actual: unknown): number =>
    /\d/.test(String(actual)) ? 1.0 : 0.0;

  return [
    new TestCase({
      id: "math-basic",
      description: "Simple arithmetic",
      input: "What is 2 + 2?",
      expectedOutput: "4",
      scoring: exactMatch(),
      tags: ["math", "basic"],
    }),
    new TestCase({
      id: "geography-capital",
      description: "Capital city lookup",
      input: "What is the capital of France?",
      expectedOutput: "Paris",
      scoring: containsMatch(),
      tags: ["geography"],
    }),
    new TestCase({
      id: "greeting-fuzzy",
      description: "Greeting should be warm",
      input: "Say hello",
      expectedOutput: "Hello! How can I help?",
      scoring: fuzzyMatch(0.65),
      tags: ["greeting"],
    }),
    new TestCase({
      id: "json-output",
      description: "Agent returns valid JSON with expected fields",
      input: "Return JSON",
      expectedOutput: { name: "Alice", age: 30 },
      scoring: jsonMatch(["city"], 1.0),
      tags: ["structured"],
    }),
    new TestCase({
      id: "custom-number-check",
      description: "Response must contain a number",
      input: "What is 2 + 2?",
      expectedOutput: "4",
      scoring: customScorer(containsDigit, 1.0),
      tags: ["math", "custom"],
    }),
    new TestCase({
      id: "unknown-input",
      description: "Agent gracefully handles unknown queries",
      input: "xyzzy-unknown-prompt",
      expectedOutput: "I don't know.",
      scoring: exactMatch(),
      tags: ["edge-case"],
    }),
  ];
}

// ---------------------------------------------------------------------------
// Run
// ---------------------------------------------------------------------------

async function main() {
  const harness = new EvalHarness({
    agent: echoAgent,
    suiteName: "basic-echo-suite",
    defaultTimeoutMs: 5_000,
    verbose: true,
  });

  harness.addMany(makeTestSuite());

  const result = await harness.run({
    reportJson: "reports/basic_report.json",
    reportHtml: "reports/basic_report.html",
  });

  console.log(
    `Programmatic: pass_rate=${(result.results.filter((r) => r.passed).length / result.results.length * 100).toFixed(1)}%`
  );

  process.exit(result.results.every((r) => r.passed) ? 0 : 1);
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
