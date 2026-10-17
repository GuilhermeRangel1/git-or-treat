import { NavLink } from "react-router-dom";
import type { NavItem } from "@/routes.ts";
import { useTheme } from "@/hooks/useTheme.ts";

type SidebarProps = {
  items: NavItem[];
};

export default function Sidebar({ items }: SidebarProps) {
  const { theme, toggleTheme } = useTheme();

  return (
    <aside className="sidebar" aria-label="Menu lateral principal">
      <header className="sidebar__brand">
        <h2 className="sidebar__logo">grid360</h2>
        <p className="sidebar__tagline">V—ENERGY / INTELIGÊNCIA</p>
      </header>

      <nav className="sidebar__nav" aria-label="Navegação principal">
        <ul>
          {items.map((item) => (
            <li key={item.path}>
              <NavLink
                to={item.path}
                className={({ isActive }: { isActive: boolean }) =>
                  `nav-item${isActive ? " nav-item--active" : ""}`
                }
              >
                <span className="nav-item__label">{item.label}</span>
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
