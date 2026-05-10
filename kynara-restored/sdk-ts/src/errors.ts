import type { Decision } from "./types.js";

export class KynaraError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "KynaraError";
  }
}

export class PermissionDenied extends KynaraError {
  readonly decision: Decision;
  constructor(decision: Decision) {
    super(`permission denied: ${decision.reason}`);
    this.name = "PermissionDenied";
    this.decision = decision;
  }
}

export class ApprovalRequired extends KynaraError {
  readonly decision: Decision;
  readonly approvalUrl: string | null;
  constructor(decision: Decision) {
    super(`approval required: ${decision.reason}`);
    this.name = "ApprovalRequired";
    this.decision = decision;
    this.approvalUrl = decision.approval_url ?? null;
  }
}

export class KynaraUnavailable extends KynaraError {
  readonly cause?: unknown;
  constructor(message: string, cause?: unknown) {
    super(`kynara unavailable: ${message}`);
    this.name = "KynaraUnavailable";
    this.cause = cause;
  }
}
