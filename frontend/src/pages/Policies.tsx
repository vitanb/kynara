import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { Plus, ShieldCheck, ShieldOff } from "lucide-react";
import PageHeader from "@/components/layout/PageHeader";
import { api } from "@/lib/api";

export default function PoliciesPage() {
  const { data = [] } = useQuery({
    queryKey: ["policies"],
    queryFn: () => api.get<any[]>("/api/v1/policies"),
  });

  return (
    <div>
      <PageHeader
        title="Policies"
        subtitle="ABAC rules evaluated in priority order. First matching decision wins; default is deny."
        actions={
          <Link to="/app/policies/new" className="btn-primary">
            <Plus className="size-4" /> New policy
          </Link>
        }
      />
      <div className="px-8 py-6">
        {data.length === 0 ? (
          <div className="card p-10 text-center">
            <ShieldOff className="size-10 mx-auto mb-3 text-ink-600" />
            <div className="text-sm text-ink-300 font-medium mb-1">No policies yet</div>
            <p className="text-xs text-ink-500 mb-4">
              Policies define what agents can do. Without any policies, all agent requests are denied by default.
            </p>
            <Link to="/app/policies/new" className="btn-primary mx-auto">
              <Plus className="size-4" /> Create your first policy
            </Link>
          </div>
        ) : (
        <div className="card overflow-hidden">
          <table className="table">
            <thead>
              <tr>
                <th className="w-10">Pri</th><th>Policy</th><th>Actions</th>
                <th>Resources</th><th>Effect</th><th>Enabled</th>
              </tr>
            </thead>
            <tbody>
              {data.map((p) => (
                <tr key={p.id}>
                  <td className="font-mono text-xs text-ink-400">{p.priority}</td>
                  <td>
                    <Link to={`/app/policies/${p.id}`}
                          className="text-sm font-medium text-accent-500 hover:underline">
                      {p.display_name}
                    </Link>
                    <div className="text-xs text-ink-400">{p.description || "—"}</div>
                  </td>
                  <td className="text-xs font-mono">
                    {(p.actions || []).join(", ") || "*"}
                  </td>
                  <td className="text-xs font-mono">
                    {(p.resource_types || []).join(", ") || "*"}
                  </td>
                  <td>
                    <span className={
                      p.effect === "allow" ? "pill-ok" :
                      p.effect === "deny"  ? "pill-danger" : "pill-warn"
                    }>
                      <ShieldCheck className="size-3" /> {p.effect}
                    </span>
                  </td>
                  <td>{p.is_enabled ? <span className="pill-ok">on</span> : <span className="pill-danger">off</span>}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        )}
      </div>
    </div>
  );
}
