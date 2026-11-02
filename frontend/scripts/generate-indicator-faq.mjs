import { readFileSync, writeFileSync } from "node:fs";
import { createHash } from "node:crypto";

// Public conceptual definitions only: never publish physical mappings or grants.
const catalogUrl = new URL(
  "../../backend/app/catalogs/gold_v2.json",
  import.meta.url,
);
const target = new URL(
  "../src/shared/help/indicatorFaq.generated.json",
  import.meta.url,
);
const catalog = JSON.parse(readFileSync(catalogUrl, "utf8"));
const topics = [
  [
    "revenue",
    "Receita faturada é o valor pago?",
    ["receita", "faturamento", "pago", "fatura"],
    ["billing.revenue"],
    ["assistente", "panorama", "receita", "uc360"],
  ],
  [
    "consumption",
    "Consumo medido é energia faturada?",
    ["energia", "consumo", "leitura", "kwh"],
    ["energy.consumption"],
    ["assistente", "panorama", "receita", "uc360"],
  ],
  [
    "price",
    "Preço médio observado é a tarifa homologada?",
    ["preco", "tarifa", "comparavel"],
    ["billing.effective_tariff"],
    ["assistente", "panorama", "receita"],
  ],
  [
    "ticket",
    "O que significa ticket médio?",
    ["ticket", "media", "faturada"],
    ["billing.average_ticket"],
    ["assistente", "panorama", "receita"],
  ],
  [
    "continuity",
    "Qual a diferença entre DEC e FEC?",
    ["dec", "fec", "continuidade", "duracao", "frequencia"],
    [
      "network.equivalent_interruption_duration",
      "network.equivalent_interruption_frequency",
    ],
    ["assistente", "panorama", "operacao"],
  ],
  [
    "events",
    "Interrupções registradas são o mesmo que FEC?",
    ["interrupcao", "interrupcoes", "ocorrencia", "evento"],
    ["network.interruption_events"],
    ["assistente", "operacao"],
  ],
  [
    "attendance",
    "Chamados acumulados representam um mês?",
    ["chamados", "atendimento", "acumulado", "historico"],
    ["service.accumulated_attendance", "service.attendance"],
    ["assistente", "panorama", "uc360"],
  ],
  [
    "decomposition",
    "A decomposição da receita explica a causa da variação?",
    ["decomposicao", "variacao", "causa", "volume"],
    ["billing.price_volume"],
    ["assistente", "receita"],
  ],
  [
    "gd",
    "Geração distribuída comprova a causa de uma queda de consumo?",
    ["gd", "geracao", "solar", "queda"],
    ["energy.gd_consumption_drop"],
    ["assistente", "uc360"],
  ],
];
const entries = topics.map(([id, question, keywords, metricIds, screens]) => ({
  id,
  question,
  keywords,
  screens,
  status: "active",
  validFrom: "2026-11-02",
  validUntil: null,
  audience: "Pessoas usuárias do portal interno",
  owner: "Dados/negócio (definição); Frontend/GenAI (publicação)",
  definitions: metricIds.map((metricId) => {
    const metric = catalog.metrics.find((item) => item.metric_id === metricId);
    if (!metric?.definition || !metric.label)
      throw new Error(`Definição ausente: ${metricId}`);
    return { metricId, label: metric.label, text: metric.definition };
  }),
}));
const content = {
  version: createHash("sha256")
    .update(JSON.stringify(entries))
    .digest("hex")
    .slice(0, 12),
  catalogVersion: catalog.mapping_version,
  source: "Dicionário de indicadores da distribuidora",
  entries,
};
const serialized = JSON.stringify(content, null, 2) + "\n";
if (process.argv.includes("--check")) {
  if (
    JSON.stringify(JSON.parse(readFileSync(target, "utf8"))) !==
    JSON.stringify(content)
  )
    throw new Error(
      "FAQ desatualizado: execute npm run generate:faq e revise as definições.",
    );
  console.log("FAQ confere com as definições do catálogo Gold v2.");
} else writeFileSync(target, serialized);
