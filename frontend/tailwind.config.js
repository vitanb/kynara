/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        // ── Neutral ramp (light monochrome — WorkOS / Notion family) ──────────
        // NOTE: scale is intentionally "inverted" vs a dark theme so existing
        // usage (bg-ink-950 = page, text-ink-50 = primary text) renders light.
        // Low indices = dark ink for TEXT. High indices = light surfaces for BG.
        ink: {
          50:  "#18181B",   // primary text — near black
          100: "#27272A",   // strong text
          200: "#3F3F46",   // body text
          300: "#52525B",   // muted text
          400: "#71717A",   // faint text / icons
          500: "#A1A1AA",   // placeholder / disabled
          600: "#D4D4D8",   // strong hairline / hover border
          700: "#E7E5E4",   // hairline border / secondary surface
          800: "#FFFFFF",   // card surface
          900: "#FAFAF9",   // sidebar / elevated rail
          950: "#FFFFFF",   // page background
        },
        // ── Brand accent — monochrome ink (no purple). Reserved for primary
        // actions and active states; color is otherwise semantic only. ────────
        accent: {
          50:  "#F4F4F5",
          100: "#E7E5E4",
          300: "#A1A1AA",
          400: "#52525B",   // "info" text / subtle links
          500: "#27272A",   // primary hover
          600: "#18181B",   // primary resting (near black)
          700: "#000000",
          800: "#000000",
        },
        // Secondary data accent — muted teal for charts / live indicators
        teal: {
          300: "#5EEAD4",
          400: "#0D9488",
          500: "#0F766E",
          600: "#115E59",
          700: "#134E4A",
        },
        // ── Status palette — tuned for contrast on white surfaces ─────────────
        ok:     { 300: "#6EE7B7", 400: "#059669", 500: "#047857", 700: "#065F46" },
        warn:   { 300: "#FCD34D", 400: "#B45309", 500: "#92400E", 700: "#78350F" },
        danger: { 300: "#FDA4AF", 400: "#DC2626", 500: "#B91C1C", 700: "#991B1B" },
      },
      fontFamily: {
        sans: ["Inter", "ui-sans-serif", "system-ui"],
        mono: ["ui-monospace", "Menlo", "monospace"],
      },
      boxShadow: {
        // Soft, low-contrast elevation — no colored glows.
        "card":        "0 1px 2px rgba(24,24,27,0.04), 0 1px 3px rgba(24,24,27,0.04)",
        "card-hover":  "0 4px 16px rgba(24,24,27,0.08), 0 1px 3px rgba(24,24,27,0.05)",
        "glow-accent": "0 0 0 3px rgba(24,24,27,0.08)",
        "glow-sm":     "0 1px 2px rgba(24,24,27,0.05)",
        "btn":         "0 1px 2px rgba(24,24,27,0.08)",
        "btn-hover":   "0 2px 6px rgba(24,24,27,0.12)",
      },
    },
  },
  plugins: [],
};
