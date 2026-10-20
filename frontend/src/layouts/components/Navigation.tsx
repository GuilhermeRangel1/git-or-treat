import { NavLink } from "react-router-dom";
import type { NavItem } from "../navigation";

type NavigationProps = {
  items: NavItem[];
  mobile?: boolean;
  onNavigate?: () => void;
};

export default function Navigation({
  items,
  mobile = false,
  onNavigate,
}: NavigationProps) {
  return (
    <nav aria-label={mobile ? "Navegação mobile" : "Navegação principal"}>
      <ul className={mobile ? "flex flex-col gap-4" : "flex flex-col gap-3"}>
        {items.map(({ path, label, icon: Icon }) => (
          <li key={path}>
            <NavLink
              to={path}
              onClick={onNavigate}
              className={({ isActive }) =>
                `relative flex items-center gap-3 rounded-lg p-3 text-sm leading-5 font-medium focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand ${mobile ? "min-h-12" : "min-h-11"} ${isActive ? "bg-selected text-content before:absolute before:top-3 before:left-0 before:h-5 before:w-[3px] before:bg-brand" : "text-muted hover:bg-nav-hover"}`
              }
            >
              <Icon
                size={20}
                strokeWidth={1.75}
                className="shrink-0"
                aria-hidden="true"
              />
              <span>{label}</span>
            </NavLink>
          </li>
        ))}
      </ul>
    </nav>
  );
}
