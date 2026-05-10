/** LangChain.js callback handler — checks Kynara on every tool start. */
import type { Kynara } from "./client.js";

export class KynaraCallbackHandler {
  name = "KynaraCallbackHandler";

  constructor(private client: Kynara, private agentId: string) {}

  async handleToolStart(tool: { name?: string }, input: string | Record<string, unknown>) {
    const action = tool.name ?? "tool.unknown";
    const resource = {
      type: "tool.invocation",
      id: action,
      attrs: { input: typeof input === "string" ? { raw: input } : input },
    };
    await this.client.enforce({
      subject: { type: "agent", id: this.agentId },
      action,
      resource,
      context: { framework: "langchain.js" },
    });
  }
}
