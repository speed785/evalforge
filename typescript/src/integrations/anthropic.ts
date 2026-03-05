/**
 * Anthropic integration — pre-built agent and LLM judge for Claude models.
 *
 * Usage:
 *   import { AnthropicAgent, anthropicJudgeFn } from "evalforge/integrations/anthropic";
 *   import { EvalHarness, TestCase } from "evalforge";
 *   import { Scorer } from "evalforge/scorer";
 *
 *   const agent = new AnthropicAgent({ model: "claude-3-5-haiku-20241022" });
 *   const scorer = new Scorer(anthropicJudgeFn());
 *
 *   const harness = new EvalHarness({ agent: (i) => agent.call(i), scorer, suiteName: "suite" });
 */

import type { LLMJudgeFn } from "../scorer.js";

export interface AnthropicAgentOptions {
  model?: string;
  apiKey?: string;
  systemPrompt?: string;
  maxTokens?: number;
  temperature?: number;
}

type MessageRole = "user" | "assistant";
interface ChatMessage { role: MessageRole; content: string; }

/**
 * A callable agent backed by a Claude model via the Anthropic API.
 * Requires the `@anthropic-ai/sdk` npm package.
 */
export class AnthropicAgent {
  private opts: Required<Omit<AnthropicAgentOptions, "systemPrompt">> & {
    systemPrompt?: string;
  };

  constructor(opts: AnthropicAgentOptions = {}) {
    this.opts = {
      model: opts.model ?? "claude-3-5-haiku-20241022",
      apiKey: opts.apiKey ?? process.env.ANTHROPIC_API_KEY ?? "",
      systemPrompt: opts.systemPrompt,
      maxTokens: opts.maxTokens ?? 1024,
      temperature: opts.temperature ?? 0,
    };
  }

  async call(input: unknown): Promise<string> {
    const { default: Anthropic } = await import("@anthropic-ai/sdk").catch(() => {
      throw new Error(
        "@anthropic-ai/sdk package required. Install with: npm install @anthropic-ai/sdk"
      );
    });

    const client = new Anthropic({ apiKey: this.opts.apiKey });
    const messages = this.buildMessages(input);

    const params: Parameters<typeof client.messages.create>[0] = {
      model: this.opts.model,
      messages,
      max_tokens: this.opts.maxTokens,
    };
    if (this.opts.systemPrompt) {
      params.system = this.opts.systemPrompt;
    }

    const response = await client.messages.create(params);

    for (const block of response.content) {
      if (block.type === "text") return block.text;
    }
    return "";
  }

  private buildMessages(input: unknown): ChatMessage[] {
    if (typeof input === "string") {
      return [{ role: "user", content: input }];
    }
    if (
      input !== null &&
      typeof input === "object" &&
      "messages" in input &&
      Array.isArray((input as { messages: unknown[] }).messages)
    ) {
      return (input as { messages: ChatMessage[] }).messages;
    }
    if (Array.isArray(input)) {
      return input as ChatMessage[];
    }
    return [{ role: "user", content: String(input) }];
  }
}

/**
 * Returns an async LLM judge function backed by a Claude model.
 *
 * Usage:
 *   import { Scorer } from "evalforge/scorer";
 *   const scorer = new Scorer(anthropicJudgeFn());
 */
export function anthropicJudgeFn(opts: AnthropicAgentOptions = {}): LLMJudgeFn {
  const model = opts.model ?? "claude-3-5-haiku-20241022";
  const apiKey = opts.apiKey ?? process.env.ANTHROPIC_API_KEY ?? "";

  return async (prompt: string): Promise<number> => {
    const { default: Anthropic } = await import("@anthropic-ai/sdk").catch(() => {
      throw new Error(
        "@anthropic-ai/sdk package required. Install with: npm install @anthropic-ai/sdk"
      );
    });

    const client = new Anthropic({ apiKey });
    const response = await client.messages.create({
      model,
      max_tokens: 10,
      system:
        "You are an impartial evaluator. Respond with ONLY a decimal number between 0.0 and 1.0.",
      messages: [{ role: "user", content: prompt }],
    });

    let raw = "";
    for (const block of response.content) {
      if (block.type === "text") { raw = block.text.trim(); break; }
    }

    const score = parseFloat(raw);
    return isNaN(score) ? 0 : Math.max(0, Math.min(1, score));
  };
}
