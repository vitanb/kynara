import { createContext, useContext, useEffect, useState } from "react";

export type ThemeId = "mercury" | "mercury-light";

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
    id: "mercury",
    label: "Mercury",
    description: "Dark · Blue",
    sidebar: "#0F131B",
    accent:  "#3B82F6",
    card:    "#151A24",
  },
  {
    id: "mercury-light",
    label: "Mercury Light",
    description: "Light · Blue",
    sidebar: "#F8FAFC",
    accent:  "#2563EB",
    card:    "#FFFFFF",
  },
];

const VALID: ThemeId[] = ["mercury", "mercury-light"];

interface ThemeCtx {
  theme: ThemeId;
  setTheme: (t: ThemeId) => void;
}

const Ctx = createContext<ThemeCtx>({ theme: "mercury", setTheme: () => {} });

export function ThemeProvider({ children }: { children: React.ReactNode }) {
  const [theme, setThemeState] = useState<ThemeId>(() => {
    const saved = localStorage.getItem("kynara_theme") as ThemeId | null;
    return saved && VALID.includes(saved) ? saved : "mercury";
  });

  function setTheme(t: ThemeId) {
    setThemeState(t);
    localStorage.setItem("kynara_theme", t);
  }

  useEffect(() => {
    document.documentElement.setAttribute("data-theme", theme);
  }, [theme]);

  useEffect(() => {
    document.documentElement.setAttribute("data-theme", theme);
  }, []);

  return <Ctx.Provider value={{ theme, setTheme }}>{children}</Ctx.Provider>;
}

export function useTheme() { return useContext(Ctx); }
