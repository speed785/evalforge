/**
 * scorer.ts - Multiple scoring strategies for evaluating agent outputs.
 */

import { ScoringCriteria } from "./testCase.js";
import { createHash } from "crypto";

export type LLMJudgeFn = (
  prompt: string,
  expected: unknown,
  actual: unknown
) => Promise<number>;

// ---------------------------------------------------------------------------
// Main Scorer
// ---------------------------------------------------------------------------

export class Scorer {
  private embeddingCache = new Map<string, number[]>();

  constructor(private llmJudgeFn?: LLMJudgeFn) {}

  async score(
    criteria: ScoringCriteria,
    expected: unknown,
    actual: unknown
  ): Promise<number> {
    switch (criteria.strategy) {
      case "exact":
        return exactScore(expected, actual);
      case "fuzzy":
        return fuzzyScore(expected, actual);
      case "contains":
        return containsScore(expected, actual);
      case "json_match":
        return jsonMatchScore(expected, actual, criteria.jsonIgnoreKeys ?? []);
      case "llm_judge":
        return this.llmJudge(criteria, expected, actual);
      case "semantic":
        return this.semanticScore(criteria, expected, actual);
      case "custom":
        if (!criteria.scorerFn) {
          throw new Error(
            "ScoringCriteria.scorerFn must be set for 'custom' strategy"
          );
        }
        return Promise.resolve(criteria.scorerFn(expected, actual));
      default:
        throw new Error(`Unknown scoring strategy: ${(criteria as ScoringCriteria).strategy}`);
    }
  }

  private async llmJudge(
    criteria: ScoringCriteria,
    expected: unknown,
    actual: unknown
  ): Promise<number> {
    if (!this.llmJudgeFn) {
      throw new Error(
        "llm_judge strategy requires a llmJudgeFn passed to Scorer(). " +
          "Use new Scorer(myJudgeFn) or use an integration."
      );
    }
    const prompt =
      criteria.llmJudgePrompt ?? defaultJudgePrompt(expected, actual);
    return this.llmJudgeFn(prompt, expected, actual);
  }

  private async semanticScore(
    criteria: ScoringCriteria,
    expected: unknown,
    actual: unknown
  ): Promise<number> {
    const model = criteria.semanticModel ?? "text-embedding-3-small";
    const expectedText = String(expected);
    const actualText = String(actual);

    let OpenAI: new (opts?: { apiKey?: string }) => {
      embeddings: { create: (args: { model: string; input: string }) => Promise<{ data: Array<{ embedding: number[] }> }> };
    };
    try {
      ({ default: OpenAI } = await import("openai"));
    } catch {
      console.warn("openai not installed, semantic scoring skipped. Install with: npm install openai");
      return 0;
    }

    const client = new OpenAI({ apiKey: process.env.OPENAI_API_KEY });
    const expectedEmbedding = await this.getEmbedding(client, expectedText, model);
    const actualEmbedding = await this.getEmbedding(client, actualText, model);
    return cosineSimilarity(expectedEmbedding, actualEmbedding);
  }

  private async getEmbedding(
    client: { embeddings: { create: (args: { model: string; input: string }) => Promise<{ data: Array<{ embedding: number[] }> }> } },
    text: string,
    model: string
  ): Promise<number[]> {
    const key = createHash("sha256").update(`${model}:${text}`).digest("hex");
    const cached = this.embeddingCache.get(key);
    if (cached) {
      return cached;
    }

    const response = await client.embeddings.create({ model, input: text });
    const embedding = response.data[0]?.embedding ?? [];
    this.embeddingCache.set(key, embedding);
    return embedding;
  }
}

// ---------------------------------------------------------------------------
// Strategy implementations
// ---------------------------------------------------------------------------

function exactScore(expected: unknown, actual: unknown): number {
  if (typeof expected === "string" && typeof actual === "string") {
    return expected.trim() === actual.trim() ? 1.0 : 0.0;
  }
  return JSON.stringify(expected) === JSON.stringify(actual) ? 1.0 : 0.0;
}

function fuzzyScore(expected: unknown, actual: unknown): number {
  // Simple built-in Levenshtein-based similarity
  const a = String(expected);
  const b = String(actual);
  if (a === b) return 1.0;
  const maxLen = Math.max(a.length, b.length);
  if (maxLen === 0) return 1.0;
  const dist = levenshtein(a.toLowerCase(), b.toLowerCase());
  return 1.0 - dist / maxLen;
}

function levenshtein(a: string, b: string): number {
  const m = a.length;
  const n = b.length;
  const dp: number[][] = Array.from({ length: m + 1 }, (_, i) =>
    Array.from({ length: n + 1 }, (_, j) => (i === 0 ? j : j === 0 ? i : 0))
  );
  for (let i = 1; i <= m; i++) {
    for (let j = 1; j <= n; j++) {
      dp[i][j] =
        a[i - 1] === b[j - 1]
          ? dp[i - 1][j - 1]
          : 1 + Math.min(dp[i - 1][j], dp[i][j - 1], dp[i - 1][j - 1]);
    }
  }
  return dp[m][n];
}

function containsScore(expected: unknown, actual: unknown): number {
  return String(actual).includes(String(expected).trim()) ? 1.0 : 0.0;
}

function jsonMatchScore(
  expected: unknown,
  actual: unknown,
  ignoreKeys: string[]
): number {
  const ignore = new Set(ignoreKeys);

  function flatten(obj: unknown, prefix = ""): Map<string, unknown> {
    const result = new Map<string, unknown>();
    if (obj !== null && typeof obj === "object") {
      if (Array.isArray(obj)) {
        obj.forEach((v, i) => {
          flatten(v, `${prefix}[${i}]`).forEach((val, key) =>
            result.set(key, val)
          );
        });
      } else {
        for (const [k, v] of Object.entries(obj as Record<string, unknown>)) {
          if (ignore.has(k)) continue;
          const path = prefix ? `${prefix}.${k}` : k;
          flatten(v, path).forEach((val, key) => result.set(key, val));
        }
      }
    } else {
      result.set(prefix, obj);
    }
    return result;
  }

  // Try to parse strings as JSON
  let exp = expected;
  let act = actual;
  if (typeof exp === "string") {
    try { exp = JSON.parse(exp); } catch {}
  }
  if (typeof act === "string") {
    try { act = JSON.parse(act); } catch {}
  }

  const expFlat = flatten(exp);
  const actFlat = flatten(act);

  if (expFlat.size === 0) return actFlat.size === 0 ? 1.0 : 0.0;

  let matches = 0;
  for (const [k, v] of expFlat) {
    if (JSON.stringify(actFlat.get(k)) === JSON.stringify(v)) matches++;
  }
  return matches / expFlat.size;
}

function defaultJudgePrompt(expected: unknown, actual: unknown): string {
  return (
    `You are an impartial evaluator. Score the following agent response ` +
    `on a scale of 0.0 to 1.0 where 1.0 is a perfect answer.\n\n` +
    `Expected answer:\n${expected}\n\n` +
    `Agent response:\n${actual}\n\n` +
    `Reply with ONLY a decimal number between 0.0 and 1.0.`
  );
}

function cosineSimilarity(a: number[], b: number[]): number {
  if (a.length === 0 || b.length === 0 || a.length !== b.length) {
    return 0;
  }
  let dot = 0;
  let normA = 0;
  let normB = 0;
  for (let i = 0; i < a.length; i++) {
    dot += a[i] * b[i];
    normA += a[i] * a[i];
    normB += b[i] * b[i];
  }
  if (normA === 0 || normB === 0) {
    return 0;
  }
  return dot / (Math.sqrt(normA) * Math.sqrt(normB));
}

// ---------------------------------------------------------------------------
// Convenience constructors
// ---------------------------------------------------------------------------

export const exactMatch = (): ScoringCriteria => ({
  strategy: "exact",
  threshold: 1.0,
});

export const fuzzyMatch = (threshold = 0.8): ScoringCriteria => ({
  strategy: "fuzzy",
  threshold,
});

export const containsMatch = (threshold = 1.0): ScoringCriteria => ({
  strategy: "contains",
  threshold,
});

export const jsonMatch = (
  ignoreKeys: string[] = [],
  threshold = 1.0
): ScoringCriteria => ({
  strategy: "json_match",
  threshold,
  jsonIgnoreKeys: ignoreKeys,
});

export const llmJudge = (
  prompt?: string,
  threshold = 0.7
): ScoringCriteria => ({
  strategy: "llm_judge",
  threshold,
  llmJudgePrompt: prompt,
});

export const semanticMatch = (
  threshold = 0.85,
  model = "text-embedding-3-small"
): ScoringCriteria => ({
  strategy: "semantic",
  threshold,
  semanticModel: model,
});

export const customScorer = (
  fn: (expected: unknown, actual: unknown) => number | Promise<number>,
  threshold = 0.5
): ScoringCriteria => ({
  strategy: "custom",
  threshold,
  scorerFn: fn,
});
