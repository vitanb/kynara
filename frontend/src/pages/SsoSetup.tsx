import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useMutation } from "@tanstack/react-query";
import {
  Plug, ArrowLeft, Shield, KeyRound, FileText, Check, Copy,
} from "lucide-react";
import PageHeader from "@/components/layout/PageHeader";
import { api } from "@/lib/api";

type Protocol = "oidc" | "saml";

export default function SsoSetupPage() {
  const nav = useNavigate();
  const [protocol, setProtocol] = useState<Protocol>("oidc");
  const [step, setStep] = useState(1);

  const [form, setForm] = useState({
    provider: "okta",
    domain: "",
    // OIDC
    issuer: "",
    client_id: "",
    client_secret: "",
    // SAML
    idp_entity_id: "",
    idp_sso_url: "",
    idp_x509: "",
    attribute_mapping_email: "email",
    attribute_mapping_name: "displayName",
    attribute_mapping_groups: "groups",
  });

  const create = useMutation({
    mutationFn: () => api.post("/api/v1/sso/connections", { protocol, ...form }),
    onSuccess: () => nav("/app/settings"),
  });

  const base = (import.meta.env.VITE_API_BASE || window.location.origin).replace(/\/$/, "");
  const spMetadata  = `${base}/api/v1/auth/sso/saml/metadata`;
  const spAcs       = `${base}/api/v1/auth/sso/saml/acs`;
  const spEntity    = "urn:kynara:sp";
  const oidcRedirect = `${base}/api/v1/auth/sso/oidc/callback`;

  return (
    <div>
      <PageHeader
        title="Add identity provider"
        subtitle="Configure SAML 2.0 or OpenID Connect to delegate authentication to your IdP."
        actions={
          <button onClick={() => nav("/app/settings")} className="btn-ghost">
            <ArrowLeft className="size-4" /> Back
          </button>
        }
      />
      <div className="px-8 py-6 max-w-4xl">
        <Stepper step={step} />

        {step === 1 && (
          <div className="card p-6 space-y-4">
            <div className="text-sm font-medium">Choose provider and protocol</div>
            <div className="grid grid-cols-2 gap-3">
              {(["okta", "azure-ad", "google", "onelogin", "pingidentity", "custom"] as const).map((p) => (
                <button key={p}
                        onClick={() => setForm({ ...form, provider: p })}
                        className={`card p-4 text-left transition hover:border-accent-500
                          ${form.provider === p ? "border-accent-500 ring-1 ring-accent-500/50" : ""}`}>
                  <div className="flex items-center gap-2">
                    <Plug className="size-4 text-accent-500" />
                    <span className="text-sm font-medium capitalize">{p.replace("-", " ")}</span>
                  </div>
                </button>
              ))}
            </div>

            <div className="grid grid-cols-2 gap-3 pt-2">
              <button
                onClick={() => setProtocol("oidc")}
                className={`card p-4 text-left transition
                  ${protocol === "oidc" ? "border-accent-500 ring-1 ring-accent-500/50" : ""}`}>
                <div className="flex items-center gap-2 mb-1">
                  <KeyRound className="size-4 text-accent-500" />
                  <span className="text-sm font-medium">OpenID Connect</span>
                </div>
                <p className="text-xs text-ink-400">
                  Modern OAuth2-based flow with PKCE. Recommended for Okta, Azure AD, Google.
                </p>
              </button>
              <button
                onClick={() => setProtocol("saml")}
                className={`card p-4 text-left transition
                  ${protocol === "saml" ? "border-accent-500 ring-1 ring-accent-500/50" : ""}`}>
                <div className="flex items-center gap-2 mb-1">
                  <Shield className="size-4 text-accent-500" />
                  <span className="text-sm font-medium">SAML 2.0</span>
                </div>
                <p className="text-xs text-ink-400">
                  Enterprise standard with signed assertions. Required by most Fortune 500.
                </p>
              </button>
            </div>

            <div className="flex justify-end pt-2">
              <button className="btn-primary" onClick={() => setStep(2)}>Next</button>
            </div>
          </div>
        )}

        {step === 2 && (
          <div className="card p-6 space-y-4">
            <div className="flex items-center gap-2 text-sm font-medium">
              <FileText className="size-4 text-accent-500" />
              Share our Service Provider details with your IdP admin
            </div>
            <p className="text-xs text-ink-400">
              Your IdP administrator needs these values to register Kynara as a trusted
              application.
            </p>

            {protocol === "saml" ? (
              <div className="space-y-3">
                <CopyRow label="SP Entity ID" value={spEntity} />
                <CopyRow label="ACS URL" value={spAcs} />
                <CopyRow label="Metadata URL" value={spMetadata} />
                <div className="text-xs text-ink-400 border-l-2 border-accent-500 pl-3 py-1">
                  We require signed AuthnRequests and signed assertions. Encrypted assertions
                  supported (recommended). NameID format: emailAddress.
                </div>
              </div>
            ) : (
              <div className="space-y-3">
                <CopyRow label="Redirect URI" value={oidcRedirect} />
                <CopyRow label="Grant types" value="authorization_code, refresh_token" />
                <CopyRow label="Scopes" value="openid email profile groups offline_access" />
                <div className="text-xs text-ink-400 border-l-2 border-accent-500 pl-3 py-1">
                  We use PKCE (S256) and verify the id_token signature against your JWKS endpoint.
                  Token endpoint auth: client_secret_basic.
                </div>
              </div>
            )}

            <div className="flex justify-between pt-2">
              <button className="btn-ghost" onClick={() => setStep(1)}>Back</button>
              <button className="btn-primary" onClick={() => setStep(3)}>Next</button>
            </div>
          </div>
        )}

        {step === 3 && (
          <div className="card p-6 space-y-4">
            <div className="text-sm font-medium">
              Enter your IdP details
            </div>

            <Field label="Email domain (users with this domain will be routed to this IdP)">
              <input className="input font-mono" placeholder="acme.com"
                     value={form.domain}
                     onChange={(e) => setForm({ ...form, domain: e.target.value })} />
            </Field>

            {protocol === "oidc" ? (
              <>
                <Field label="Issuer URL">
                  <input className="input font-mono" placeholder="https://your-org.okta.com"
                         value={form.issuer}
                         onChange={(e) => setForm({ ...form, issuer: e.target.value })} />
                </Field>
                <div className="grid grid-cols-2 gap-3">
                  <Field label="Client ID">
                    <input className="input font-mono" value={form.client_id}
                           onChange={(e) => setForm({ ...form, client_id: e.target.value })} />
                  </Field>
                  <Field label="Client Secret">
                    <input type="password" className="input font-mono"
                           value={form.client_secret}
                           onChange={(e) => setForm({ ...form, client_secret: e.target.value })} />
                  </Field>
                </div>
              </>
            ) : (
              <>
                <Field label="IdP Entity ID">
                  <input className="input font-mono" value={form.idp_entity_id}
                         placeholder="http://www.okta.com/exk..."
                         onChange={(e) => setForm({ ...form, idp_entity_id: e.target.value })} />
                </Field>
                <Field label="IdP SSO URL">
                  <input className="input font-mono" value={form.idp_sso_url}
                         placeholder="https://your-org.okta.com/app/.../sso/saml"
                         onChange={(e) => setForm({ ...form, idp_sso_url: e.target.value })} />
                </Field>
                <Field label="IdP X.509 signing certificate">
                  <textarea className="input font-mono text-xs min-h-[140px]"
                            value={form.idp_x509}
                            placeholder="-----BEGIN CERTIFICATE-----"
                            onChange={(e) => setForm({ ...form, idp_x509: e.target.value })} />
                </Field>
              </>
            )}

            <div className="pt-3 border-t border-ink-800">
              <div className="text-xs font-medium mb-2 text-ink-300">Attribute mapping</div>
              <div className="grid grid-cols-3 gap-3">
                <Field label="Email">
                  <input className="input font-mono" value={form.attribute_mapping_email}
                         onChange={(e) => setForm({ ...form, attribute_mapping_email: e.target.value })} />
                </Field>
                <Field label="Display name">
                  <input className="input font-mono" value={form.attribute_mapping_name}
                         onChange={(e) => setForm({ ...form, attribute_mapping_name: e.target.value })} />
                </Field>
                <Field label="Groups">
                  <input className="input font-mono" value={form.attribute_mapping_groups}
                         onChange={(e) => setForm({ ...form, attribute_mapping_groups: e.target.value })} />
                </Field>
              </div>
            </div>

            <div className="flex justify-between pt-2">
              <button className="btn-ghost" onClick={() => setStep(2)}>Back</button>
              <button className="btn-primary" onClick={() => create.mutate()}>
                <Check className="size-4" /> Create connection
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

function Stepper({ step }: { step: number }) {
  const steps = ["Provider", "SP details", "IdP config"];
  return (
    <div className="flex items-center gap-3 mb-6">
      {steps.map((label, i) => {
        const idx = i + 1;
        const active = idx === step;
        const done = idx < step;
        return (
          <div key={label} className="flex items-center gap-3">
            <div className={`size-7 rounded-full text-xs flex items-center justify-center font-medium
              ${active ? "bg-accent-500 text-white"
                : done ? "bg-ok-500 text-white"
                : "bg-ink-800 text-ink-400"}`}>
              {done ? <Check className="size-3" /> : idx}
            </div>
            <span className={`text-sm ${active ? "text-ink-100" : "text-ink-400"}`}>{label}</span>
            {i < steps.length - 1 && <div className="h-px w-8 bg-ink-800" />}
          </div>
        );
      })}
    </div>
  );
}

function CopyRow({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <div className="text-xs text-ink-400 mb-1">{label}</div>
      <div className="flex items-center gap-2">
        <code className="flex-1 bg-ink-900 border border-ink-800 rounded p-2 text-xs font-mono break-all">
          {value}
        </code>
        <button className="btn-ghost" onClick={() => navigator.clipboard.writeText(value)}>
          <Copy className="size-4" />
        </button>
      </div>
    </div>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return <div><label className="label">{label}</label>{children}</div>;
}
