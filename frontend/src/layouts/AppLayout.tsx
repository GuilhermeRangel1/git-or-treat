import { Outlet, matchPath, useLocation } from "react-router-dom";
import type { NavItem } from "./navigation";
import Header from "./components/Header";
import Sidebar from "./components/Sidebar";
import "./layout.css";

export default function AppLayout({ navigation }: { navigation: NavItem[] }) {
  const { pathname } = useLocation();
  const current = navigation.find((item) =>
    matchPath({ path: item.path, end: false }, pathname),
  );
  return (
    <div className="layout">
      <Sidebar items={navigation} />
      <div className="layout__main">
        <Header
          title={current?.label ?? "grid360"}
          subtitle={current?.subtitle}
          requirementId={current?.requirementId}
        />
        <main className="content">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
