export type NavItem = {
  path: string;
  label: string;
  description?: string;
  requirementId?: string;
};

export const ITEMS: NavItem[] = [
  { path: "/panorama", label: "Panorama", description: "Visão executiva e KPIs gerais", requirementId: "WEB-01" },
  { path: "/receita", label: "Receita", description: "Decomposição preço x volume", requirementId: "WEB-02" },
  { path: "/uc-360", label: "UC 360", description: "Visão 360 da unidade consumidora", requirementId: "WEB-03" },
  { path: "/inspecoes", label: "Inspeções", description: "Fila de perdas e priorização", requirementId: "WEB-04" },
  { path: "/ordens", label: "Ordens", description: "Ciclo de vida de ordens de serviço", requirementId: "WEB-05" },
  { path: "/operacao", label: "Operação", description: "Continuidade DEC/FEC por alimentador", requirementId: "WEB-06" },
  { path: "/assistente", label: "Assistente", description: "Assistente inteligente em linguagem natural", requirementId: "IA-04" },
];
