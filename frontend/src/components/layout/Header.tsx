import { useTheme } from "@/hooks/useTheme.ts";

type HeaderProps = {
  title: string;
  subtitle?: string;
  requirementId?: string;
};

export default function Header({ title, subtitle, requirementId }: HeaderProps) {
  const { theme, toggleTheme } = useTheme();

  return (
    <header className="page-header">
      <div className="page-header__info">
        <div className="page-header__meta">
          {requirementId && <span className="req-tag">{requirementId}</span>}
          {subtitle && <span className="page-header__subtitle">{subtitle}</span>}
        </div>
        <h1 className="page-header__title">{title}</h1>
      </div>

      <div className="page-header__actions">
        <span className="api-status-badge api-status-badge--online">
          <span className="status-dot"></span>
          FastAPI Online
        </span>
        <button
          type="button"
          onClick={toggleTheme}
          className="header-theme-toggle"
          aria-label={`Alternar para tema ${theme === "light" ? "escuro" : "claro"}`}
        >
          {theme === "light" ? "🌙 Escuro" : "☀️ Claro"}
        </button>
      </div>
    </header>
  );
}
