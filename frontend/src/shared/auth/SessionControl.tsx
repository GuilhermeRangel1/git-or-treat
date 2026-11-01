import { LogOut } from "lucide-react";
import { useSession } from "./useSession";

export default function SessionControl() {
  const session = useSession();
  if (!session.configured || !session.user) return null;
  return (
    <button
      type="button"
      className="inline-flex min-h-10 items-center gap-2 rounded-lg px-3 text-sm text-muted hover:bg-canvas hover:text-content focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand"
      onClick={() => void session.logout().catch(() => {})}
      aria-label="Sair da conta"
    >
      <LogOut size={16} aria-hidden="true" />
      <span className="hidden sm:inline">Sair</span>
    </button>
  );
}
