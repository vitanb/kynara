/** Core types for the Kynara TypeScript SDK. */

export type DecisionEffect = "allow" | "deny" | "require_approval";

export interface Resource {
  type: string;
  id?: string;
  attrs?: Record<string, unknown>;
}

export interface Subject {
  type: "agent" | "user" | "api_key";
  id: string;
}

export interface CheckRequest {
  subject: Subject;
  action: string;
  resource: Resource;
  context?: Record<string, unknown>;
  /** Override TTL of the local cache for this allow decision. */
  ttlSecondsHint?: number;
}

export interface Decision {
  effect: DecisionEffect;
  matched_policy_id: string | null;
  reason: string;
  obligations?: Array<Record<string, unknown>>;
  approval_url?: string | null;
  decision_id: string;
  ttl_seconds: number;
}

export interface ClientOptions {
  baseUrl?: string;
  apiKey?: string;
  agentId?: string;
  failClosed?: boolean;
  timeoutMs?: number;
  cacheMaxEntries?: number;
  /** Hook called for every decision; useful for telemetry. */
  onDecision?: (req: CheckRequest, decision: Decision) => void;
}
