/** Higher-order tool guard: equivalent of the Python `@permission_required`.
 *
 * Wrap a function and Kynara will check the request *before* invoking it.
 * On deny / require_approval, the wrapper throws.
 *
 * Example:
 *
 *     const issueRefund = guarded({
 *       client,
 *       action: "payments.refund.issue",
 *       resource: (refundId, amountCents) => ({
 *         type: "payment.refund",
 *         id: refundId,
 *         attrs: { amount_cents: amountCents, currency: "USD" },
 *       }),
 *       context: () => ({ ip_country: "US" }),
 *     }, async (refundId: string, amountCents: number) => {
 *       return await processRefund(refundId, amountCents);
 *     });
 */
import type { Kynara } from "./client.js";
import type { CheckRequest, Resource } from "./types.js";

export interface GuardOptions<Args extends unknown[]> {
  client: Kynara;
  action: string;
  resource: Resource | ((...args: Args) => Resource);
  context?: Record<string, unknown> | ((...args: Args) => Record<string, unknown>);
}

export function guarded<Args extends unknown[], R>(
  opts: GuardOptions<Args>,
  fn: (...args: Args) => Promise<R>,
): (...args: Args) => Promise<R> {
  const { client, action } = opts;
  return async (...args: Args) => {
    const resource = typeof opts.resource === "function" ? opts.resource(...args) : opts.resource;
    const context = typeof opts.context === "function" ? opts.context(...args) : opts.context ?? {};
    const subject = (client as unknown as { agentCheck: typeof client.agentCheck })
      .agentCheck(action, resource, context);
    const req: CheckRequest = subject;
    await client.enforce(req);
    return fn(...args);
  };
}
