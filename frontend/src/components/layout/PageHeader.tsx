import { ReactNode } from "react";

export default function PageHeader({
  title, subtitle, actions,
}: { title: string; subtitle?: string; actions?: ReactNode }) {
  return (
    <div
      className="flex items-center justify-between gap-6 px-6 py-4"
      style={{ borderBottom: "1px solid var(--s0-border)" }}
    >
      <div className="min-w-0">
        <h1 className="text-base font-semibold tracking-tight text-white leading-none">{title}</h1>
        {subtitle ? (
          <p className="text-xs text-ink-400 mt-1 max-w-xl leading-relaxed">{subtitle}</p>
        ) : null}
      </div>
      {actions ? (
        <div className="flex items-center gap-2 shrink-0">{actions}</div>
      ) : null}
    </div>
  );
}
