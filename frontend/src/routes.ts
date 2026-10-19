import type { LucideIcon } from "lucide-react";
import {
  Activity,
  Bot,
  Building2,
  ChartNoAxesCombined,
  ClipboardCheck,
  ClipboardList,
  LayoutGrid,
} from "lucide-react";

// Fonte única das telas: a sidebar e as rotas leem daqui.
export type NavItem = {
  path: string;
  label: string;
  icon: LucideIcon;
};

export const ITEMS: NavItem[] = [
  { path: "/panorama", label: "Panorama", icon: LayoutGrid },
  { path: "/receita", label: "Receita", icon: ChartNoAxesCombined },
  { path: "/uc-360", label: "UC 360", icon: Building2 },
  { path: "/inspecoes", label: "Inspeções", icon: ClipboardCheck },
  { path: "/ordens", label: "Ordens", icon: ClipboardList },
  { path: "/operacao", label: "Operação", icon: Activity },
  { path: "/assistente", label: "Assistente", icon: Bot },
];
