import { ApprovalRequired, PermissionDenied, KynaraUnavailable } from "./errors.js";
import type { CheckRequest, ClientOptions, Decision } from "./types.js";

interface CacheEntry { decision: Decision; expiresAt: number }

class DecisionCache {
  private map = new Map<string, CacheEntry>();
  constructor(private max: number) {}

  key(req: CheckRequest): string {
    return JSON.stringify({
      s: req.subject, a: req.action,
      rt: req.resource.type, rid: req.resource.id ?? null,
      ra: req.resource.attrs ?? null, c: req.context ?? null,
    });
  }
  get(req: CheckRequest): Decision | null {
    const k = this.key(req);
    const e = this.map.get(k);
    if (!e) return null;
    if (e.expiresAt < Date.now()) { this.map.delete(k); return null; }
    return e.decision;
  }
  put(req: CheckRequest, d: Decision): void {
    if (d.effect !== "allow") return;        // never cache deny / require_approval
    if (this.map.size >= this.max) {
      const first = this.map.keys().next().value;
      if (first) this.map.delete(first);
    }
    this.map.set(this.key(req), {
      decision: d,
      expiresAt: Date.now() + (d.ttl_seconds || 5) * 1000,
    });
  }
  clear(): void { this.map.clear(); }
}

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

export class Kynara {
  private readonly baseUrl: string;
  private readonly apiKey: string;
  private readonly agentId?: string;
  private readonly failClosed: boolean;
  private readonly timeoutMs: number;
  private readonly cache: DecisionCache;
  private readonly onDecision?: ClientOptions["onDecision"];

  constructor(opts: ClientOptions = {}) {
    this.baseUrl = (opts.baseUrl ?? process.env.KYNARA_BASE_URL ?? "https://kynara.example.com").replace(/\/$/, "");
    this.apiKey = opts.apiKey ?? process.env.KYNARA_API_KEY ?? "";
    this.agentId = opts.agentId ?? process.env.KYNARA_AGENT_ID;
    this.failClosed = opts.failClosed ?? (process.env.KYNARA_FAIL_CLOSED ?? "true") !== "false";
    this.timeoutMs = opts.timeoutMs ?? 5000;
    this.cache = new DecisionCache(opts.cacheMaxEntries ?? 1000);
    this.onDecision = opts.onDecision;

    if (!this.apiKey) {
      throw new Error("Kynara: missing apiKey (or KYNARA_API_KEY env var)");
    }
  }

  static fromEnv(): Kynara {
    return new Kynara();
  }

  /** Check a request. Returns the {@link Decision}. Does NOT throw on deny — see {@link enforce}. */
  async check(req: CheckRequest): Promise<Decision> {
    const cached = this.cache.get(req);
    if (cached) return cached;

    const body = {
      subject_type: req.subject.type,
      subject_id: req.subject.id,
      action: req.action,
      resource: req.resource,
      context: req.context ?? {},
    };

    let lastErr: unknown;
    for (let attempt = 0; attempt < 3; attempt++) {
      try {
        const ctrl = new AbortController();
        const timer = setTimeout(() => ctrl.abort(), this.timeoutMs);
        let res: Response;
        try {
          res = await fetch(`${this.baseUrl}/api/v1/decisions/check`, {
            method: "POST",
            headers: {
              "Content-Type": "application/json",
              "X-Kynara-Key": this.apiKey,
              "User-Agent": "kynara-sdk-ts/1.0",
            },
            body: JSON.stringify(body),
            signal: ctrl.signal,
          });
        } finally {
          clearTimeout(timer);
        }

        if (res.status === 429 || res.status >= 500) {
          await sleep(100 * (attempt + 1) ** 2);
          continue;
        }
        if (!res.ok) {
          const err = await res.text();
          throw new KynaraUnavailable(`HTTP ${res.status}: ${err.slice(0, 200)}`);
        }
        const decision = (await res.json()) as Decision;
        this.cache.put(req, decision);
        this.onDecision?.(req, decision);
        return decision;
      } catch (e) {
        lastErr = e;
        if (attempt === 2) break;
        await sleep(100 * (attempt + 1) ** 2);
      }
    }

    if (this.failClosed) {
      const denied: Decision = {
        effect: "deny",
        matched_policy_id: null,
        reason: "fail-closed: kynara unreachable",
        decision_id: "local-fail-closed",
        ttl_seconds: 0,
      };
      this.onDecision?.(req, denied);
      return denied;
    }
    throw new KynaraUnavailable("network error after retries", lastErr);
  }

  /** Throw on deny / require_approval. Use this from a tool boundary. */
  async enforce(req: CheckRequest): Promise<Decision> {
    const d = await this.check(req);
    if (d.effect === "deny") throw new PermissionDenied(d);
    if (d.effect === "require_approval") throw new ApprovalRequired(d);
    return d;
  }

  /** Returns true if allowed, false otherwise. Never throws. */
  async allowed(req: CheckRequest): Promise<boolean> {
    return (await this.check(req)).effect === "allow";
  }

  /** Build a partial CheckRequest using the SDK's default agent. */
  agentCheck(action: string, resource: import("./types.js").Resource,
             context?: Record<string, unknown>): CheckRequest {
    if (!this.agentId) throw new Error("Kynara: agentId not configured");
    return { subject: { type: "agent", id: this.agentId }, action, resource, context: context ?? {} };
  }

  invalidateCache(): void { this.cache.clear(); }
}
