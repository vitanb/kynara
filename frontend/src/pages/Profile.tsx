import { useState, useRef } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import {
  UserCircle, Save, Check, Globe, Palette, Image, Mail, ShieldCheck,
} from "lucide-react";
import PageHeader from "@/components/layout/PageHeader";
import { useAuth } from "@/lib/auth";
import { useTheme, THEMES, type ThemeId } from "@/lib/theme";
import { api } from "@/lib/api";

// Curated set of IANA timezones grouped by region
const TZ_OPTIONS: { label: string; value: string }[] = [
  // UTC
  { label: "UTC", value: "UTC" },
  // Americas
  { label: "America/New_York (ET)", value: "America/New_York" },
  { label: "America/Chicago (CT)", value: "America/Chicago" },
  { label: "America/Denver (MT)", value: "America/Denver" },
  { label: "America/Los_Angeles (PT)", value: "America/Los_Angeles" },
  { label: "America/Phoenix (AZ)", value: "America/Phoenix" },
  { label: "America/Anchorage (AK)", value: "America/Anchorage" },
  { label: "Pacific/Honolulu (HI)", value: "Pacific/Honolulu" },
  { label: "America/Toronto", value: "America/Toronto" },
  { label: "America/Vancouver", value: "America/Vancouver" },
  { label: "America/Sao_Paulo", value: "America/Sao_Paulo" },
  { label: "America/Argentina/Buenos_Aires", value: "America/Argentina/Buenos_Aires" },
  { label: "America/Mexico_City", value: "America/Mexico_City" },
  { label: "America/Bogota", value: "America/Bogota" },
  // Europe
  { label: "Europe/London (GMT/BST)", value: "Europe/London" },
  { label: "Europe/Paris (CET)", value: "Europe/Paris" },
  { label: "Europe/Berlin", value: "Europe/Berlin" },
  { label: "Europe/Amsterdam", value: "Europe/Amsterdam" },
  { label: "Europe/Stockholm", value: "Europe/Stockholm" },
  { label: "Europe/Warsaw", value: "Europe/Warsaw" },
  { label: "Europe/Helsinki", value: "Europe/Helsinki" },
  { label: "Europe/Kyiv", value: "Europe/Kyiv" },
  { label: "Europe/Moscow", value: "Europe/Moscow" },
  { label: "Europe/Istanbul", value: "Europe/Istanbul" },
  // Asia / Pacific
  { label: "Asia/Dubai", value: "Asia/Dubai" },
  { label: "Asia/Kolkata (IST)", value: "Asia/Kolkata" },
  { label: "Asia/Dhaka", value: "Asia/Dhaka" },
  { label: "Asia/Bangkok", value: "Asia/Bangkok" },
  { label: "Asia/Singapore", value: "Asia/Singapore" },
  { label: "Asia/Hong_Kong", value: "Asia/Hong_Kong" },
  { label: "Asia/Shanghai", value: "Asia/Shanghai" },
  { label: "Asia/Tokyo (JST)", value: "Asia/Tokyo" },
  { label: "Asia/Seoul", value: "Asia/Seoul" },
  { label: "Australia/Sydney", value: "Australia/Sydney" },
  { label: "Australia/Melbourne", value: "Australia/Melbourne" },
  { label: "Australia/Perth", value: "Australia/Perth" },
  { label: "Pacific/Auckland", value: "Pacific/Auckland" },
  // Africa
  { label: "Africa/Cairo", value: "Africa/Cairo" },
  { label: "Africa/Johannesburg", value: "Africa/Johannesburg" },
  { label: "Africa/Lagos", value: "Africa/Lagos" },
  { label: "Africa/Nairobi", value: "Africa/Nairobi" },
];

function AvatarCircle({ name, email, url, size = 80 }: { name?: string | null; email: string; url?: string | null; size?: number }) {
  const initials = ((name || email || "?")[0]).toUpperCase();
  if (url) {
    return (
      <img
        src={url}
        alt="avatar"
        className="rounded-full object-cover shrink-0"
        style={{ width: size, height: size, border: "2px solid var(--s0-border)" }}
        onError={(e) => { (e.target as HTMLImageElement).style.display = "none"; }}
      />
    );
  }
  return (
    <div
      className="rounded-full flex items-center justify-center shrink-0 font-bold text-white select-none"
      style={{
        width: size, height: size,
        background: "var(--s0-accent)",
        fontSize: size * 0.38,
        boxShadow: "0 0 0 2px var(--s0-accent-ring)",
      }}
    >
      {initials}
    </div>
  );
}

export default function ProfilePage() {
  const { me } = useAuth();
  const { theme, setTheme } = useTheme();
  const queryClient = useQueryClient();

  const [displayName, setDisplayName] = useState(me?.display_name ?? "");
  const [timezone, setTimezone] = useState(me?.timezone ?? "UTC");
  const [avatarUrl, setAvatarUrl] = useState(me?.avatar_url ?? "");
  const [saved, setSaved] = useState(false);

  const save = useMutation({
    mutationFn: () =>
      api.patch<any>("/api/v1/auth/me", {
        display_name: displayName.trim() || null,
        timezone: timezone || null,
        avatar_url: avatarUrl.trim() || null,
      }),
    onSuccess: () => {
      // Refresh the /me query so AppShell initials update
      queryClient.invalidateQueries({ queryKey: ["me"] });
      setSaved(true);
      setTimeout(() => setSaved(false), 2500);
    },
  });

  if (!me) return null;

  const nowInTz = (() => {
    try {
      return new Intl.DateTimeFormat("en-US", {
        timeZone: timezone || "UTC",
        hour: "2-digit", minute: "2-digit", second: "2-digit",
        hour12: false,
      }).format(new Date());
    } catch { return "—"; }
  })();

  return (
    <div>
      <PageHeader
        title="My Profile"
        subtitle="Manage your personal settings — avatar, display name, theme, and timezone."
      />

      <div className="px-8 py-6 grid grid-cols-1 lg:grid-cols-3 gap-6 max-w-5xl">

        {/* ── Left column: identity ── */}
        <div className="lg:col-span-2 space-y-5">

          {/* Avatar + name card */}
          <div className="card p-5">
            <div className="flex items-center gap-2 mb-4">
              <UserCircle className="size-4 text-accent-500" />
              <span className="font-medium text-sm">Identity</span>
            </div>

            <div className="flex items-center gap-5 mb-5">
              <AvatarCircle name={displayName || me.display_name} email={me.email} url={avatarUrl} size={72} />
              <div className="min-w-0">
                <div className="font-semibold text-sm text-ink-100 truncate">
                  {displayName || me.display_name || me.email}
                </div>
                <div className="text-xs text-ink-400 mt-0.5 flex items-center gap-1.5">
                  <Mail className="size-3" /> {me.email}
                </div>
                <div className="text-xs text-ink-500 mt-0.5 flex items-center gap-1.5">
                  <ShieldCheck className="size-3" /> {me.seat_role}
                </div>
              </div>
            </div>

            {/* Display name */}
            <div className="space-y-3">
              <div>
                <label className="label">Display name</label>
                <input
                  className="input"
                  placeholder={me.email}
                  value={displayName}
                  onChange={e => setDisplayName(e.target.value)}
                  maxLength={120}
                />
              </div>

              {/* Avatar URL */}
              <div>
                <label className="label flex items-center gap-1.5">
                  <Image className="size-3" /> Avatar URL
                  <span className="text-ink-500 font-normal">(optional — link to any image)</span>
                </label>
                <input
                  className="input font-mono text-xs"
                  placeholder="https://example.com/avatar.png"
                  value={avatarUrl}
                  onChange={e => setAvatarUrl(e.target.value)}
                />
                <p className="text-[10px] text-ink-500 mt-1">
                  Leave empty to use your initials. Paste a publicly accessible image URL.
                </p>
              </div>
            </div>
          </div>

          {/* Timezone */}
          <div className="card p-5">
            <div className="flex items-center gap-2 mb-4">
              <Globe className="size-4 text-accent-500" />
              <span className="font-medium text-sm">Timezone</span>
            </div>
            <div>
              <label className="label">Preferred timezone</label>
              <select
                className="input"
                value={timezone}
                onChange={e => setTimezone(e.target.value)}
              >
                {TZ_OPTIONS.map(t => (
                  <option key={t.value} value={t.value}>{t.label}</option>
                ))}
              </select>
              <p className="text-[10px] text-ink-500 mt-1.5">
                Audit log timestamps will be shown in this timezone. Current time:{" "}
                <span className="font-mono text-ink-300">{nowInTz}</span>{" "}
                <span className="text-ink-500">({timezone})</span>
              </p>
            </div>
          </div>

          {/* Save button */}
          <button
            className="btn-primary"
            disabled={save.isPending || saved}
            onClick={() => save.mutate()}
          >
            {saved
              ? <><Check className="size-4" /> Saved</>
              : <><Save className="size-4" /> {save.isPending ? "Saving…" : "Save changes"}</>
            }
          </button>
          {save.isError && (
            <p className="text-xs text-danger-400 mt-1">
              {(save.error as any)?.message || "Failed to save — please try again."}
            </p>
          )}
        </div>

        {/* ── Right column: theme ── */}
        <div className="space-y-5">
          <div className="card p-5">
            <div className="flex items-center gap-2 mb-4">
              <Palette className="size-4 text-accent-500" />
              <span className="font-medium text-sm">Appearance</span>
            </div>
            <div className="space-y-2">
              {THEMES.map(t => (
                <button
                  key={t.id}
                  onClick={() => setTheme(t.id as ThemeId)}
                  className="w-full flex items-center gap-3 px-3 py-3 rounded-lg text-left transition-all"
                  style={{
                    background: theme === t.id ? "rgba(255,255,255,0.06)" : "rgba(255,255,255,0.02)",
                    border: theme === t.id
                      ? `1px solid var(--s0-accent-ring)`
                      : "1px solid rgba(148,163,184,0.08)",
                  }}
                >
                  {/* Preview swatch row */}
                  <div className="flex gap-1 shrink-0">
                    <div className="size-5 rounded-sm" style={{ background: t.sidebar }} />
                    <div className="size-5 rounded-sm" style={{ background: t.accent }} />
                    <div className="size-5 rounded-sm" style={{ background: t.card }} />
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="text-xs font-medium text-ink-100">{t.label}</div>
                    <div className="text-[10px] text-ink-500">{t.description}</div>
                  </div>
                  {theme === t.id && (
                    <Check className="size-3.5 shrink-0" style={{ color: "var(--s0-accent-text)" }} />
                  )}
                </button>
              ))}
            </div>
            <p className="text-[10px] text-ink-600 mt-3">
              Theme is stored locally in your browser and applied immediately.
            </p>
          </div>

          {/* Account info (read-only) */}
          <div className="card p-4 space-y-2 text-xs">
            <div className="text-ink-400 font-medium text-[10px] uppercase tracking-wide mb-2">Account</div>
            <div className="flex justify-between border-t border-ink-800 pt-2">
              <span className="text-ink-500">Email</span>
              <span className="text-ink-300 font-mono">{me.email}</span>
            </div>
            <div className="flex justify-between border-t border-ink-800 pt-2">
              <span className="text-ink-500">Role</span>
              <span className={`text-[10px] font-medium px-1.5 py-0.5 rounded-full ${
                me.seat_role === "owner" || me.seat_role === "admin" ? "pill-info" :
                me.seat_role === "developer" ? "pill-teal" :
                me.seat_role === "auditor" ? "pill-warn" : "pill-neutral"
              }`}>{me.seat_role}</span>
            </div>
            <div className="flex justify-between border-t border-ink-800 pt-2">
              <span className="text-ink-500">MFA</span>
              <span className={me.mfa_enrolled ? "text-ok-400" : "text-ink-500"}>
                {me.mfa_enrolled ? "Enrolled" : "Not enrolled"}
              </span>
            </div>
            <div className="flex justify-between border-t border-ink-800 pt-2">
              <span className="text-ink-500">User ID</span>
              <span className="text-ink-500 font-mono text-[10px]">{me.user_id.slice(0, 12)}…</span>
            </div>
          </div>
        </div>

      </div>
    </div>
  );
}
