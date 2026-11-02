import { useRef, useState } from "react";
import Button from "../../shared/ui/Button";
import Modal from "../../shared/ui/Modal";
import type { KpiMetric, PanoramaData } from "../../shared/analytics/types";
import { formatCompetenciaLabel } from "../../shared/analytics/syntheticData";

const primaryMetrics = [
  ["receitaFaturada", "Valor faturado"],
  ["energiaConsumida", "Consumo apurado"],
  ["ucsAtivas", "UCs cadastradas no lote"],
  ["ucsFaturadasNoMes", "UCs faturadas no mês"],
] as const;
const additionalMetrics = [
  ["precoMedioEfetivo", "Preço observado"],
  ["continuidadeDec", "DEC"],
  ["continuidadeFec", "FEC"],
] as const;

function formatValue(metric: KpiMetric) {
  if (metric.valorAtual == null) return "Indisponível";
  if (metric.unidade === "R$")
    return new Intl.NumberFormat("pt-BR", {
      style: "currency",
      currency: "BRL",
      maximumFractionDigits: 2,
    }).format(metric.valorAtual);
  return `${metric.valorAtual.toLocaleString("pt-BR", { maximumFractionDigits: 2 })} ${metric.unidade}`;
}

function formatTimestamp(value: string) {
  const date = new Date(value);
  return Number.isNaN(date.valueOf())
    ? value
    : new Intl.DateTimeFormat("pt-BR", {
        dateStyle: "short",
        timeStyle: "short",
      }).format(date);
}

export default function PanoramaFoundations({ data }: { data: PanoramaData }) {
  const [open, setOpen] = useState(false);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const isGold = data.origem?.kind === "gold";
  const metricEntries = [...primaryMetrics, ...additionalMetrics].flatMap(
    ([key, title]) => {
      const metric = data.metricas[key];
      return metric ? [{ key, title, metric }] : [];
    },
  );
  return (
    <>
      <Button
        ref={triggerRef}
        variant="ghost"
        size="md"
        className="px-1 underline underline-offset-4"
        onClick={() => setOpen(true)}
      >
        Ver fundamentos
      </Button>
      <Modal
        open={open}
        onClose={() => setOpen(false)}
        triggerRef={triggerRef}
        title="Fundamentos do Panorama"
        description="Definições, limites e origem dos indicadores deste recorte."
        closeLabel="Fechar fundamentos"
        size="lg"
        header="sticky"
      >
        <div className="max-h-[min(75vh,720px)] space-y-6 overflow-y-auto p-5 sm:p-6">
          <section aria-labelledby="foundation-primary-title">
            <h2
              id="foundation-primary-title"
              className="mb-3 text-base font-semibold"
            >
              Indicadores principais
            </h2>
            <div className="grid gap-3 sm:grid-cols-2">
              {primaryMetrics.flatMap(([key, title]) => {
                const metric = data.metricas[key];
                if (!metric) return [];
                const cadence =
                  key === "ucsAtivas" && isGold
                    ? "Fotografia do lote · todos os status"
                    : `Competência ${formatCompetenciaLabel(data.filtros.periodo)}`;
                const displayTitle =
                  key === "ucsAtivas" && !isGold ? "Base de UCs" : title;
                return [
                  <article
                    key={key}
                    className="rounded-xl border border-border bg-surface p-4"
                  >
                    <h3 className="text-sm font-medium text-muted">
                      {displayTitle}
                    </h3>
                    <p className="mt-1 font-heading text-xl font-semibold text-content">
                      {formatValue(metric)}
                    </p>
                    <p className="mt-1 text-xs text-muted">
                      {cadence} ·{" "}
                      {data.filtros.municipio === "todos"
                        ? "Todos os municípios"
                        : data.filtros.municipio}{" "}
                      ·{" "}
                      {data.filtros.classe === "todas"
                        ? "Todas as classes"
                        : data.filtros.classe}
                    </p>
                    {key !== "ucsAtivas" &&
                      data.filtros.comparacao !== "nenhuma" &&
                      metric.valorAnterior != null &&
                      metric.variacaoPercentual != null && (
                        <p className="mt-2 text-xs text-muted">
                          {comparisonLabel(data.filtros.comparacao)}:{" "}
                          {metric.variacaoPercentual > 0 ? "+" : ""}
                          {metric.variacaoPercentual.toLocaleString("pt-BR", {
                            maximumFractionDigits: 2,
                          })}
                          %
                          {metric.statusComparacao === "partial" && isGold
                            ? " · observado; fechamento mensal não declarado."
                            : ""}
                        </p>
                      )}
                    {key !== "ucsAtivas" &&
                      data.filtros.comparacao !== "nenhuma" &&
                      metric.valorAnterior == null && (
                        <p className="mt-2 text-xs text-muted">
                          {metric.limitacoesComparacao?.join(" ") ||
                            "Sem valor disponível na competência de referência."}
                        </p>
                      )}
                    {metric.baseZero && metric.valorAnterior != null && (
                      <p className="mt-2 text-xs text-muted">
                        Base anterior zero · variação percentual indisponível.
                      </p>
                    )}
                    <details className="mt-3 border-t border-divider pt-3 text-xs text-muted">
                      <summary className="min-h-9 cursor-pointer py-2 font-medium text-content">
                        Definição e fórmula
                      </summary>
                      <dl className="space-y-2">
                        <div>
                          <dt className="font-medium text-content">
                            Definição
                          </dt>
                          <dd>{metric.definicao}</dd>
                        </div>
                        <div>
                          <dt className="font-medium text-content">Fórmula</dt>
                          <dd className="break-words font-mono">
                            {metric.formula}
                          </dd>
                        </div>
                        <div>
                          <dt className="font-medium text-content">Unidade</dt>
                          <dd>{metric.unidade}</dd>
                        </div>
                        {metric.limitacoes?.map((limitation) => (
                          <div key={limitation}>
                            <dt className="font-medium text-content">Limite</dt>
                            <dd>{limitation}</dd>
                          </div>
                        ))}
                        {isGold && key === "receitaFaturada" && (
                          <div>
                            <dt className="font-medium text-content">
                              Base de cálculo
                            </dt>
                            <dd>
                              Soma apenas os pares UC/mês comparáveis; não
                              representa o total financeiro irrestrito.
                            </dd>
                          </div>
                        )}
                        {isGold && key === "energiaConsumida" && (
                          <div>
                            <dt className="font-medium text-content">
                              Distinção de medida
                            </dt>
                            <dd>
                              Consumo medido não comprova energia faturada; essa
                              grandeza não está disponível na publicação.
                            </dd>
                          </div>
                        )}
                      </dl>
                    </details>
                  </article>,
                ];
              })}
            </div>
          </section>

          <section aria-labelledby="foundation-additional-title">
            <h2
              id="foundation-additional-title"
              className="mb-3 text-base font-semibold"
            >
              Fundamentos adicionais
            </h2>
            <div className="divide-y divide-divider rounded-xl border border-border px-4">
              {metricEntries
                .filter(({ key }) =>
                  additionalMetrics.some(([candidate]) => candidate === key),
                )
                .map(({ key, title, metric }) => (
                  <details key={key} className="py-3 text-sm">
                    <summary className="min-h-9 cursor-pointer font-medium text-content">
                      {title} · {formatValue(metric)}
                    </summary>
                    <p className="mt-2 text-xs text-muted">
                      {metric.definicao} Unidade: {metric.unidade}. Fórmula:{" "}
                      <span className="font-mono">{metric.formula}</span>
                    </p>
                    {metric.limitacoes?.length ? (
                      <p className="mt-2 text-xs text-muted">
                        {metric.limitacoes.join(" ")}
                      </p>
                    ) : null}
                  </details>
                ))}
            </div>
          </section>

          <details className="rounded-xl border border-border bg-surface p-4 text-sm">
            <summary className="min-h-9 cursor-pointer font-semibold">
              Atualização e período
            </summary>
            <dl className="mt-2 grid gap-2 text-xs text-muted sm:grid-cols-2">
              <div>
                <dt className="inline font-medium text-content">
                  Atualizado em:{" "}
                </dt>
                <dd className="inline">
                  {formatTimestamp(data.dataAtualizacao)}
                </dd>
              </div>
              <div>
                <dt className="inline font-medium text-content">
                  Competência:{" "}
                </dt>
                <dd className="inline">
                  {formatCompetenciaLabel(data.filtros.periodo)}
                  {isGold && !data.fechamentoMensalDeclarado
                    ? " · fechamento mensal não informado"
                    : ""}
                </dd>
              </div>
            </dl>
          </details>
        </div>
      </Modal>
    </>
  );
}

function comparisonLabel(value: PanoramaData["filtros"]["comparacao"]) {
  return value === "anterior"
    ? "Mês anterior"
    : value === "ano_anterior"
      ? "Mesmo mês do ano anterior"
      : "Sem comparação";
}
