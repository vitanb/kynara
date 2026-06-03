import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  CheckCircle2, XCircle, Clock, AlertTriangle, ChevronRight,
  User, Bot, Calendar, RefreshCw, type LucideIcon,
} from "lucide-react";
import PageHeader from "@/components/layout/PageHeader";
import { api } from "@/lib/api";

// ─── types ────────────────────────────────────────────────────────────────────

interface ApprovalItem {
  id: string;
  subject_type: string;
  subject_id: string;
  on_behalf_of_user_id: string | null;
  action: string;
  resource_type: string | null;
  resource_id: string | null;
  resource_attrs: Record<string, unknown>;
  context: Record<string, unknown>;
  matched_policy_id: string | null;
  status: "pending" | "approved" | "rejected" | "expired";
  reviewed_by_user_id: string | null;
  reviewed_at: string | null;
  review_note: string | null;
  expires_at: string;
  created_at: string;
}

interface ApprovalListOut {
  items: ApprovalItem[];
  total: number;
  pending_count: number;
}

// ─── helpers ──────────────────────────────────────────────────────────────────

function relativeTime(iso: string): string {
  const secs = Math.floor((Date.now() - new Date(iso).getTime()) / 1000);
  if (secs < 60) return "just now";
  if (secs < 3600) return `${Math.floor(secs / 60)}m ago`;
  if (secs < 86400) return `${Math.floor(secs / 3600)}h ago`;
  return `${Math.floor(secs / 86400)}d ago`;
}

function expiresIn(iso: string): string {
  const secs = Math.floor((new Date(iso).getTime() - Date.now()) / 1000);
  if (secs <= 0) return "expired";
  if (secs < 3600) return `expires in ${Math.floor(secs / 60)}m`;
  if (secs < 86400) return `expires in ${Math.floor(secs / 3600)}h`;
  return `expires in ${Math.floor(secs / 86400)}d`;
}

const STATUS_META: Record<string, { label: string; color: string; icon: LucideIcon }> = {
  pending:  { label: "Pending",  color: "#F59E0B", icon: Clock },
  approved: { label: "Approved", color: "#10B981", icon: CheckCircle2 },
  rejected: { label: "Rejected", color: "#F43F5E", icon: XCircle },
  expired:  { label: "Expired",  color: "#64748B", icon: AlertTriangle },
};

// ─── Review modal ─────────────────────────────────────────────────────────────

function ReviewModal({
  item,
  action,
  onClose,
  onDone,
}: {
  item: ApprovalItem;
  action: "approve" | "reject";
  onClose: () => void;
  onDone: () => void;
}) {
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  async function submit() {
    setBusy(true);
    setErr(null);
    try {
      await api.post(`/api/v1/approvals/${item.id}/${action}`, { note: note || null });
      onDone();
    } catch (e: any) {
      setErr(e?.message || "Failed");
    } finally {
      setBusy(false);
    }
  }

  const isApprove = action === "approve";

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div
        className="absolute inset-0"
        style={{ background: "rgba(0,0,0,0.7)", backdropFilter: "blur(4px)" }}
        onClick={onClose}
      />
      <div
        className="relative z-10 w-full max-w-md rounded-2xl p-6 flex flex-col gap-4"
        style={{ background: "#FFFFFF", border: "1px solid rgba(148,163,184,0.12)" }}
      >
        <div className="flex items-center gap-3">
          <div
            className="size-9 rounded-lg flex items-center justify-center shrink-0"
            style={{
              background: isApprove ? "rgba(16,185,129,0.12)" : "rgba(244,63,94,0.12)",
              border: `1px solid ${isApprove ? "rgba(4,120,87,0.3)" : "rgba(190,18,60,0.3)"}`,
            }}
          >
            {isApprove
              ? <CheckCircle2 className="size-4" style={{ color: "#10B981" }} />
              : <XCircle className="size-4" style={{ color: "#F43F5E" }} />
            }
          </div>
          <div>
            <div className="text-sm font-semibold text-ink-50">
              {isApprove ? "Approve" : "Reject"} request
            </div>
            <div className="text-xs text-ink-400">{item.action}</div>
          </div>
        </div>

        {/* Summary */}
        <div
          className="rounded-lg p-3 text-xs font-mono text-ink-300 space-y-1"
          style={{ background: "rgba(148,163,184,0.05)", border: "1px solid rgba(148,163,184,0.08)" }}
        >
          <div><span className="text-ink-400">subject  </span>{item.subject_type}:{item.subject_id.slice(0, 8)}…</div>
          <div><span className="text-ink-400">action   </span>{item.action}</div>
          {item.resource_type && (
            <div><span className="text-ink-400">resource </span>{item.resource_type}{item.resource_id ? `:${item.resource_id.slice(0, 8)}…` : ""}</div>
          )}
        </div>

        <div className="flex flex-col gap-1.5">
          <label className="text-xs font-medium text-ink-400">
            Review note <span className="text-slate-600">(optional)</span>
          </label>
          <textarea
            className="w-full rounded-lg px-3 py-2 text-sm text-ink-50 resize-none"
            style={{
              background: "rgba(148,163,184,0.06)",
              border: "1px solid rgba(148,163,184,0.15)",
              outline: "none",
              minHeight: "72px",
            }}
            placeholder={isApprove ? "Why is this approved?" : "Why is this rejected?"}
            value={note}
            onChange={(e) => setNote(e.target.value)}
          />
        </div>

        {err && (
          <div className="text-xs text-rose-400 px-1">{err}</div>
        )}

        <div className="flex gap-2 justify-end">
          <button
            onClick={onClose}
            disabled={busy}
            className="btn-secondary text-sm px-4 py-2"
          >
            Cancel
          </button>
          <button
            onClick={submit}
            disabled={busy}
            className="text-sm px-4 py-2 rounded-lg font-medium transition-colors disabled:opacity-50"
            style={{
              background: isApprove ? "#10B981" : "#F43F5E",
              color: "white",
            }}
          >
            {busy ? (isApprove ? "Approving…" : "Rejecting…") : (isApprove ? "Approve" : "Reject")}
          </button>
        </div>
      </div>
    </div>
  );
}

// ─── Approval row ─────────────────────────────────────────────────────────────

function ApprovalRow({
  item,
  onReview,
}: {
  item: ApprovalItem;
  onReview: (item: ApprovalItem, action: "approve" | "reject") => void;
}) {
  const [expanded, setExpanded] = useState(false);
  const meta = STATUS_META[item.status] ?? STATUS_META.expired;
  const StatusIcon = meta.icon;
  const isPending = item.status === "pending";

  return (
    <div
      className="rounded-xl overflow-hidden transition-all"
      style={{
        background: "#FFFFFF",
        border: `1px solid ${isPending ? "rgba(245,158,11,0.2)" : "rgba(148,163,184,0.08)"}`,
      }}
    >
      {/* Main row */}
      <button
        className="w-full flex items-center gap-3 px-4 py-3.5 text-left hover:bg-white/[0.02] transition-colors"
        onClick={() => setExpanded(e => !e)}
      >
        {/* Status icon */}
        <div
          className="size-8 rounded-lg flex items-center justify-center shrink-0"
          style={{
            background: `${meta.color}18`,
            border: `1px solid ${meta.color}33`,
          }}
        >
          <StatusIcon className="size-4" style={{ color: meta.color }} />
        </div>

        {/* Action + subject */}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-sm font-medium text-ink-50">{item.action}</span>
            {item.resource_type && (
              <span className="text-xs text-ink-400">
                on {item.resource_type}
                {item.resource_id ? ` #${item.resource_id.slice(0, 8)}` : ""}
              </span>
            )}
          </div>
          <div className="flex items-center gap-3 mt-0.5 text-xs text-ink-400">
            <span className="flex items-center gap-1">
              {item.subject_type === "agent"
                ? <Bot className="size-3" />
                : <User className="size-3" />
              }
              {item.subject_type}:{item.subject_id.slice(0, 8)}…
            </span>
            <span>{relativeTime(item.created_at)}</span>
            {isPending && (
              <span style={{ color: "#F59E0B" }}>{expiresIn(item.expires_at)}</span>
            )}
            {item.review_note && (
              <span className="text-ink-400 truncate max-w-xs italic">"{item.review_note}"</span>
            )}
          </div>
        </div>

        {/* Status pill */}
        <span
          className="shrink-0 text-[10px] font-semibold px-2 py-0.5 rounded-full"
          style={{ background: `${meta.color}18`, color: meta.color }}
        >
          {meta.label}
        </span>

        <ChevronRight
          className={`size-4 text-slate-600 shrink-0 transition-transform ${expanded ? "rotate-90" : ""}`}
        />
      </button>

      {/* Expanded detail */}
      {expanded && (
        <div
          className="px-4 pb-4 pt-1 border-t"
          style={{ borderColor: "rgba(148,163,184,0.07)" }}
        >
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 mb-4">
            {/* Context card */}
            <div
              className="rounded-lg p-3 text-xs font-mono space-y-1"
              style={{ background: "rgba(148,163,184,0.04)", border: "1px solid rgba(148,163,184,0.08)" }}
            >
              <div className="text-[10px] font-sans font-semibold text-ink-400 uppercase tracking-wider mb-2">Request details</div>
              <div><span className="text-ink-400">subject  </span><span className="text-ink-300">{item.subject_type}:{item.subject_id}</span></div>
              {item.on_behalf_of_user_id && (
                <div><span className="text-ink-400">on_behalf</span><span className="text-ink-300"> {item.on_behalf_of_user_id}</span></div>
              )}
              <div><span className="text-ink-400">action   </span><span className="text-ink-300">{item.action}</span></div>
              {item.resource_type && (
                <div><span className="text-ink-400">resource </span><span className="text-ink-300">{item.resource_type}{item.resource_id ? `:${item.resource_id}` : ""}</span></div>
              )}
              {item.matched_policy_id && (
                <div><span className="text-ink-400">policy   </span><span className="text-ink-300">{item.matched_policy_id.slice(0, 16)}…</span></div>
              )}
            </div>

            {/* Review card */}
            <div
              className="rounded-lg p-3 text-xs space-y-1"
              style={{ background: "rgba(148,163,184,0.04)", border: "1px solid rgba(148,163,184,0.08)" }}
            >
              <div className="text-[10px] font-semibold text-ink-400 uppercase tracking-wider mb-2">Review</div>
              <div className="flex gap-2">
                <span className="text-ink-400">Status</span>
                <span style={{ color: meta.color }}>{meta.label}</span>
              </div>
              {item.reviewed_at && (
                <div className="flex gap-2">
                  <span className="text-ink-400">Reviewed</span>
                  <span className="text-ink-300">{new Date(item.reviewed_at).toLocaleString()}</span>
                </div>
              )}
              {item.review_note && (
                <div className="flex gap-2">
                  <span className="text-ink-400 shrink-0">Note</span>
                  <span className="text-ink-300 italic">"{item.review_note}"</span>
                </div>
              )}
              <div className="flex gap-2">
                <Calendar className="size-3 text-slate-600 mt-0.5 shrink-0" />
                <span className="text-ink-400">
                  Created {new Date(item.created_at).toLocaleString()}
                </span>
              </div>
            </div>
          </div>

          {/* Action buttons for pending */}
          {isPending && (
            <div className="flex gap-2">
              <button
                onClick={(e) => { e.stopPropagation(); onReview(item, "approve"); }}
                className="flex items-center gap-1.5 text-xs font-medium px-3 py-1.5 rounded-lg transition-colors"
                style={{ background: "rgba(16,185,129,0.15)", color: "#10B981", border: "1px solid rgba(16,185,129,0.25)" }}
              >
                <CheckCircle2 className="size-3.5" />
                Approve
              </button>
              <button
                onClick={(e) => { e.stopPropagation(); onReview(item, "reject"); }}
                className="flex items-center gap-1.5 text-xs font-medium px-3 py-1.5 rounded-lg transition-colors"
                style={{ background: "rgba(244,63,94,0.15)", color: "#F43F5E", border: "1px solid rgba(244,63,94,0.25)" }}
              >
                <XCircle className="size-3.5" />
                Reject
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ─── Main page ────────────────────────────────────────────────────────────────

type Tab = "pending" | "all";

export default function ApprovalsPage() {
  const [tab, setTab] = useState<Tab>("pending");
  const [reviewing, setReviewing] = useState<{ item: ApprovalItem; action: "approve" | "reject" } | null>(null);
  const qc = useQueryClient();

  const { data, isLoading, refetch } = useQuery<ApprovalListOut>({
    queryKey: ["approvals", tab],
    queryFn: () =>
      api.get<ApprovalListOut>(
        tab === "pending"
          ? "/api/v1/approvals?status=pending"
          : "/api/v1/approvals?status=all"
      ),
    refetchInterval: tab === "pending" ? 15_000 : false, // auto-refresh pending tab
  });

  function afterReview() {
    setReviewing(null);
    qc.invalidateQueries({ queryKey: ["approvals"] });
    qc.invalidateQueries({ queryKey: ["approvals-count"] });
  }

  const items = data?.items ?? [];
  const pendingCount = data?.pending_count ?? 0;

  const TABS: { key: Tab; label: string }[] = [
    { key: "pending", label: `Pending${pendingCount > 0 ? ` (${pendingCount})` : ""}` },
    { key: "all",     label: "All requests" },
  ];

  return (
    <div className="page-enter">
      <PageHeader
        title="Approvals"
        subtitle="Review require_approval decisions raised by the policy engine."
        actions={
          <button
            onClick={() => refetch()}
            className="btn-secondary flex items-center gap-1.5 text-sm"
            title="Refresh"
          >
            <RefreshCw className="size-3.5" />
            Refresh
          </button>
        }
      />

      {/* Tabs */}
      <div className="px-8 pb-4">
        <div
          className="inline-flex rounded-lg p-0.5"
          style={{ background: "rgba(148,163,184,0.06)", border: "1px solid rgba(148,163,184,0.1)" }}
        >
          {TABS.map((t) => (
            <button
              key={t.key}
              onClick={() => setTab(t.key)}
              className="px-4 py-1.5 rounded-md text-sm font-medium transition-all"
              style={
                tab === t.key
                  ? { background: "#1E2A3E", color: "white", boxShadow: "0 1px 4px rgba(0,0,0,0.3)" }
                  : { color: "#64748B" }
              }
            >
              {t.label}
            </button>
          ))}
        </div>
      </div>

      {/* Content */}
      <div className="px-8 pb-8 space-y-2">
        {isLoading ? (
          <div className="text-sm text-ink-400 py-8 text-center">Loading…</div>
        ) : items.length === 0 ? (
          <div
            className="rounded-xl py-12 text-center"
            style={{ background: "#FFFFFF", border: "1px solid rgba(148,163,184,0.08)" }}
          >
            <CheckCircle2 className="size-8 mx-auto mb-3" style={{ color: "#10B981" }} />
            <div className="text-sm font-medium text-ink-50 mb-1">
              {tab === "pending" ? "No pending approvals" : "No approval requests yet"}
            </div>
            <div className="text-xs text-ink-400">
              {tab === "pending"
                ? "Requests appear here when a policy returns require_approval."
                : "Approval requests will appear here once agents start hitting require_approval policies."}
            </div>
          </div>
        ) : (
          items.map((item) => (
            <ApprovalRow
              key={item.id}
              item={item}
              onReview={(it, action) => setReviewing({ item: it, action })}
            />
          ))
        )}
      </div>

      {/* Review modal */}
      {reviewing && (
        <ReviewModal
          item={reviewing.item}
          action={reviewing.action}
          onClose={() => setReviewing(null)}
          onDone={afterReview}
        />
      )}
    </div>
  );
}
