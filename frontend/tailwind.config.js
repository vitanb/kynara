/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        // ── Neutral ramp — slate-tinted, DARK orientation (default theme is dark)
        // bg-ink-950 = page (darkest), text-ink-50 = primary text (lightest).
        ink: {
          50:  "#F8FAFC",   // primary text
          100: "#E8EDF5",   // strong text
          200: "#CBD5E1",   // body text
          300: "#94A3B8",   // muted text
          400: "#64748B",   // faint text / icons
          500: "#475569",   // subtle / disabled
          600: "#334155",   // strong hairline
          700: "#1E2533",   // hairline / secondary surface
          800: "#151A24",   // card surface
          900: "#0F131B",   // sidebar / elevated rail
          950: "#0B0E14",   // page background
        },
        // ── Brand accent — Mercury blue ───────────────────────────────────────
        accent: {
          50:  "#EFF6FF",
          100: "#DBEAFE",
          300: "#93C5FD",
          400: "#60A5FA",   // accent text / links on dark
          500: "#3B82F6",   // primary interactive (dark)
          600: "#2563EB",   // primary resting (light) / button
          700: "#1D4ED8",   // hover
          800: "#1E40AF",
        },
        // Secondary data accent — cyan/teal for charts / live indicators
        teal: {
          300: "#7DD3FC",
          400: "#38BDF8",
          500: "#0EA5E9",
          600: "#0284C7",
          700: "#0369A1",
        },
        // ── Status palette — readable on dark and light surfaces ──────────────
        ok:     { 300: "#6EE7B7", 400: "#10B981", 500: "#059669", 700: "#047857" },
        warn:   { 300: "#FCD34D", 400: "#F59E0B", 500: "#D97706", 700: "#B45309" },
        danger: { 300: "#FDA4AF", 400: "#F43F5E", 500: "#E11D48", 700: "#BE123C" },
      },
      fontFamily: {
        sans: ["Inter", "ui-sans-serif", "system-ui"],
        mono: ["ui-monospace", "Menlo", "monospace"],
      },
      boxShadow: {
        "card":        "0 1px 2px rgba(2,6,23,0.20), 0 1px 3px rgba(2,6,23,0.16)",
        "card-hover":  "0 6px 24px rgba(2,6,23,0.28), 0 1px 3px rgba(2,6,23,0.20)",
        "glow-accent": "0 0 0 3px rgba(59,130,246,0.22)",
        "glow-sm":     "0 0 12px rgba(59,130,246,0.18)",
        "btn":         "0 1px 2px rgba(2,6,23,0.30)",
        "btn-hover":   "0 4px 14px rgba(37,99,235,0.35)",
      },
    },
  },
  plugins: [],
};
