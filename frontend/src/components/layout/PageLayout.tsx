import type { ReactNode } from "react";
import Sidebar from "./Sidebar.tsx";
import Header from "./Header.tsx";
import { ITEMS } from "@/routes.ts";

type PageLayoutProps = {
  title: string;
  subtitle?: string;
  requirementId?: string;
  children?: ReactNode;
};

export default function PageLayout({
  title,
  subtitle,
  requirementId,
  children,
}: PageLayoutProps) {
  return (
    <div className="layout">
      <Sidebar items={ITEMS} />
      <div className="layout__main">
        <Header title={title} subtitle={subtitle} requirementId={requirementId} />
        <main className="content">{children}</main>
      </div>
    </div>
  );
}
