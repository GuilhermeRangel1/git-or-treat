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
    title: "Entenda a receita.",
    subtitle:
      "Compare períodos, investigue territórios e separe preço efetivo de volume faturado.",
    requirementId: "WEB-02",
    icon: ChartNoAxesCombined,
    Component: ReceitaPage,
  },
  {
    path: "/uc-360",
    label: "UC 360",
    title: "Cada unidade tem uma história.",
    section: "Atendimento",
    subtitle: "Localize a UC pelo número informado no atendimento.",
    requirementId: "WEB-03",
    icon: Building2,
    Component: UC360Page,
  },
  {
    path: "/inspecoes",
    contentHeading: true,
    label: "Inspeções",
    title: "Priorize a próxima inspeção.",
    section: "Perdas",
    subtitle:
      "Uma fila explicável para orientar a investigação de perdas. Suspeita não é fraude comprovada.",
    requirementId: "WEB-04",
    icon: ClipboardCheck,
    Component: InspecoesPage,
  },
  {
    path: "/ordens",
    label: "Ordens",
    title: "Acompanhe o trabalho de campo.",
    subtitle:
      "Criação, atualização, resultado e cancelamento no mesmo contexto operacional.",
    requirementId: "WEB-05",
    icon: ClipboardList,
    Component: OrdensPage,
  },
  {
    path: "/operacao",
    label: "Operação",
    title: "Continuidade, onde importa.",
    subtitle:
      "Compare alimentadores e investigue os registros que sustentam os indicadores internos.",
    requirementId: "WEB-06",
    icon: Activity,
    Component: OperacaoPage,
  },
  {
    path: "/assistente",
    label: "Assistente",
    contentHeading: true,
    layout: "conversation",
    requirementId: "IA-05",
    icon: Bot,
    Component: AssistentePage,
  },
] satisfies AppRoute[];
