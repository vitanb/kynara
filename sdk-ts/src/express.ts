/** Express middleware: enforce a Kynara check on a route. */
import type { Kynara } from "./client.js";
import { ApprovalRequired, PermissionDenied } from "./errors.js";
import type { Resource } from "./types.js";

export interface RequireOptions {
  client: Kynara;
  action: string;
  resource: (req: any) => Resource;
  context?: (req: any) => Record<string, unknown>;
}

export function requirePermission(opts: RequireOptions) {
  return async function (req: any, res: any, next: any) {
    try {
      const subject = (opts.client as any).agentCheck(
        opts.action,
        opts.resource(req),
        opts.context ? opts.context(req) : {},
      );
      await opts.client.enforce(subject);
      next();
    } catch (e) {
      if (e instanceof PermissionDenied) {
        res.status(403).json({ error: "permission_denied", reason: e.decision.reason });
        return;
      }
      if (e instanceof ApprovalRequired) {
        res.status(202).json({
          error: "approval_required",
          approval_url: e.approvalUrl,
          decision_id: e.decision.decision_id,
        });
        return;
      }
      next(e);
    }
  };
}
