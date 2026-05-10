import { useState } from "react";
import { useQuery, useMutation } from "@tanstack/react-query";
import { ShieldCheck, ShieldAlert, CheckCircle2, XCircle, Download } from "lucide-react";
import PageHeader from "@/components/layout/PageHeader";
import { api } from "@/lib/api";

export default function AuditPage() {
  const [filters, setFilters] = useState({
    actor: "", event_type: "", outcome: "",
  });
  const [verifyResult, setVerifyResult] = useState<any>(null);

  const qs = Object.entries(filters).filter(([, v]) => v).map(([k, v]) => `${encodeURIComponent(k)}=${encodeURIComponent(v)}`).join("&");

  function exportCsv() {
    const token = localStorage.getItem("kynara_access") ?? "";
    const url = `/api/v1/audit/export${qs ? `?${qs}` : ""}`;
    // fetch with auth, then trigger download
    fetch(url, { headers: { Authorization: `Bearer ${token}` } })
      .then((r) => r.blob())
      .then((blob) => {
        const a = document.createElement("a");
        a.href = URL.createObjectURL(blob);
        a.download = `audit-export-${new Date().toISOString().slice(0, 10)}.csv`;
        a.click();
        URL.revokeObjectURL(a.href);
      });
  }
  const { data = [] } = useQuery({
    queryKey: ["audit", qs],
    queryFn: () => api.get<any[]>(`/api/v1/audit/events?${qs}&limit=200`),
  });
  const verify = useMutation({
    mutationFn: () => api.post<any>("/api/v1/audit/verify"),
    onSuccess: (r) => setVerifyResult(r),
  });

  return (
    <div>
      <PageHeader
        title="Audit log"
        subtitle="Every authorization decision and admin change, hash-chained for tamper evidence."
        actions={
          <div className="flex items-center gap-2">
            <button className="btn-secondary" onClick={exportCsv}>
              <Download className="size-4" /> Export CSV
            </button>
            <button className="btn-primary" onClick={() => verify.mutate()}>
              <ShieldCheck className="size-4" /> Verify chain
            </button>
          </div>
        }
      />
      <div className="px-8 py-6 space-y-4">
        {verifyResult && (
          <div className={`card p-4 flex items-start gap-3 ${verifyResult.ok ? "" : "border-danger-700"}`}>
            {verifyResult.ok
              ? <CheckCircle2 className="size-5 text-ok-500 mt-0.5" />
              : <ShieldAlert className="size-5 text-danger-500 mt-0.5" />}
            <div>
              <div className="font-medium">
                {verifyResult.ok ? "Chain verified" : `Chain broken at #${verifyResult.broken_at}`}
              </div>
              <div className="text-xs text-ink-400 font-mono mt-1">
                tip: {verifyResult.tip.slice(0, 24)}… · verified {verifyResult.count} events
              </div>
            </div>
          </div>
        )}

        <div className="card p-3 flex flex-wrap items-end gap-3">
          <Filter label="Actor" value={filters.actor}
                  onChange={(v) => setFilters({ ...filters, actor: v })} />
          <Filter label="Event type" value={filters.event_type}
                  onChange={(v) => setFilters({ ...filters, event_type: v })} />
          <div>
            <label className="label">Outcome</label>
            <select className="input"
                    value={filters.outcome}
                    onChange={(e) => setFilters({ ...filters, outcome: e.target.value })}>
              <option value="">any</option>
              <option value="allow">allow</option>
              <option value="deny">deny</option>
              <option value="require_approval">require_approval</option>
            </select>
          </div>
        </div>

        <div className="card overflow-hidden">
          <table className="table">
            <thead><tr>
              <th>#</th><th>When</th><th>Event</th><th>Actor</th><th>Resource</th>
              <th>Outcome</th><th>Reason</th><th className="w-24">Hash</th>
            </tr></thead>
            <tbody>
              {data.map((e) => (
                <tr key={e.id}>
                  <td className="font-mono text-xs text-ink-400">#{e.sequence}</td>
                  <td className="text-xs text-ink-300">{new Date(e.ts).toLocaleString()}</td>
                  <td className="text-xs font-mono">{e.event_type}</td>
                  <td className="text-xs font-mono">{e.actor}</td>
                  <td className="text-xs font-mono">
                    {e.resource_type ? `${e.resource_type}:${e.resource_id || ""}` : "—"}
                  </td>
                  <td>
                    {e.outcome === "allow" && <span className="pill-ok"><CheckCircle2 className="size-3" /> allow</span>}
                    {e.outcome === "deny"  && <span className="pill-danger"><XCircle className="size-3" /> deny</span>}
                    {e.outcome === "require_approval" && <span className="pill-warn">approval</span>}
                    {e.outcome === "info" && <span className="pill-info">info</span>}
                  </td>
                  <td className="text-xs text-ink-400 max-w-[320px] truncate">
                    {e.payload?.reason || e.payload?.action || "—"}
                  </td>
                  <td className="font-mono text-[10px] text-ink-500 truncate">{e.entry_hash?.slice(0, 8)}…</td>
                </tr>
              ))}
              {!data.length && (
                <tr><td colSpan={8} className="text-center text-ink-500 py-8 text-xs">
                  No events match these filters.
                </td></tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

function Filter({ label, value, onChange }: { label: string; value: string; onChange: (v: string) => void }) {
  return (
    <div>
      <label className="label">{label}</label>
      <input className="input w-56 font-mono" value={value}
             onChange={(e) => onChange(e.target.value)} />
    </div>
  );
}
