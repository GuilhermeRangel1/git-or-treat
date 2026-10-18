import type { ComponentType } from "react";
import {
  Activity,
  Bot,
  Building2,
  ChartNoAxesCombined,
  ClipboardCheck,
  ClipboardList,
  LayoutDashboard,
} from "lucide-react";
import type { NavItem } from "@/layouts/navigation";
import PanoramaPage from "@/features/panorama/PanoramaPage";
import ReceitaPage from "@/features/receita/ReceitaPage";
import UC360Page from "@/features/uc360/UC360Page";
import InspecoesPage from "@/features/inspecoes/InspecoesPage";
import OrdensPage from "@/features/ordens/OrdensPage";
import OperacaoPage from "@/features/operacao/OperacaoPage";
import AssistentePage from "@/features/assistente/AssistentePage";

type AppRoute = NavItem & { Component: ComponentType };

export const routes = [
  {
    path: "/panorama",
    label: "Panorama",
    subtitle: "Visão executiva e KPIs gerais",
    requirementId: "WEB-01",
    icon: LayoutDashboard,
    contentHeading: true,
    Component: PanoramaPage,
  },
  {
    path: "/receita",
    label: "Receita",
    subtitle: "Decomposição preço x volume",
    requirementId: "WEB-02",
    icon: ChartNoAxesCombined,
    Component: ReceitaPage,
  },
  {
    path: "/uc-360",
    label: "UC 360",
    subtitle: "Visão 360 da unidade consumidora",
    requirementId: "WEB-03",
    icon: Building2,
    Component: UC360Page,
  },
  {
    path: "/inspecoes",
    label: "Inspeções",
    subtitle: "Fila de perdas e priorização",
    requirementId: "WEB-04",
    icon: ClipboardCheck,
    Component: InspecoesPage,
  },
  {
    path: "/ordens",
    label: "Ordens",
    subtitle: "Ciclo de vida de ordens de serviço",
    requirementId: "WEB-05",
    icon: ClipboardList,
    Component: OrdensPage,
  },
  {
    path: "/operacao",
    label: "Operação",
    subtitle: "Continuidade DEC/FEC por alimentador",
    requirementId: "WEB-06",
    icon: Activity,
    Component: OperacaoPage,
  },
  {
    path: "/assistente",
    label: "Assistente",
    subtitle: "Assistente inteligente em linguagem natural",
    requirementId: "IA-05",
    icon: Bot,
    Component: AssistentePage,
  },
] satisfies AppRoute[];
