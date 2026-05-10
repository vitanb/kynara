import { createContext, useContext, useEffect, useState } from "react";

export type ThemeId = "midnight" | "slate" | "google";

export interface ThemeDef {
  id: ThemeId;
  label: string;
  description: string;
  /** Preview swatches */
  sidebar: string;
  accent: string;
  card: string;
}

export const THEMES: ThemeDef[] = [
  {
    id: "midnight",
    label: "Midnight",
    description: "Deep navy · Indigo",
    sidebar: "#080C14",
    accent:  "#4F46E5",
    card:    "#0D1421",
  },
  {
    id: "slate",
    label: "Slate",
    description: "Corporate dark · Blue",
    sidebar: "#162032",
    accent:  "#2563EB",
    card:    "#1A2744",
  },
  {
    id: "google",
    label: "Google",
    description: "Light · Google Blue",
    sidebar: "#F8F9FA",
    accent:  "#1A73E8",
    card:    "#FFFFFF",
  },
];

interface ThemeCtx {
  theme: ThemeId;
  setTheme: (t: ThemeId) => void;
}

const Ctx = createContext<ThemeCtx>({ theme: "midnight", setTheme: () => {} });

export function ThemeProvider({ children }: { children: React.ReactNode }) {
  const [theme, setThemeState] = useState<ThemeId>(() => {
    const saved = localStorage.getItem("kynara_theme");
    return (saved as ThemeId) || "midnight";
  });

  function setTheme(t: ThemeId) {
    setThemeState(t);
    localStorage.setItem("kynara_theme", t);
  }

  useEffect(() => {
    document.documentElement.setAttribute("data-theme", theme);
  }, [theme]);

  // Apply on first render
  useEffect(() => {
    document.documentElement.setAttribute("data-theme", theme);
  }, []);

  return <Ctx.Provider value={{ theme, setTheme }}>{children}</Ctx.Provider>;
}

export function useTheme() { return useContext(Ctx); }
