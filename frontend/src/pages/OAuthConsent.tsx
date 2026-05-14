/**
 * OAuth 2.0 consent page — shown when Claude (or any OAuth client) initiates
 * an authorization flow.  The backend redirects here after validating params.
 *
 * Route: /oauth/consent  (public, but requires the user to log in first)
 */
import { useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { ShieldCheck, Bot, ScrollText } from "lucide-react";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";

export default function OAuthConsentPage() {
  const [params] = useSearchParams();
  const { me } = useAuth();
  const navigate = useNavigate();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const clientId           = params.get("client_id") ?? "";
  const redirectUri        = params.get("redirect_uri") ?? "";
  const scope              = params.get("scope") ?? "read";
  const state              = params.get("state") ?? "";
  const codeChallenge      = params.get("code_challenge") ?? "";
  const codeChallengeMethod = params.get("code_challenge_method") ?? "S256";

  const scopes = scope.split(/[\s+,]+/).filter(Boolean);

  const scopeLabels: Record<string, { label: string; icon: typeof Bot }> = {
    read:  { label: "Read agents, roles, policies, and audit logs", icon: ScrollText },
    write: { label: "Approve/reject requests and manage agents",    icon: Bot },
  };

  // If not logged in, do a hard redirect to the login page so the user can
  // authenticate and come back here. React Router's navigate() is unreliable
  // in a new tab opened by an OAuth client, so we use window.location.replace
  // which always works regardless of router state.
  if (!me) {
    const returnTo = encodeURIComponent(window.location.pathname + window.location.search);
    window.location.replace(`/login?next=${returnTo}`);
    return (
      <div
        className="min-h-screen flex items-center justify-center"
        style={{ background: "var(--s0-page)" }}
      >
        <p className="text-sm text-slate-400">Redirecting to sign-in…</p>
      </div>
    );
  }

  function handleApprove() {
    setLoading(true);
    setError(null);

    // Submit as a native HTML form so the browser follows the 302 redirect
    // to Claude's callback URL naturally.  fetch() with redirect:"manual"
    // returns an opaque response and can't read the Location header, which
    // means the code never reaches Claude's callback listener.
    const form = document.createElement("form");
    form.method = "POST";
    form.action = "/oauth/authorize";

    const fields: Record<string, string> = {
      client_id:             clientId,
      redirect_uri:          redirectUri,
      scope,
      state,
      code_challenge:        codeChallenge,
      code_challenge_method: codeChallengeMethod,
      // Token embedded as hidden field — backend accepts it from form body
      // when there is no Authorization header (native form submit).
      access_token:          localStorage.getItem("kynara_access") ?? "",
    };

    for (const [name, value] of Object.entries(fields)) {
      const input = document.createElement("input");
      input.type  = "hidden";
      input.name  = name;
      input.value = value;
      form.appendChild(input);
    }

    document.body.appendChild(form);
    form.submit();
  }

  function handleDeny() {
    const params = new URLSearchParams({ error: "access_denied", state });
    window.location.href = `${redirectUri}?${params.toString()}`;
  }

  return (
    <div
      className="min-h-screen flex items-center justify-center p-4"
      style={{ background: "var(--s0-page)" }}
    >
      <div
        className="w-full max-w-md rounded-2xl p-8 shadow-2xl"
        style={{ background: "var(--s0-card)", border: "1px solid var(--s0-border)" }}
      >
        {/* Header */}
        <div className="flex items-center justify-center gap-3 mb-6">
          <img
            src="/logo.svg"
            className="size-10 rounded-xl"
            alt="Kynara"
          />
          <div className="text-slate-400 text-lg font-light">+</div>
          <div
            className="size-10 rounded-xl flex items-center justify-center text-sm font-bold text-white"
            style={{ background: "linear-gradient(135deg, #7C3AED, #4F46E5)" }}
          >
            C
          </div>
        </div>

        <h1 className="text-lg font-bold text-white text-center mb-1">
          Connect Kynara to Claude
        </h1>
        <p className="text-sm text-slate-400 text-center mb-6">
          Claude is requesting access to your Kynara workspace as{" "}
          <span className="text-slate-200 font-medium">{me.email}</span>
        </p>

        {/* Permissions */}
        <div
          className="rounded-xl p-4 mb-6 space-y-3"
          style={{ background: "rgba(148,163,184,0.05)", border: "1px solid rgba(148,163,184,0.1)" }}
        >
          <div className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">
            Claude will be able to
          </div>
          {scopes.map((s) => {
            const info = scopeLabels[s];
            if (!info) return null;
            const Icon = info.icon;
            return (
              <div key={s} className="flex items-start gap-3">
                <div
                  className="size-7 rounded-lg flex items-center justify-center shrink-0 mt-0.5"
                  style={{ background: "rgba(99,102,241,0.12)" }}
                >
                  <Icon className="size-3.5" style={{ color: "#818CF8" }} />
                </div>
                <p className="text-sm text-slate-300 leading-snug">{info.label}</p>
              </div>
            );
          })}
          <div className="flex items-start gap-3">
            <div
              className="size-7 rounded-lg flex items-center justify-center shrink-0 mt-0.5"
              style={{ background: "rgba(16,185,129,0.1)" }}
            >
              <ShieldCheck className="size-3.5" style={{ color: "#10B981" }} />
            </div>
            <p className="text-sm text-slate-300 leading-snug">
              All actions are logged in the Kynara audit trail
            </p>
          </div>
        </div>

        {error && (
          <div
            className="rounded-lg p-3 mb-4 text-sm"
            style={{ background: "rgba(244,63,94,0.1)", color: "#F43F5E", border: "1px solid rgba(244,63,94,0.2)" }}
          >
            {error}
          </div>
        )}

        {/* Actions */}
        <div className="flex gap-3">
          <button
            onClick={handleDeny}
            disabled={loading}
            className="flex-1 py-2.5 rounded-xl text-sm font-medium text-slate-300 hover:text-white transition-colors"
            style={{ background: "rgba(148,163,184,0.08)", border: "1px solid rgba(148,163,184,0.12)" }}
          >
            Deny
          </button>
          <button
            onClick={handleApprove}
            disabled={loading}
            className="flex-1 py-2.5 rounded-xl text-sm font-semibold text-white transition-all"
            style={{
              background: "var(--s0-accent)",
              boxShadow: "0 0 0 1px var(--s0-accent-ring)",
              opacity: loading ? 0.7 : 1,
            }}
          >
            {loading ? "Authorizing..." : "Allow access"}
          </button>
        </div>

        <p className="text-center text-xs text-slate-500 mt-4">
          You can revoke this access at any time in{" "}
          <a href="/app/settings" className="text-slate-400 hover:text-slate-200 underline">
            Settings
          </a>
        </p>
      </div>
    </div>
  );
}
