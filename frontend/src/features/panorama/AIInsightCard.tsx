import { useEffect, useRef, useState } from "react";
import {
  ArrowRight,
  Check,
  ChevronDown,
  Info,
  Sparkles,
  X,
} from "lucide-react";
import Button from "../../shared/ui/Button";
import type {
  PanoramaData,
  PanoramaFilters,
} from "../../shared/analytics/types";
import { PanoramaInsightApiError } from "./insightApi";
import type {
  PanoramaInsightAnalysis,
  PanoramaInsightContribution,
} from "./insightContract";
import type { usePanoramaInsight } from "./usePanoramaInsight";

type InsightQuery = ReturnType<typeof usePanoramaInsight>;

interface AIInsightCardProps {
  filters: PanoramaFilters;
  data: PanoramaData;
  query: InsightQuery;
  onRefreshIndicators: () => void;
}

function periodLabel(period: string) {
  const [year, month] = period.split("-").map(Number);
  const months = [
    "Jan",
    "Fev",
    "Mar",
    "Abr",
    "Mai",
    "Jun",
    "Jul",
    "Ago",
    "Set",
    "Out",
    "Nov",
    "Dez",
  ];
  return `${months[month - 1]}/${String(year).slice(-2)}`;
}

function comparisonPeriod(filters: PanoramaFilters) {
  if (filters.comparacao === "nenhuma") return null;
  const [year, month] = filters.periodo.split("-").map(Number);
  const date = new Date(0);
  date.setUTCFullYear(year, month - 1, 1);
  if (filters.comparacao === "anterior")
    date.setUTCMonth(date.getUTCMonth() - 1);
  else date.setUTCFullYear(date.getUTCFullYear() - 1);
  return `${String(date.getUTCFullYear()).padStart(4, "0")}-${String(date.getUTCMonth() + 1).padStart(2, "0")}`;
}

function comparisonLabel(filters: PanoramaFilters) {
  const period = comparisonPeriod(filters);
  return period ? periodLabel(period) : "Sem comparação";
}

function filterLabel(value: string, allLabel: string) {
  if (value === "todos" || value === "todas") return allLabel;
  return value;
}

function formatValue(value: number, unit: string) {
  return `${new Intl.NumberFormat("pt-BR", { maximumFractionDigits: 2 }).format(value)} ${unit}`;
}

function formatPercentage(value: number | null) {
  if (value === null) return null;
  return `${new Intl.NumberFormat("pt-BR", { maximumFractionDigits: 1 }).format(Math.abs(value))}%`;
}

function describeTrend(
  analysis: PanoramaInsightAnalysis,
  metric: PanoramaData["metricas"]["energiaFaturada"],
  filters: PanoramaFilters,
) {
  const current = periodLabel(filters.periodo);
  const previous = comparisonLabel(filters);
  const percentage = formatPercentage(analysis.variacaoPercentual);

  if (analysis.direcao === "indisponivel")
    return "Não há comparação válida para identificar uma tendência neste recorte.";
  if (analysis.direcao === "estavel")
    return `${metric.nome} ficou estável de ${previous} para ${current}.`;

  const verb = analysis.direcao === "queda" ? "caiu" : "aumentou";
  const change =
    percentage ??
    formatValue(Math.abs(metric.variacaoAbsoluta ?? 0), metric.unidade);
  return `${metric.nome} ${verb} ${change} de ${previous} para ${current}.`;
}

function describeContribution(
  contribution: PanoramaInsightContribution,
  analysis: PanoramaInsightAnalysis,
  unit: string,
) {
  const dimension = contribution.dimension === "classe" ? "da classe" : "de";
  const movement = analysis.direcao === "queda" ? "queda" : "alta";
  const share = formatPercentage(contribution.participacaoPercentual);
  return `A maior ${movement} veio ${dimension} ${contribution.segmento}: ${formatValue(Math.abs(contribution.variacaoAbsoluta), unit)}${share ? ` (${share} da ${analysis.direcao === "queda" ? "redução" : "alta"})` : ""}.`;
}

function describeOffset(
  contribution: PanoramaInsightContribution,
  analysis: PanoramaInsightAnalysis,
  unit: string,
) {
  const dimension = contribution.dimension === "classe" ? "na classe" : "em";
  const movement = analysis.direcao === "queda" ? "A alta" : "A queda";
  return `${movement} ${dimension} ${contribution.segmento} (${formatSignedValue(contribution.variacaoAbsoluta, unit)}) compensou parte da variação total.`;
}

function formatSignedValue(value: number, unit: string) {
  const sign = value > 0 ? "+" : value < 0 ? "−" : "";
  return `${sign}${formatValue(Math.abs(value), unit)}`;
}

function investigationSuggestion(
  analysis: PanoramaInsightAnalysis,
  filters: PanoramaFilters,
) {
  const contribution = analysis.principalContribuicao;
  if (analysis.direcao === "indisponivel")
    return "Selecione um período comparável para encontrar mudanças no indicador.";
  if (analysis.direcao === "estavel")
    return "Compare os recortes por município e classe; o total pode ocultar movimentos diferentes entre grupos.";
  if (contribution?.dimension === "classe")
    return `Acompanhe a classe ${contribution.segmento} em outras competências para verificar se o movimento se repete. Os dados não indicam a causa.`;
  if (contribution?.dimension === "municipio")
    return `Abra ${contribution.segmento} por classe para localizar onde o movimento se concentra. Os dados não indicam a causa.`;
  if (filters.municipio !== "todos" && filters.classe !== "todas")
    return "Abra o recorte por município ou classe para localizar onde o movimento se concentra. Os dados não indicam a causa.";
  return "Compare os grupos deste recorte para localizar onde o movimento se concentra. Os dados não indicam a causa.";
}

function compactNextStep(analysis: PanoramaInsightAnalysis) {
  const contribution = analysis.principalContribuicao;
  if (analysis.direcao === "indisponivel")
    return "escolha um período comparável.";
  if (analysis.direcao === "estavel")
    return "compare município e classe neste recorte.";
  if (contribution?.dimension === "classe")
    return `acompanhe ${contribution.segmento} em outras competências.`;
  if (contribution?.dimension === "municipio")
    return `explore ${contribution.segmento} por classe.`;
  return "compare os grupos deste recorte.";
}

function statusLabel(status: string) {
  switch (status) {
    case "needs_clarification":
      return "Precisa de esclarecimento";
    case "refused":
      return "Solicitação recusada";
    case "no_evidence":
      return "Sem evidência suficiente";
    case "recoverable_error":
      return "Falha temporária";
    default:
      return "Interpretação automatizada";
  }
}

export default function AIInsightCard({
  filters,
  data,
  query,
  onRefreshIndicators,
}: AIInsightCardProps) {
  const [detailsOpen, setDetailsOpen] = useState(false);
  const [showFoundation, setShowFoundation] = useState(false);
  const detailsDialogRef = useRef<HTMLDialogElement>(null);
  const detailsTriggerRef = useRef<HTMLButtonElement>(null);
  const restoreDetailsFocusRef = useRef(false);
  const metric = data.metricas.energiaFaturada;
  // A failed refetch can leave TanStack Query's previous response in `data`.
  // Never present that cached interpretation as current after an error.
  const response = query.isError ? undefined : query.data;
  const insight = response?.insight;
  const analysis = response?.analysis;
  const pending =
    data.totalRegistros > 0 && (query.isPending || query.isFetching);
  const apiError =
    query.error instanceof PanoramaInsightApiError ? query.error : null;
  const isStale = apiError?.code === "invalid_context";
  const canRetryResponse =
    insight?.status === "recoverable_error" &&
    insight.error?.retryable === true;
  const limitations = [
    ...(response?.source.limitacoes ?? []),
    ...(insight?.limitations ?? []),
  ];
  if (data.periodoIncompleto) {
    limitations.push(
      `A competência ${filters.periodo} está em aberto; a comparação pode não estar disponível.`,
    );
  }
  limitations.push(
    "Os números são fictícios e servem apenas para demonstração; não representam dados operacionais reais.",
  );
  const uniqueLimitations = [...new Set(limitations)];

  let stateMessage = "";
  if (data.totalRegistros === 0) {
    stateMessage = "Não há evidência para interpretar este recorte.";
  } else if (pending) {
    stateMessage = "Gerando uma interpretação para o recorte atual.";
  } else if (query.isError) {
    stateMessage = isStale
      ? "O lote mudou desde que os indicadores foram carregados. Atualize o Panorama para sincronizar o contexto."
      : "Não foi possível gerar a interpretação agora. Os indicadores continuam disponíveis para consulta.";
  } else if (insight && insight.status !== "answered") {
    stateMessage =
      insight.message ?? "Não foi possível interpretar este recorte.";
  }

  useEffect(() => {
    const dialog = detailsDialogRef.current;
    if (!dialog) return;
    if (detailsOpen && !dialog.open) {
      if (typeof dialog.showModal === "function") dialog.showModal();
      else dialog.setAttribute("open", "");
    }
    if (!detailsOpen && dialog.open) {
      if (typeof dialog.close === "function") dialog.close();
      else dialog.removeAttribute("open");
    }
  }, [detailsOpen]);

  useEffect(() => {
    if (!detailsOpen && restoreDetailsFocusRef.current) {
      detailsTriggerRef.current?.focus();
      restoreDetailsFocusRef.current = false;
    }
  }, [detailsOpen]);

  function closeDetails() {
    restoreDetailsFocusRef.current = true;
    setDetailsOpen(false);
  }

  function renderAnalysis() {
    if (insight?.status !== "answered") return null;
    return (
      <div className="space-y-3 text-sm leading-6 text-content">
        <p className="font-medium">
          {analysis
            ? describeTrend(analysis, metric, filters)
            : "Não há análise calculada para este recorte."}
        </p>
        {analysis?.principalContribuicao && (
          <p>
            {describeContribution(
              analysis.principalContribuicao,
              analysis,
              metric.unidade,
            )}
          </p>
        )}
        {analysis?.compensacao && (
          <p>
            {describeOffset(analysis.compensacao, analysis, metric.unidade)}
          </p>
        )}
      </div>
    );
  }

  return (
    <section
      aria-label="Insight contextual do Panorama"
      className={`flex w-full min-w-0 flex-col gap-4 rounded-xl border p-4 shadow-sm ${data.totalRegistros === 0 || query.isError || (insight && insight.status !== "answered") ? "border-[var(--status-warning)] bg-[var(--accent-goiaba-subtle)]" : "border-border bg-[var(--accent-pistache-subtle)]"}`}
    >
      <div className="space-y-3">
        <div className="flex items-center justify-between gap-3">
          <div className="flex min-w-0 items-center gap-2.5">
            <span className="grid size-9 shrink-0 place-items-center rounded-lg bg-surface text-[var(--accent-pistache)]">
              <Sparkles aria-hidden="true" className="size-4" />
            </span>
            <div className="min-w-0">
              <p className="font-heading text-sm font-semibold text-content">
                Insight do Panorama
              </p>
              <p className="text-xs text-muted">
                Análise assistida por IA · dados demonstrativos
              </p>
            </div>
          </div>
          <span className="rounded-full border border-[var(--line)] bg-surface px-2.5 py-1 text-[11px] font-semibold tracking-wide text-content">
            IA
          </span>
        </div>

        <div className="rounded-lg border border-[var(--line)] bg-surface/70 p-3">
          {data.totalRegistros === 0 ? (
            <p className="text-sm leading-6 text-muted">
              Não há observações de dados para este recorte.
            </p>
          ) : (
            <>
              <div className="flex items-center gap-1.5 text-xs font-semibold text-muted">
                <Check
                  aria-hidden="true"
                  className="size-3.5 text-[var(--accent-pistache)]"
                />
                Dado observado no Panorama
              </div>
              <p className="mt-1.5 font-heading text-xl font-semibold text-content">
                {formatValue(metric.valorAtual, metric.unidade)}
              </p>
              <p className="mt-0.5 text-xs text-muted">
                {metric.nome} · {periodLabel(filters.periodo)}
              </p>
              <p className="mt-1 text-xs text-muted">
                {metric.valorAnterior == null
                  ? "Sem valor comparável disponível"
                  : `${comparisonLabel(filters)}: ${formatValue(metric.valorAnterior, metric.unidade)}${metric.variacaoAbsoluta == null ? "" : ` · variação ${formatValue(metric.variacaoAbsoluta, metric.unidade)}`}`}
              </p>
            </>
          )}
        </div>
      </div>

      <div>
        <p className="text-xs font-semibold uppercase tracking-wide text-muted">
          Leitura do recorte
        </p>
        {pending ? (
          <p
            role="status"
            aria-live="polite"
            className="mt-2 text-sm leading-6 text-content"
          >
            <span className="mr-2 inline-block size-3 animate-spin rounded-full border-2 border-[var(--line)] border-t-[var(--accent-pistache)] align-[-2px]" />
            Recorte alterado · atualizando a interpretação.
          </p>
        ) : insight?.status === "answered" ? (
          <div className="mt-2 space-y-1.5 text-sm leading-5 text-content">
            <p className="font-medium">
              {analysis
                ? describeTrend(analysis, metric, filters)
                : "Não há análise calculada para este recorte."}
            </p>
            {analysis?.principalContribuicao && (
              <p className="text-xs leading-5 text-muted">
                Principal movimento: {analysis.principalContribuicao.segmento} ·{" "}
                {formatSignedValue(
                  analysis.principalContribuicao.variacaoAbsoluta,
                  metric.unidade,
                )}
                .
              </p>
            )}
            {analysis && (
              <p className="mt-3 border-l-2 border-[var(--accent-pistache)] pl-3 text-xs leading-5 text-muted">
                <span className="font-semibold text-content">
                  Próximo passo:
                </span>{" "}
                {compactNextStep(analysis)}
              </p>
            )}
            {insight.hypothesis && (
              <div className="mt-3 border-l-2 border-[var(--accent-goiaba)] pl-3">
                <p className="text-[11px] font-semibold uppercase tracking-wide text-muted">
                  Hipótese para investigar
                </p>
                <p className="mt-1 line-clamp-2 text-xs leading-5 text-muted">
                  {insight.hypothesis}
                </p>
                <p className="mt-1 text-[11px] leading-4 text-muted">
                  Sugestão de investigação; não comprova causa.
                </p>
              </div>
            )}
          </div>
        ) : (
          <div className="mt-2">
            {data.totalRegistros === 0 && (
              <p className="mb-1 text-xs font-semibold text-[var(--status-warning)]">
                Sem evidência suficiente
              </p>
            )}
            {!isStale && query.isError && (
              <p className="mb-1 text-xs font-semibold text-[var(--status-danger)]">
                O insight não está disponível agora.
              </p>
            )}
            {insight && (
              <p className="mb-1 text-xs font-semibold text-[var(--status-warning)]">
                {statusLabel(insight.status)}
              </p>
            )}
            <p
              role="status"
              aria-live="polite"
              className="text-sm leading-6 text-content"
            >
              {stateMessage}
            </p>
          </div>
        )}
        {((query.isError && (apiError?.retryable || isStale)) ||
          canRetryResponse) && (
          <button
            type="button"
            onClick={() =>
              isStale ? onRefreshIndicators() : void query.refetch()
            }
            className="mt-3 w-fit rounded-md px-2 py-1 text-sm font-semibold text-brand underline-offset-4 hover:underline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand"
          >
            {isStale ? "Atualizar indicadores" : "Tentar novamente"}
          </button>
        )}
      </div>

      <div className="mt-auto border-t border-[var(--line)] pt-3">
        <Button
          ref={detailsTriggerRef}
          variant="primary"
          size="lg"
          aria-haspopup="dialog"
          onClick={() => setDetailsOpen(true)}
          rightIcon={<ArrowRight aria-hidden="true" className="size-4" />}
          className="w-full font-semibold"
        >
          Ver análise detalhada
        </Button>
      </div>

      {detailsOpen && (
        <dialog
          ref={detailsDialogRef}
          id="panorama-insight-details"
          aria-labelledby="panorama-insight-title"
          aria-modal="true"
          className="fixed inset-y-0 right-0 m-0 h-dvh w-[min(460px,calc(100vw-1rem))] max-h-none max-w-none overflow-hidden border-l border-border bg-surface p-0 text-content shadow-2xl backdrop:bg-black/45"
          style={{
            position: "fixed",
            top: 0,
            right: 0,
            bottom: 0,
            left: "auto",
            margin: 0,
          }}
          onCancel={(event) => {
            event.preventDefault();
            closeDetails();
          }}
          onClose={closeDetails}
          onClick={(event) => {
            if (event.target === detailsDialogRef.current) closeDetails();
          }}
        >
          <div className="flex h-full min-h-0 flex-col">
            <header className="flex shrink-0 items-start justify-between gap-4 border-b border-[var(--line)] p-5 sm:p-6">
              <div className="flex items-start gap-3">
                <span className="grid size-11 shrink-0 place-items-center rounded-full border border-[var(--line)] bg-surface text-[var(--accent-pistache)]">
                  <Sparkles aria-hidden="true" className="size-5" />
                </span>
                <div>
                  <h2
                    id="panorama-insight-title"
                    className="font-heading text-xl font-semibold"
                  >
                    Insight
                  </h2>
                  <p className="mt-1 text-sm text-muted">
                    Análise do recorte selecionado.
                  </p>
                </div>
              </div>
              <button
                type="button"
                aria-label="Fechar análise detalhada"
                className="grid size-10 shrink-0 place-items-center rounded-lg border border-control hover:bg-surface-hover focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand"
                onClick={closeDetails}
              >
                <X aria-hidden="true" className="size-4" />
              </button>
            </header>

            <div className="min-h-0 flex-1 space-y-5 overflow-y-auto overscroll-contain p-5 sm:p-6">
              <section
                aria-label="Dado observado"
                className="rounded-xl bg-[var(--accent-pistache-subtle)] p-4"
              >
                {data.totalRegistros === 0 ? (
                  <p className="text-sm leading-6 text-muted">
                    Não há observações de dados para este recorte.
                  </p>
                ) : (
                  <>
                    <div className="flex items-center gap-2 text-xs font-semibold text-muted">
                      <Check
                        aria-hidden="true"
                        className="size-3.5 text-[var(--accent-pistache)]"
                      />
                      Dado observado no Panorama
                    </div>
                    <p className="mt-1.5 font-heading text-xl font-semibold">
                      {formatValue(metric.valorAtual, metric.unidade)}
                    </p>
                    <p className="mt-0.5 text-xs text-muted">
                      {metric.nome} · {periodLabel(filters.periodo)}
                    </p>
                    <p className="mt-1 text-xs text-muted">
                      {metric.valorAnterior == null
                        ? "Sem valor comparável disponível"
                        : `${comparisonLabel(filters)}: ${formatValue(metric.valorAnterior, metric.unidade)}${metric.variacaoAbsoluta == null ? "" : ` · variação ${formatSignedValue(metric.variacaoAbsoluta, metric.unidade)}`}`}
                    </p>
                  </>
                )}
              </section>

              <section aria-labelledby="panorama-insight-points-title">
                <h3
                  id="panorama-insight-points-title"
                  className="font-heading text-base font-semibold"
                >
                  Principais pontos
                </h3>
                <div className="mt-3">
                  {pending ? (
                    <p role="status" className="text-sm leading-6 text-muted">
                      Atualizando a interpretação para o recorte atual.
                    </p>
                  ) : insight?.status === "answered" ? (
                    renderAnalysis()
                  ) : (
                    <div>
                      {insight && (
                        <p className="mb-1 text-xs font-semibold text-[var(--status-warning)]">
                          {statusLabel(insight.status)}
                        </p>
                      )}
                      <p role="status" className="text-sm leading-6">
                        {stateMessage}
                      </p>
                      {((query.isError && (apiError?.retryable || isStale)) ||
                        canRetryResponse) && (
                        <button
                          type="button"
                          onClick={() =>
                            isStale
                              ? onRefreshIndicators()
                              : void query.refetch()
                          }
                          className="mt-3 w-fit rounded-md px-2 py-1 text-sm font-semibold text-brand underline-offset-4 hover:underline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand"
                        >
                          {isStale
                            ? "Atualizar indicadores"
                            : "Tentar novamente"}
                        </button>
                      )}
                    </div>
                  )}
                </div>
              </section>

              {insight?.status === "answered" && insight.hypothesis && (
                <section
                  aria-labelledby="panorama-insight-hypothesis-title"
                  className="rounded-xl border border-[var(--line)] bg-surface p-4"
                >
                  <h3
                    id="panorama-insight-hypothesis-title"
                    className="font-heading text-sm font-semibold"
                  >
                    Hipótese para investigar
                  </h3>
                  <p className="mt-2 text-sm leading-6 text-content">
                    {insight.hypothesis}
                  </p>
                  <p className="mt-2 text-xs leading-5 text-muted">
                    Interpretação gerada pela IA; os dados observados não
                    comprovam uma causa.
                  </p>
                </section>
              )}

              {insight?.status === "answered" && (
                <section className="rounded-xl border border-[var(--line)] bg-[var(--accent-pistache-subtle)]/60 p-4">
                  <h3 className="flex items-center gap-2 text-sm font-semibold">
                    <Info
                      aria-hidden="true"
                      className="size-4 text-[var(--accent-pistache)]"
                    />
                    Recomendação
                  </h3>
                  <p className="mt-2 text-sm leading-6 text-muted">
                    {analysis
                      ? investigationSuggestion(analysis, filters)
                      : "Confira o detalhamento do período antes de tirar conclusões."}
                  </p>
                </section>
              )}

              <div className="flex flex-wrap gap-1.5">
                <span className="rounded-full border border-[var(--line)] bg-surface px-2.5 py-1 text-[11px] text-muted">
                  Período: {periodLabel(filters.periodo)}
                </span>
                <span className="rounded-full border border-[var(--line)] bg-surface px-2.5 py-1 text-[11px] text-muted">
                  Município: {filterLabel(filters.municipio, "Todos")}
                </span>
                <span className="rounded-full border border-[var(--line)] bg-surface px-2.5 py-1 text-[11px] text-muted">
                  Classe: {filterLabel(filters.classe, "Todas")}
                </span>
                <span className="rounded-full border border-[var(--line)] bg-surface px-2.5 py-1 text-[11px] text-muted">
                  Comparação: {comparisonLabel(filters)}
                </span>
              </div>

              <p className="flex items-start gap-1.5 text-xs leading-5 text-muted">
                <Info aria-hidden="true" className="mt-0.5 size-3.5 shrink-0" />
                {uniqueLimitations[0]}
              </p>

              <section className="border-t border-[var(--line)] pt-4">
                <button
                  type="button"
                  aria-expanded={showFoundation}
                  onClick={() => setShowFoundation((shown) => !shown)}
                  className="flex w-full items-center justify-between text-left text-sm font-semibold hover:text-brand focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand"
                >
                  <span>
                    {showFoundation ? "Ocultar fundamento" : "Ver fundamento"}
                  </span>
                  <ChevronDown
                    aria-hidden="true"
                    className={`size-4 transition-transform ${showFoundation ? "rotate-180" : ""}`}
                  />
                </button>
                {showFoundation && (
                  <div
                    role="region"
                    aria-label="Fundamento do insight"
                    tabIndex={0}
                    className="mt-3 space-y-3 text-xs leading-5 text-content focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand"
                  >
                    <div>
                      <p className="font-semibold">Recorte aplicado</p>
                      <p>
                        {metric.nome} ({metric.unidade}) ·{" "}
                        {periodLabel(filters.periodo)}
                        {metric.valorAnterior == null
                          ? ""
                          : ` comparado a ${comparisonLabel(filters)}`}
                      </p>
                      <p>
                        Município: {filterLabel(filters.municipio, "Todos")} ·
                        Classe: {filterLabel(filters.classe, "Todas")}
                      </p>
                    </div>
                    <div>
                      <p className="font-semibold">Definição</p>
                      <p>{response?.metric.definicao ?? metric.definicao}</p>
                    </div>
                    <div>
                      <p className="font-semibold">Fórmula aplicada</p>
                      <p className="font-mono">
                        {response?.metric.formula ?? metric.formula}
                      </p>
                    </div>
                    <div>
                      <p className="font-semibold">Fonte e lote</p>
                      <p>Dados sintéticos · {data.loteVersao}</p>
                      <p>Atualizado em {data.dataAtualizacao}</p>
                      {insight?.evidence.map((item) => (
                        <p
                          key={`${item.source}:${item.description}`}
                          className="break-all"
                        >
                          Evidência: {item.source} · {item.description}
                        </p>
                      ))}
                    </div>
                    <div>
                      <p className="font-semibold">Limitações</p>
                      <ul className="list-disc space-y-1 pl-4">
                        {uniqueLimitations.map((limitation) => (
                          <li key={limitation}>{limitation}</li>
                        ))}
                      </ul>
                    </div>
                  </div>
                )}
              </section>
            </div>
          </div>
        </dialog>
      )}
    </section>
  );
}
