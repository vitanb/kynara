/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        // Carbon-slate dark — neutral, enterprise-grade (Linear / GitHub Dark / Stripe)
        ink: {
          50:  "#F1F5F9",   // slate-100
          100: "#CBD5E1",   // slate-300
          200: "#94A3B8",   // slate-400
          300: "#64748B",   // slate-500
          400: "#475569",   // slate-600
          500: "#334155",   // slate-700
          600: "#1E293B",   // slate-800
          700: "#141D2E",   // custom deep slate
          800: "#0D1421",   // card surface
          900: "#080C14",   // sidebar / elevated
          950: "#05080F",   // page background
        },
        // Brand — electric indigo (Stripe / Linear / Notion family)
        accent: {
          50:  "#EEF2FF",
          100: "#E0E7FF",
          300: "#A5B4FC",
          400: "#818CF8",
          500: "#6366F1",   // primary interactive
          600: "#4F46E5",   // button resting
          700: "#4338CA",   // button hover
          800: "#3730A3",
        },
        // Secondary data accent — teal (charts, live indicators)
        teal: {
          300: "#5EEAD4",
          400: "#2DD4BF",
          500: "#14B8A6",
          600: "#0D9488",
          700: "#0F766E",
        },
        // Status palette — vivid, high contrast
        ok:     { 300: "#6EE7B7", 400: "#34D399", 500: "#10B981", 700: "#047857" },
        warn:   { 300: "#FCD34D", 400: "#FBBF24", 500: "#F59E0B", 700: "#B45309" },
        danger: { 300: "#FDA4AF", 400: "#FB7185", 500: "#F43F5E", 700: "#BE123C" },
      },
      fontFamily: {
        sans: ["Inter", "ui-sans-serif", "system-ui"],
        mono: ["ui-monospace", "Menlo", "monospace"],
      },
      boxShadow: {
        "card":        "0 1px 3px rgba(0,0,0,0.4), 0 1px 2px rgba(0,0,0,0.3)",
        "card-hover":  "0 4px 16px rgba(0,0,0,0.5), 0 1px 4px rgba(0,0,0,0.3)",
        "glow-accent": "0 0 0 3px rgba(99,102,241,0.25)",
        "glow-sm":     "0 0 16px rgba(99,102,241,0.2)",
        "btn":         "0 1px 2px rgba(0,0,0,0.4), inset 0 1px 0 rgba(255,255,255,0.06)",
        "btn-hover":   "0 2px 8px rgba(79,70,229,0.45), inset 0 1px 0 rgba(255,255,255,0.06)",
      },
    },
  },
  plugins: [],
};
