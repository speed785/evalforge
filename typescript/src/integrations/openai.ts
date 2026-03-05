/**
 * OpenAI integration — pre-built agent and LLM judge for OpenAI models.
 *
 * Usage:
 *   import { OpenAIAgent, openaiJudgeFn } from "evalforge/integrations/openai";
 *   import { EvalHarness, TestCase } from "evalforge";
 *   import { llmJudge } from "evalforge/scorer";
 *   import { Scorer } from "evalforge/scorer";
 *
 *   const agent = new OpenAIAgent({ model: "gpt-4o" });
 *   const scorer = new Scorer(openaiJudgeFn({ model: "gpt-4o-mini" }));
 *
 *   const harness = new EvalHarness({ agent, scorer, suiteName: "my-suite" });
 *   harness.add(new TestCase({ ... }));
 *   await harness.run();
 */

import type { LLMJudgeFn } from "../scorer.js";

export interface OpenAIAgentOptions {
  model?: string;
  apiKey?: string;
  systemPrompt?: string;
  temperature?: number;
  maxTokens?: number;
  [key: string]: unknown;
}

type MessageRole = "user" | "assistant" | "system";
interface ChatMessage { role: MessageRole; content: string; }

/**
 * A callable agent backed by an OpenAI chat completion model.
 * Requires the `openai` npm package: `npm install openai`
 */
export class OpenAIAgent {
  private opts: Required<Omit<OpenAIAgentOptions, "systemPrompt">> & { systemPrompt?: string };

  constructor(opts: OpenAIAgentOptions = {}) {
    this.opts = {
      model: opts.model ?? "gpt-4o-mini",
      apiKey: opts.apiKey ?? process.env.OPENAI_API_KEY ?? "",
      systemPrompt: opts.systemPrompt,
      temperature: (opts.temperature as number) ?? 0,
      maxTokens: (opts.maxTokens as number) ?? 1024,
    };
  }

  async __call__(input: unknown): Promise<string> {
    return this.call(input);
  }

  async call(input: unknown): Promise<string> {
    // Dynamic import so the package is optional
    const { default: OpenAI } = await import("openai").catch(() => {
      throw new Error('openai package required. Install with: npm install openai');
    });

    const client = new OpenAI({ apiKey: this.opts.apiKey });
    const messages = this.buildMessages(input);

    const response = await client.chat.completions.create({
      model: this.opts.model,
      messages,
      temperature: this.opts.temperature,
      max_tokens: this.opts.maxTokens,
    });

    return response.choices[0]?.message?.content ?? "";
  }

  private buildMessages(input: unknown): ChatMessage[] {
    const messages: ChatMessage[] = [];

    if (this.opts.systemPrompt) {
      messages.push({ role: "system", content: this.opts.systemPrompt });
    }

    if (typeof input === "string") {
      messages.push({ role: "user", content: input });
    } else if (
      input !== null &&
      typeof input === "object" &&
      "messages" in input &&
      Array.isArray((input as { messages: unknown[] }).messages)
    ) {
      messages.push(...(input as { messages: ChatMessage[] }).messages);
    } else if (Array.isArray(input)) {
      messages.push(...(input as ChatMessage[]));
    } else {
      messages.push({ role: "user", content: String(input) });
    }

    return messages;
  }
}

/**
 * Returns an async LLM judge function backed by an OpenAI model.
 *
 * Usage:
 *   import { Scorer } from "evalforge/scorer";
 *   const scorer = new Scorer(openaiJudgeFn({ model: "gpt-4o-mini" }));
 */
export function openaiJudgeFn(opts: OpenAIAgentOptions = {}): LLMJudgeFn {
  const model = opts.model ?? "gpt-4o-mini";
  const apiKey = opts.apiKey ?? process.env.OPENAI_API_KEY ?? "";

  return async (prompt: string): Promise<number> => {
    const { default: OpenAI } = await import("openai").catch(() => {
      throw new Error('openai package required. Install with: npm install openai');
    });

    const client = new OpenAI({ apiKey });
    const response = await client.chat.completions.create({
      model,
      messages: [
        {
          role: "system",
          content:
            "You are an impartial evaluator. Respond with ONLY a decimal number between 0.0 and 1.0.",
        },
        { role: "user", content: prompt },
      ],
      temperature: 0,
      max_tokens: 10,
    });

    const raw = response.choices[0]?.message?.content?.trim() ?? "0";
    const score = parseFloat(raw);
    return isNaN(score) ? 0 : Math.max(0, Math.min(1, score));
  };
}
