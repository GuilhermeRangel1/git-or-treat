import { useContext } from "react";
import { ThemeContext, type ThemeContextType } from "../contexts/theme-context-def.ts";

export function useTheme(): ThemeContextType {
  const context = useContext(ThemeContext);
  if (!context) {
    throw new Error("useTheme deve ser usado dentro de um ThemeProvider");
  }
  return context;
}
