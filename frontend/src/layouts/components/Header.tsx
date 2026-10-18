import { Menu } from "lucide-react";
import Brand from "@/shared/ui/Brand";
import IconButton from "@/shared/ui/IconButton";
import ThemeToggle from "@/shared/ui/ThemeToggle";

export default function Header({
  title,
  onOpenMenu,
}: {
  title: string;
  onOpenMenu: () => void;
}) {
  return (
    <header className="w-full bg-surface px-4 py-2.5 lg:max-w-[1184px] lg:bg-transparent lg:px-12 lg:pt-12 lg:pb-0">
      <div className="flex h-11 items-center justify-between gap-4">
        <div className="lg:hidden">
          <Brand />
        </div>
        <p className="hidden font-mono text-xs leading-[18px] text-muted lg:block">
          V—ENERGY / {title.toLocaleUpperCase("pt-BR")}
        </p>
        <div className="flex gap-2">
          <ThemeToggle />
          <IconButton
            className="lg:hidden"
            onClick={onOpenMenu}
            aria-label="Abrir menu"
            aria-haspopup="dialog"
            aria-controls="mobile-navigation"
          >
            <Menu size={24} strokeWidth={1.75} aria-hidden="true" />
          </IconButton>
        </div>
      </div>
    </header>
  );
}
