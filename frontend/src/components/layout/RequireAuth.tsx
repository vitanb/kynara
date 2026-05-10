import { useEffect } from "react";
import { Navigate } from "react-router-dom";
import { useAuth } from "@/lib/auth";

export default function RequireAuth({ children }: { children: React.ReactNode }) {
  const { me, loading, bootstrap } = useAuth();
  useEffect(() => { bootstrap(); }, [bootstrap]);
  if (loading) {
    return (
      <div className="flex h-full items-center justify-center text-ink-400 text-sm">
        <div className="animate-pulse">Loading Kynara…</div>
      </div>
    );
  }
  if (!me) return <Navigate to="/login" replace />;
  return <>{children}</>;
}
