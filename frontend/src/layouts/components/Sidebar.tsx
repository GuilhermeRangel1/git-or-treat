import Brand from "@/shared/ui/Brand";
import type { NavItem } from "../navigation";
import Navigation from "./Navigation";

export default function Sidebar({ items }: { items: NavItem[] }) {
  return (
    <aside
      className="sticky top-0 hidden h-dvh w-56 shrink-0 flex-col gap-3 overflow-y-auto bg-surface p-4 lg:flex"
      aria-label="Menu lateral principal"
    >
      <Brand />
      <p className="font-mono text-xs leading-[18px] text-muted">
        V—ENERGY / INTELIGÊNCIA
      </p>
      <div className="h-px shrink-0 bg-divider" />
      <Navigation items={items} />
    </aside>
  );
}
