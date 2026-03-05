/**
 * Example 2: Regression tracking across runs (TypeScript).
 *
 * Run:
 *   cd typescript
 *   npm install
 *   npx ts-node --esm examples/example_regression.ts
 */

import { EvalHarness, TestCase, registry, suiteStats } from "../dist/index.js";
import { RegressionTracker } from "../dist/reporter.js";
import { fuzzyMatch, containsMatch } from "../dist/scorer.js";
import { mkdirSync } from "fs";

// ---------------------------------------------------------------------------
// Register test suite
// ---------------------------------------------------------------------------

registry.registerSuite("customer-support", () => [
  new TestCase({
    id: "refund-policy",
    description: "Agent knows refund policy",
    input: "What is your refund policy?",
    expectedOutput: "30-day",
    scoring: containsMatch(),
    tags: ["policy"],
  }),
  new TestCase({
    id: "shipping-time",
    description: "Agent knows shipping times",
    input: "How long does shipping take?",
    expectedOutput: "3-5 business days",
    scoring: containsMatch(),
    tags: ["shipping"],
  }),
  new TestCase({
    id: "contact-support",
    description: "Agent can direct to support",
    input: "How do I contact support?",
    expectedOutput: "support@example.com",
    scoring: containsMatch(),
    tags: ["contact"],
  }),
  new TestCase({
    id: "greeting",
    description: "Agent greets politely",
    input: "Hello!",
    expectedOutput: "Hello! How can I help you today?",
    scoring: fuzzyMatch(0.6),
    tags: ["greeting"],
  }),
]);

// ---------------------------------------------------------------------------
// Two "versions" of the agent
// ---------------------------------------------------------------------------

const RESPONSES_V1: Record<string, string> = {
  "What is your refund policy?": "We offer a 30-day money back guarantee.",
  "How long does shipping take?": "Standard shipping takes 3-5 business days.",
  "How do I contact support?": "Email us at support@example.com",
  "Hello!": "Hello! How can I help you today?",
};

const RESPONSES_V2: Record<string, string> = {
  "What is your refund policy?": "Please check our website.", // regression!
  "How long does shipping take?": "Shipping takes 3-5 business days.",
  "How do I contact support?": "Contact support@example.com",
  "Hello!": "Hi there!",
};

registry.registerAgent("support-bot-v1", async (input: unknown) => {
  await new Promise((r) => setTimeout(r, 10));
  return RESPONSES_V1[String(input)] ?? "I don't have that information.";
});

registry.registerAgent("support-bot-v2", async (input: unknown) => {
  await new Promise((r) => setTimeout(r, 10));
  return RESPONSES_V2[String(input)] ?? "I don't have that information.";
});

// ---------------------------------------------------------------------------
// Run and compare
// ---------------------------------------------------------------------------

async function main() {
  mkdirSync("reports", { recursive: true });
  const tracker = new RegressionTracker("reports/regression_history.jsonl");

  console.log("=".repeat(60));
  console.log("  Running v1 (baseline)");
  console.log("=".repeat(60));

  const testCases = registry.getSuite("customer-support");

  const harness1 = new EvalHarness({
    agent: registry.getAgent("support-bot-v1"),
    suiteName: "customer-support",
    verbose: true,
  });
  harness1.addMany(testCases);
  const result1 = await harness1.run({ reportHtml: "reports/v1_report.html" });

  const regressions1 = tracker.compareAndSave(result1);
  console.log(`v1 regressions (vs prior): ${regressions1.length ? regressions1.join(", ") : "none (first run)"}\n`);

  console.log("=".repeat(60));
  console.log("  Running v2 (degraded agent)");
  console.log("=".repeat(60));

  const harness2 = new EvalHarness({
    agent: registry.getAgent("support-bot-v2"),
    suiteName: "customer-support",
    verbose: true,
  });
  harness2.addMany(testCases);
  const result2 = await harness2.run({ reportHtml: "reports/v2_report.html" });

  const regressions2 = tracker.compareAndSave(result2);

  if (regressions2.length) {
    console.log(`\n⚠  REGRESSIONS in v2: ${regressions2.join(", ")}`);
    console.log("   These passed in v1 but failed in v2!\n");
  } else {
    console.log("\n✓ No regressions.\n");
  }

  // Historical summary
  const history = tracker.loadHistory("customer-support");
  console.log(`History (${history.length} runs):`);
  for (const h of history) {
    const stats = suiteStats(h);
    console.log(
      `  run_id=${h.runId}  pass_rate=${(stats.passRate * 100).toFixed(1)}%  passed=${stats.passed}/${stats.total}`
    );
  }

  const passRate = result2.results.filter((r) => r.passed).length / result2.results.length;
  process.exit(passRate >= 0.75 ? 0 : 1);
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
