import { useRef } from "react";
import { Outlet, matchPath, useLocation } from "react-router-dom";
import type { NavItem } from "./navigation";
import Header from "./components/Header";
import Sidebar from "./components/Sidebar";
import MobileMenu from "./components/MobileMenu";

export default function AppLayout({ navigation }: { navigation: NavItem[] }) {
  const { pathname } = useLocation();
  const menuRef = useRef<HTMLDialogElement>(null);
  const current = navigation.find((item) =>
    matchPath({ path: item.path, end: false }, pathname),
  );
  return (
    <div className="flex min-h-dvh bg-canvas">
      <a
        href="#main-content"
        className="sr-only z-50 rounded-lg bg-surface p-3 text-content focus:not-sr-only focus:fixed focus:top-2 focus:left-2"
      >
        Ir para o conteúdo
      </a>
      <Sidebar items={navigation} />
      <div className="min-w-0 flex-1">
        <Header
          title={current?.label ?? "grid360"}
          onOpenMenu={() => menuRef.current?.showModal()}
        />
        <main
          id="main-content"
          tabIndex={-1}
          className="w-full px-4 pt-5 pb-8 lg:max-w-[1184px] lg:px-12 lg:pt-6 lg:pb-12"
        >
          {!current?.contentHeading && (
            <div className="flex flex-col gap-2">
              <h1 className="font-heading text-[26px] leading-[34px] font-semibold lg:text-[32px] lg:leading-10 lg:tracking-[-0.64px]">
                {current?.label ?? "grid360"}
              </h1>
              {current?.subtitle && (
                <p className="text-sm leading-[22px] text-muted">
                  {current.subtitle}
                </p>
              )}
            </div>
          )}
          <Outlet />
        </main>
      </div>
      <MobileMenu items={navigation} dialogRef={menuRef} />
    </div>
  );
}
