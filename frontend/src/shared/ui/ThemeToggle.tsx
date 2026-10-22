import { Moon, Sun } from "lucide-react";
import { useTheme } from "@/shared/theme/useTheme";
import IconButton from "./IconButton";

export default function ThemeToggle() {
  const { theme, toggleTheme } = useTheme();
  const Icon = theme === "light" ? Moon : Sun;
  const label = `Alternar para tema ${theme === "light" ? "escuro" : "claro"}`;
  return (
    <IconButton onClick={toggleTheme} aria-label={label} title={label}>
      <Icon size={18} strokeWidth={1.75} aria-hidden="true" />
    </IconButton>
  );
}
