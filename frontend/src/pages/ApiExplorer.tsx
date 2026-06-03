import { useAuth } from "@/lib/auth";

export default function ApiExplorerPage() {
  const { me } = useAuth();
  const token = typeof window !== "undefined" ? localStorage.getItem("kynara_access") : null;
  const swaggerUrl = token
    ? `/api/v1/docs?token=${encodeURIComponent(token)}`
    : "/api/v1/docs";

  return (
    <div className="flex flex-col h-full">
      <div className="px-6 py-4 flex items-center justify-between flex-shrink-0"
        style={{ borderBottom: "1px solid rgba(148,163,184,.1)" }}>
        <div>
          <h1 className="text-base font-bold text-ink-50">API Explorer</h1>
          <p className="text-xs text-ink-400 mt-0.5">
            Interactive REST API reference — your session token is pre-filled.
          </p>
        </div>
        <a href="/api/v1/openapi.json" target="_blank"
          className="text-xs text-indigo-400 hover:underline">
          Download OpenAPI spec ↗
        </a>
      </div>
      <iframe
        src={swaggerUrl}
        className="flex-1 w-full border-0"
        title="Kynara API Explorer"
        style={{ minHeight: 0 }}
      />
    </div>
  );
}
