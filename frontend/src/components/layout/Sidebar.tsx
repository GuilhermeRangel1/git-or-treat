import { NavLink } from "react-router-dom";
import type { NavItem } from "@/routes.ts";
import { useTheme } from "@/hooks/useTheme.ts";

type SidebarProps = {
  items: NavItem[];
};

/* Marca do grid360: anel + raio + ponto. As cores vêm dos tokens do tema. */
function LogoMark() {
  return (
    <svg
      className="sidebar__logo-mark"
      viewBox="0 0 40 40"
      fill="none"
      aria-hidden="true"
    >
      <path
        d="M33 12.5A15 15 0 1 1 25.1 5.9"
        stroke="var(--accent-goiaba)"
        strokeWidth="3"
        strokeLinecap="round"
      />
      <path
        d="M22.5 10 14 21.5h5.5L17.5 30 26 18.5h-5.5z"
        fill="var(--accent-pistache)"
        stroke="var(--accent-pistache)"
        strokeWidth="1.6"
        strokeLinejoin="round"
      />
      <circle cx="30" cy="8.4" r="2.6" fill="var(--accent-pistache)" />
    </svg>
  );
}

export default function Sidebar({ items }: SidebarProps) {
  const { theme, toggleTheme } = useTheme();

  return (
    <aside className="sidebar" aria-label="Menu lateral principal">
      <header className="sidebar__brand">
        <div className="sidebar__logo-row">
          <LogoMark />
          <h2 className="sidebar__logo">grid360</h2>
        </div>
        <p className="sidebar__tagline">V—ENERGY / INTELIGÊNCIA</p>
      </header>

      <nav className="sidebar__nav" aria-label="Navegação principal">
        <ul>
          {items.map(({ path, label, icon: Icon }) => (
            <li key={path}>
              <NavLink
                to={path}
                className={({ isActive }: { isActive: boolean }) =>
                  `nav-item${isActive ? " nav-item--active" : ""}`
                }
              >
                <Icon className="nav-item__icon" size={22} strokeWidth={1.75} aria-hidden="true" />
                <span className="nav-item__label">{label}</span>
              </NavLink>
            </li>
          ))}
        </ul>
      </nav>

      <div className="sidebar__footer">
        <button
          type="button"
          onClick={toggleTheme}
          className="theme-toggle-btn"
          title={`Alternar para tema ${theme === "light" ? "escuro" : "claro"}`}
        >
          <span className="theme-toggle-icon">{theme === "light" ? "🌙" : "☀️"}</span>
          <span>Tema {theme === "light" ? "Escuro" : "Claro"}</span>
        </button>
      </div>
    </aside>
  );
}
