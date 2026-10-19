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
  const conversationLayout = current?.layout === "conversation";
  return (
    <div
      className={`flex bg-canvas ${conversationLayout ? "h-dvh overflow-hidden" : "min-h-dvh"}`}
    >
      <a
        href="#main-content"
        className="sr-only z-50 rounded-lg bg-surface p-3 text-content focus:not-sr-only focus:fixed focus:top-2 focus:left-2"
      >
        Ir para o conteúdo
      </a>
      <Sidebar items={navigation} />
      <div
        className={`min-w-0 flex-1 ${conversationLayout ? "flex min-h-0 flex-col" : ""}`}
      >
        <Header
          title={current?.section ?? current?.label ?? "grid360"}
          onOpenMenu={() => menuRef.current?.showModal()}
        />
        <main
          id="main-content"
          tabIndex={-1}
          className={
            conversationLayout
              ? "flex min-h-0 w-full flex-1 flex-col px-4 pt-3 pb-4 lg:px-8 lg:pt-6 lg:pb-8"
              : "w-full px-4 pt-5 pb-8 lg:max-w-[1184px] lg:px-12 lg:pt-6 lg:pb-12"
          }
        >
          {!current?.contentHeading && (
            <div className="flex w-full flex-col gap-2 lg:max-w-[810px]">
              <h1 className="font-heading text-[26px] leading-[34px] font-semibold lg:w-fit lg:text-[32px] lg:leading-10 lg:tracking-[-0.64px]">
                {current?.title ?? current?.label ?? "grid360"}
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
