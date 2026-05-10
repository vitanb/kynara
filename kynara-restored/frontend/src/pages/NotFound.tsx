import { Link, useNavigate } from "react-router-dom";
import { Hexagon, ArrowLeft, Home } from "lucide-react";

export default function NotFoundPage() {
  const navigate = useNavigate();

  return (
    <div
      className="min-h-screen flex flex-col items-center justify-center p-8 text-center"
      style={{ background: "#05080F" }}
    >
      {/* Logo */}
      <Link to="/" className="flex items-center gap-3 mb-16 hover:opacity-80 transition-opacity">
        <div
          className="size-9 rounded-xl flex items-center justify-center"
          style={{
            background: "#4F46E5",
            boxShadow: "0 0 0 1px rgba(99,102,241,0.5), 0 4px 14px rgba(79,70,229,0.4)",
          }}
        >
          <Hexagon className="size-5 text-white" strokeWidth={2} />
        </div>
        <div className="text-left">
          <div className="text-base font-bold text-white tracking-tight leading-none">Kynara</div>
          <div className="text-[10px] font-medium mt-0.5" style={{ color: "#818CF8", letterSpacing: "0.06em" }}>
            AI Control Plane
          </div>
        </div>
      </Link>

      {/* 404 display */}
      <div
        className="relative mb-8 select-none"
        style={{ fontSize: "9rem", fontWeight: 900, lineHeight: 1, color: "transparent",
          background: "linear-gradient(135deg, #4F46E5 0%, #818CF8 50%, #312E81 100%)",
          WebkitBackgroundClip: "text", backgroundClip: "text",
          filter: "drop-shadow(0 0 60px rgba(99,102,241,0.3))",
        }}
      >
        404
      </div>

      <h1 className="text-2xl font-bold text-white mb-3">Page not found</h1>
      <p className="text-sm text-slate-400 max-w-sm mb-10 leading-relaxed">
        The page you're looking for doesn't exist or has been moved.
        Double-check the URL or head back to somewhere familiar.
      </p>

      <div className="flex flex-col sm:flex-row items-center gap-3">
        <button
          onClick={() => navigate(-1)}
          className="inline-flex items-center gap-2 px-5 py-2.5 rounded-lg text-sm font-medium text-slate-300 hover:text-white transition-colors"
          style={{
            background: "rgba(148,163,184,0.06)",
            border: "1px solid rgba(148,163,184,0.12)",
          }}
        >
          <ArrowLeft className="size-4" /> Go back
        </button>
        <Link
          to="/"
          className="inline-flex items-center gap-2 px-5 py-2.5 rounded-lg text-sm font-semibold text-white transition-all"
          style={{
            background: "#4F46E5",
            boxShadow: "0 0 0 1px rgba(99,102,241,0.5), 0 4px 20px rgba(79,70,229,0.35)",
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
            "linear-gradient(rgba(99,102,241,0.03) 1px, transparent 1px), linear-gradient(90deg, rgba(99,102,241,0.03) 1px, transparent 1px)",
          backgroundSize: "48px 48px",
        }}
      />
    </div>
  );
}
