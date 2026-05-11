/**
 * SsoCallback — landing page after a successful SSO login.
 *
 * The backend redirects here as:
 *   /app/sso-callback#access_token=<jwt>
 *
 * This page:
 *  1. Reads the access_token from the URL hash.
 *  2. Persists it to localStorage (same key the API client uses).
 *  3. Redirects to /app/dashboard.
 *
 * If anything is wrong (no token, obviously malformed) it redirects to /login
 * with an error hint.
 */
import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";

export default function SsoCallbackPage() {
  const nav = useNavigate();
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    // Parse the hash fragment — React Router doesn't expose it, use window directly.
    const hash = window.location.hash.slice(1); // drop leading '#'
    const params = new URLSearchParams(hash);
    const token = params.get("access_token");

    if (!token) {
      setError("No access token received from SSO provider.");
      setTimeout(() => nav("/login?sso_error=missing_token", { replace: true }), 2000);
      return;
    }

    // Basic sanity: must be a JWT (3 base64 segments separated by '.')
    if (token.split(".").length !== 3) {
      setError("Received token looks malformed.");
      setTimeout(() => nav("/login?sso_error=bad_token", { replace: true }), 2000);
      return;
    }

    // Store and move on
    localStorage.setItem("kynara_access", token);
    // Clear the fragment so the token doesn't stay in browser history
    window.history.replaceState(null, "", window.location.pathname);
    nav("/app/dashboard", { replace: true });
  }, [nav]);

  if (error) {
    return (
      <div className="flex h-screen items-center justify-center bg-surface text-center p-8">
        <div>
          <div className="text-danger-400 text-sm font-medium mb-2">SSO login failed</div>
          <div className="text-ink-400 text-xs">{error}</div>
          <div className="text-ink-600 text-xs mt-3">Redirecting to login…</div>
        </div>
      </div>
    );
  }

  return (
    <div className="flex h-screen items-center justify-center bg-surface">
      <div className="text-ink-400 text-sm animate-pulse">Completing SSO sign-in…</div>
    </div>
  );
}
