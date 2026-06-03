import { createContext, useContext, useEffect, useState } from "react";

export type ThemeId = "linen" | "midnight";

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
    id: "linen",
    label: "Linen",
    description: "Light · Monochrome",
    sidebar: "#FAFAF9",
    accent:  "#18181B",
    card:    "#FFFFFF",
  },
  {
    id: "midnight",
    label: "Midnight",
    description: "Dark · Ink",
    sidebar: "#0E0E10",
    accent:  "#FAFAFA",
    card:    "#141416",
  },
];

const VALID: ThemeId[] = ["linen", "midnight"];

interface ThemeCtx {
  theme: ThemeId;
  setTheme: (t: ThemeId) => void;
}

const Ctx = createContext<ThemeCtx>({ theme: "linen", setTheme: () => {} });

export function ThemeProvider({ children }: { children: React.ReactNode }) {
  const [theme, setThemeState] = useState<ThemeId>(() => {
    const saved = localStorage.getItem("kynara_theme") as ThemeId | null;
    return saved && VALID.includes(saved) ? saved : "linen";
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
