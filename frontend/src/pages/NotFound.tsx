import { Link, useNavigate } from "react-router-dom";
import { ArrowLeft, Home } from "lucide-react";

export default function NotFoundPage() {
  const navigate = useNavigate();

  return (
    <div
      className="min-h-screen flex flex-col items-center justify-center p-8 text-center"
      style={{ background: "var(--s0-card)" }}
    >
      {/* Logo */}
      <Link to="/" className="flex items-center gap-3 mb-16 hover:opacity-80 transition-opacity">
        <img src="/logo.svg" className="size-9 rounded-xl" alt="Kynara" />
        <div className="text-left">
          <div className="text-base font-bold text-ink-50 tracking-tight leading-none">Kynara</div>
          <div className="text-[10px] font-medium mt-0.5" style={{ color: "var(--s0-accent-text)", letterSpacing: "0.06em" }}>
            AI Control Plane
          </div>
        </div>
      </Link>

      {/* 404 display */}
      <div
        className="relative mb-8 select-none"
        style={{ fontSize: "9rem", fontWeight: 900, lineHeight: 1, color: "transparent",
          background: "linear-gradient(135deg, #18181B 0%, #52525B 50%, #312E81 100%)",
          WebkitBackgroundClip: "text", backgroundClip: "text",
          filter: "drop-shadow(0 0 60px var(--s0-accent-ring))",
        }}
      >
        404
      </div>

      <h1 className="text-2xl font-bold text-ink-50 mb-3">Page not found</h1>
      <p className="text-sm text-ink-400 max-w-sm mb-10 leading-relaxed">
        The page you're looking for doesn't exist or has been moved.
        Double-check the URL or head back to somewhere familiar.
      </p>

      <div className="flex flex-col sm:flex-row items-center gap-3">
        <button
          onClick={() => navigate(-1)}
          className="inline-flex items-center gap-2 px-5 py-2.5 rounded-lg text-sm font-medium text-ink-300 hover:text-ink-50 transition-colors"
          style={{
            background: "rgba(148,163,184,0.06)",
            border: "1px solid rgba(148,163,184,0.12)",
          }}
        >
          <ArrowLeft className="size-4" /> Go back
        </button>
        <Link
          to="/"
          className="inline-flex items-center gap-2 px-5 py-2.5 rounded-lg text-sm font-semibold text-ink-50 transition-all"
          style={{
            background: "var(--s0-accent)",
            boxShadow: "0 0 0 1px var(--s0-accent-ring), 0 4px 20px var(--s0-accent-ring)",
          }}
        >
          <Home className="size-4" /> Back to home
        </Link>
      </div>

      {/* Subtle grid decoration */}
      <div
        className="fixed inset-0 pointer-events-none -z-10"
        style={{
          backgroundImage:
            "linear-gradient(var(--s0-accent-subtle) 1px, transparent 1px), linear-gradient(90deg, var(--s0-accent-subtle) 1px, transparent 1px)",
          backgroundSize: "48px 48px",
        }}
      />
    </div>
  );
}
