import { useEffect, type RefObject } from "react";
import { X } from "lucide-react";
import Brand from "@/shared/ui/Brand";
import IconButton from "@/shared/ui/IconButton";
import type { NavItem } from "../navigation";
import Navigation from "./Navigation";

export default function MobileMenu({
  items,
  dialogRef,
}: {
  items: NavItem[];
  dialogRef: RefObject<HTMLDialogElement | null>;
}) {
  useEffect(() => {
    const desktop = window.matchMedia("(min-width: 1024px)");
    const closeOnDesktop = () => {
      if (desktop.matches) dialogRef.current?.close();
    };
    desktop.addEventListener("change", closeOnDesktop);
    return () => desktop.removeEventListener("change", closeOnDesktop);
  }, [dialogRef]);

  return (
    <dialog
      ref={dialogRef}
      id="mobile-navigation"
      aria-labelledby="mobile-navigation-title"
      className="fixed inset-0 m-0 h-dvh max-h-none w-full max-w-none border-0 bg-surface px-4 pt-3 pb-6 text-content backdrop:bg-canvas open:flex open:flex-col open:gap-4"
    >
      <div className="flex items-center justify-between gap-4">
        <Brand />
        <IconButton
          autoFocus
          onClick={() => dialogRef.current?.close()}
          aria-label="Fechar menu"
        >
          <X size={18} strokeWidth={1.75} aria-hidden="true" />
        </IconButton>
      </div>
      <h2
        id="mobile-navigation-title"
        className="font-heading text-[26px] leading-[34px] font-semibold"
      >
        Navegação
      </h2>
      <Navigation
        items={items}
        mobile
        onNavigate={() => dialogRef.current?.close()}
      />
    </dialog>
  );
}
