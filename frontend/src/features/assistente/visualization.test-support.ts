export const points = [100, 120, 110].map((value, i) => ({
  observation_id: `row_${i + 1}`,
  label: `2026-0${i + 6}`,
  value,
}));
export const visualResponse = {
  contract_version: "v1",
  status: "answered",
  answer: "Resultados da receita no período solicitado.",
  evidence: [
    {
      source: "gold.local",
      description: "Agregados autorizados.",
      is_demo: false,
    },
  ],
  limitations: [],
  analysis_context: {
    batch_reference:
      "gold-csv-v2:GOLD_20261031T020143Z_fd69c375:82ff37de-0266-421c-8674-9ba4e191b20b",
    metric: "billing.revenue",
    metric_label: "Receita faturada",
    unit: "R$",
    period: "2026-06-01 a 2026-08-31",
    filters: { "geography.municipality": "Recife" },
    filter_labels: { "geography.municipality": "Município" },
  },
  visualization: {
    contract_version: "v1",
    kind: "line",
    metric: "billing.revenue",
    title: "Receita faturada",
    unit: "R$",
    precision: 2,
    dimension_ids: ["geography.municipality"],
    period: "2026-06-01 a 2026-08-31",
    category_label: "Período",
    note: "3 observações autorizadas.",
    points,
    plot_points: points,
  },
};
