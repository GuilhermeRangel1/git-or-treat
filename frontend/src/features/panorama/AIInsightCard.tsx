import { verifyVisualExport } from "../../shared/analytics/verifyVisualExport";
import VisualEvidence from "../../shared/analytics/VisualEvidence";
import { useEffect, useRef, useState } from "react";
import {
  ArrowRight,
  Check,
  ChevronDown,
  Info,
  Sparkles,
  X,
} from "lucide-react";
import { isGoldPublicationStale } from "../../shared/analytics/goldPublication";
import Button from "../../shared/ui/Button";
import { formatPanoramaTimestamp } from "./panorama-format";
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
  return `${months[month - 1]}/${year}`;
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

function businessLanguage(value: string) {
  return value
    .replace(/(?:fonte |dados )?Gold(?: v2)?/gi, "fonte de dados interna")
    .replace(/UCs?\/mês/g, "unidades consumidoras por mês")
    .replace(/\bUCs\b/g, "unidades consumidoras");
}
function formatValue(value: number | null, unit: string) {
  if (value == null) return "Indisponível";
  if (unit === "R$" || unit === "BRL")
    return new Intl.NumberFormat("pt-BR", {
      style: "currency",
      currency: "BRL",
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    }).format(value);
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
  if (analysis.composicaoAtual) {
    const item = analysis.composicaoAtual;
    const scope =
      item.dimension === "municipio"
        ? "entre os municípios"
        : item.dimension === "classe"
          ? "entre as classes de consumo"
          : "entre os bairros";
    const concentration =
      item.participacaoPercentual > 50
        ? "Esse segmento reúne mais da metade do valor observado neste recorte."
        : "Esse é o maior segmento do recorte; o restante da receita está distribuído entre os demais grupos.";
    return `${item.segmento} concentra ${formatPercentage(item.participacaoPercentual)} da receita observada em ${periodLabel(filters.periodo)} (${formatValue(item.valor, metric.unidade)}), liderando ${scope}. ${concentration}`;
  }
  if (metric.valorAtual === 0 && analysis.direcao === "indisponivel")
    return `A receita observada em ${periodLabel(filters.periodo)} soma ${formatValue(0, metric.unidade)} no recorte selecionado.`;
  const current = periodLabel(filters.periodo);
  const previous = comparisonLabel(filters);
  const percentage = formatPercentage(analysis.variacaoPercentual);

  if (analysis.direcao === "indisponivel")
    return `A receita observada em ${current} foi de ${formatValue(metric.valorAtual, metric.unidade)}. Explore os valores por município e classe no detalhamento.`;
  if (analysis.direcao === "estavel")
    return `${metric.nome} ficou estável de ${previous} para ${current}. A estabilidade do total pode coexistir com altas e quedas entre os segmentos; confira os movimentos no detalhamento.`;

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
  return `A maior ${movement} veio ${dimension} ${contribution.segmento}: ${formatValue(Math.abs(contribution.variacaoAbsoluta), unit)}${share ? ` (${share} das ${analysis.direcao === "queda" ? "reduções observadas" : "altas observadas"})` : ""}.`;
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
    return analysis.composicaoAtual?.dimension === "municipio"
      ? `Selecione ${analysis.composicaoAtual.segmento} e examine as classes que compõem sua receita.`
      : analysis.composicaoAtual?.dimension === "classe"
        ? `Selecione a classe ${analysis.composicaoAtual.segmento} para examinar sua distribuição territorial.`
        : analysis.composicaoAtual?.dimension === "bairro"
          ? `Acompanhe ${analysis.composicaoAtual.segmento} em outras competências com valores comparáveis para avaliar a continuidade dessa concentração.`
          : "Explore os valores por município e classe ou escolha outro período com evidência disponível.";
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
    return analysis.composicaoAtual?.dimension === "municipio"
      ? `explore ${analysis.composicaoAtual.segmento} por classe.`
      : analysis.composicaoAtual?.dimension === "classe"
        ? `examine a distribuição territorial de ${analysis.composicaoAtual.segmento}.`
        : analysis.composicaoAtual?.dimension === "bairro"
          ? `acompanhe ${analysis.composicaoAtual.segmento} em outros períodos comparáveis.`
          : "explore município, classe ou outro período disponível.";
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
  const isDemo = data.origem?.isDemo ?? true;
  const metric = isDemo
    ? data.metricas.energiaFaturada
    : data.metricas.receitaFaturada;
  const publicationStale = !isDemo && isGoldPublicationStale();
  const apiError =
    query.error instanceof PanoramaInsightApiError ? query.error : null;
  const keepLastAnalysis =
    query.isError &&
    apiError?.retryable === true &&
    ![401, 403, 409].includes(apiError.status ?? 0) &&
    apiError.code !== "invalid_context" &&
    query.data?.insight?.status === "answered";
  function canExportChart() {
    if (isDemo) return true;
    if (publicationStale || !data.origem?.fingerprint) return false;
    return verifyVisualExport({
      metric: "billing.revenue",
      dimension_ids: ["geography.municipality", "customer.consumption_class"],
      expected_publication: {
        lote: data.loteVersao,
        fingerprint: data.origem.fingerprint,
      },
    });
  }
  const response =
    publicationStale || (query.isError && !keepLastAnalysis)
      ? undefined
      : query.data;
  const insight = response?.insight;
  const analysis = response?.analysis;
  const pending =
    !publicationStale &&
    data.totalRegistros > 0 &&
    insight?.status !== "answered" &&
    (query.isPending || query.isFetching);
  const isStale = publicationStale || apiError?.code === "invalid_context";
  const canRetryResponse =
    insight?.status === "recoverable_error" &&
    insight.error?.retryable === true;
  const limitations = [
    ...(response?.source.limitacoes ?? []),
    ...(insight?.limitations ?? []),
  ];
  if (data.periodoIncompleto) {
    limitations.push(
      `A competência ${periodLabel(filters.periodo)} está em aberto; a comparação pode não estar disponível.`,
    );
  }
  if (isDemo)
    limitations.push(
      "Os números são fictícios e servem apenas para demonstração; não representam dados operacionais reais.",
    );
  const uniqueLimitations = [
    ...new Set(
      [
        ...limitations,
        ...(metric.limitacoes ?? []),
        ...(metric.limitacoesComparacao ?? []),
      ].map(businessLanguage),
    ),
  ];

  const observedAnalysis: PanoramaInsightAnalysis = {
    direcao:
      metric.variacaoAbsoluta == null
        ? "indisponivel"
        : metric.variacaoAbsoluta > 0
          ? "alta"
          : metric.variacaoAbsoluta < 0
            ? "queda"
            : "estavel",
    variacaoPercentual: metric.variacaoPercentual ?? null,
    principalContribuicao: null,
    compensacao: null,
    composicaoAtual:
      metric.variacaoAbsoluta == null
        ? data.distribuicao?.composicaoReceita
        : null,
  };
  const observedReading =
    metric.valorAtual == null
      ? "Não há valor disponível para interpretar este recorte."
      : describeTrend(observedAnalysis, metric, filters);

  let stateMessage = "";
  if (publicationStale) {
    stateMessage =
      "Os dados mudaram. Atualize o Panorama para gerar uma nova interpretação.";
  } else if (data.totalRegistros === 0) {
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
        {keepLastAnalysis && (
          <p role="status" className="text-xs text-muted">
            Última análise disponível. A conferência de atualização está
            pendente.
          </p>
        )}
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
      className={`flex w-full min-w-0 flex-col gap-4 rounded-xl border p-4 shadow-sm ${data.totalRegistros === 0 || (query.isError && !keepLastAnalysis) || (insight && insight.status !== "answered") ? "border-[var(--status-warning)] bg-[var(--accent-goiaba-subtle)]" : "border-border bg-[var(--accent-pistache-subtle)]"}`}
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
                Análise assistida por IA ·{" "}
                {isDemo ? "dados demonstrativos" : "fonte de dados interna"}
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
                {isDemo ? metric.nome : "Receita observada"} ·{" "}
                {periodLabel(filters.periodo)}
              </p>
              <p className="mt-1 text-xs text-muted">
                {metric.valorAnterior == null
                  ? filters.comparacao === "nenhuma"
                    ? "Sem comparação selecionada"
                    : `${comparisonLabel(filters)}: comparação indisponível neste recorte`
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
          <div className="mt-2 space-y-2">
            <p className="text-sm font-medium leading-6 text-content">
              {observedReading}
            </p>
            <p className="border-l-2 border-[var(--accent-pistache)] pl-3 text-xs leading-5 text-muted">
              <span className="font-semibold text-content">Próximo passo:</span>{" "}
              {compactNextStep(observedAnalysis)}
            </p>
            <p
              role="status"
              aria-live="polite"
              className="mt-2 text-sm leading-6 text-content"
            >
              <span className="mr-2 inline-block size-3 animate-spin rounded-full border-2 border-[var(--line)] border-t-[var(--accent-pistache)] align-[-2px]" />
              Preparando a interpretação da IA…
            </p>
          </div>
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
            {analysis && metric.valorAtual !== 0 && (
              <p className="mt-3 border-l-2 border-[var(--accent-pistache)] pl-3 text-xs leading-5 text-muted">
                <span className="font-semibold text-content">
                  Próximo passo:
                </span>{" "}
                {compactNextStep(analysis)}
              </p>
            )}
            {insight.hypothesis && analysis?.direcao !== "indisponivel" && (
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
            {!isStale && (apiError?.retryable || canRetryResponse) && (
              <p className="mb-2 text-sm font-medium leading-6 text-content">
                {observedReading}
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
        {keepLastAnalysis && (
          <p role="status" className="mt-2 text-xs leading-5 text-muted">
            Exibindo a última análise deste recorte. A conferência de
            atualização está pendente.
          </p>
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
          className="fixed inset-y-0 right-0 m-0 h-dvh w-[min(760px,100vw)] max-h-none max-w-none overflow-hidden border-l border-border bg-surface p-0 text-content shadow-2xl backdrop:bg-black/45"
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
                      {isDemo ? metric.nome : "Receita observada"} ·{" "}
                      {periodLabel(filters.periodo)}
                    </p>
                    <p className="mt-1 text-xs text-muted">
                      {metric.valorAnterior == null
                        ? filters.comparacao === "nenhuma"
                          ? "Sem comparação selecionada"
                          : `${comparisonLabel(filters)}: comparação indisponível neste recorte`
                        : `${comparisonLabel(filters)}: ${formatValue(metric.valorAnterior, metric.unidade)}${metric.variacaoAbsoluta == null ? "" : ` · variação ${formatSignedValue(metric.variacaoAbsoluta, metric.unidade)}`}`}
                    </p>
                  </>
                )}
              </section>

              {!publicationStale &&
                data.totalRegistros > 0 &&
                metric.valorAtual !== null && (
                  <VisualEvidence
                    key={`${data.loteVersao}-${data.dataAtualizacao}-${JSON.stringify(filters)}`}
                    canExport={canExportChart}
                    data={{
                      isDemo,
                      title: metric.nome,
                      unit: metric.unidade,
                      note:
                        metric.limitacoes?.map(businessLanguage).join(" ") ||
                        undefined,
                      scope: `${filterLabel(filters.municipio, "Todos os municípios")} · ${filterLabel(filters.classe, "Todas as classes")}`,
                      points: [
                        ...(filters.comparacao !== "nenhuma" &&
                        metric.valorAnterior != null
                          ? [
                              {
                                label: comparisonLabel(filters),
                                value: metric.valorAnterior,
                              },
                            ]
                          : []),
                        {
                          label: periodLabel(filters.periodo),
                          value: metric.valorAtual,
                        },
                      ],
                    }}
                  />
                )}

              {!publicationStale &&
                data.distribuicao &&
                data.totalRegistros > 0 && (
                  <VisualEvidence
                    key={`distribution-${data.loteVersao}-${data.dataAtualizacao}-${JSON.stringify(filters)}`}
                    canExport={canExportChart}
                    data={{
                      reading: data.distribuicao.reading,
                      kind:
                        data.distribuicao.completo &&
                        (data.distribuicao.visual ?? data.distribuicao.pontos)
                          .length <= 6
                          ? "donut"
                          : "horizontal",
                      isDemo,
                      total: data.distribuicao.total,
                      title: `${metric.nome} por ${data.distribuicao.dimension === "municipio" ? "município" : "classe"}`,
                      categoryLabel:
                        data.distribuicao.dimension === "municipio"
                          ? "Município"
                          : "Classe",
                      unit: data.distribuicao.unidade,
                      scope: `${periodLabel(filters.periodo)} · ${filterLabel(filters.municipio, "Todos os municípios")} · ${filterLabel(filters.classe, "Todas as classes")}`,
                      note:
                        [
                          data.distribuicao.agrupados
                            ? `${data.distribuicao.pontos.length} grupos no recorte. Gráfico: 5 maiores e ${data.distribuicao.agrupados} agrupados. Tabela e CSV: lista completa.`
                            : data.distribuicao.pontos.length > 10
                              ? `${data.distribuicao.pontos.length} grupos no recorte. Gráfico: 10 maiores valores observados. Tabela e CSV: lista completa.`
                              : undefined,
                          !data.distribuicao.completo
                            ? "Valores observados; a base não permite calcular participações neste recorte."
                            : undefined,
                        ]
                          .filter(Boolean)
                          .join(" ") || undefined,
                      tablePoints: data.distribuicao.pontos.map((p) => ({
                        label: p.segmento,
                        value: p.valor,
                        percentage: p.percentual,
                      })),
                      points: (
                        data.distribuicao.visual ?? data.distribuicao.pontos
                      ).map((p) => ({
                        label: p.segmento,
                        value: p.valor,
                        percentage: p.percentual,
                      })),
                    }}
                  />
                )}

              <section aria-labelledby="panorama-insight-points-title">
                <h3
                  id="panorama-insight-points-title"
                  className="font-heading text-base font-semibold"
                >
                  Principais pontos
                </h3>
                <div className="mt-3">
                  {pending ? (
                    <div className="space-y-3 text-sm leading-6">
                      <p className="font-medium">{observedReading}</p>
                      <p>
                        <span className="font-semibold">Próximo passo:</span>{" "}
                        {compactNextStep(observedAnalysis)}
                      </p>
                      <p role="status" className="text-muted">
                        Preparando a análise complementar…
                      </p>
                    </div>
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

              {insight?.status === "answered" &&
                analysis?.direcao !== "indisponivel" &&
                insight.hypothesis && (
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

              {insight?.status === "answered" &&
                analysis &&
                metric.valorAtual !== 0 && (
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
                Consulte o fundamento para conhecer a cobertura e os critérios
                do cálculo.
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
                        {filters.comparacao === "nenhuma"
                          ? " · Sem comparação"
                          : ` comparado a ${comparisonLabel(filters)}`}
                      </p>
                      <p>
                        Município: {filterLabel(filters.municipio, "Todos")} ·
                        Classe: {filterLabel(filters.classe, "Todas")}
                      </p>
                    </div>
                    <div>
                      <p className="font-semibold">Definição</p>
                      <p>
                        {businessLanguage(
                          response?.metric.definicao ?? metric.definicao,
                        )}
                      </p>
                    </div>
                    <div>
                      <p className="font-semibold">Como o valor é calculado</p>
                      <p>
                        {isDemo
                          ? "Soma da energia faturada no período e nos filtros selecionados."
                          : "Soma da receita faturada nas unidades consumidoras com fatura e leituras válidas no período e nos filtros selecionados."}
                      </p>
                    </div>
                    <div>
                      <p className="font-semibold">Fonte dos dados</p>
                      <p>
                        {isDemo
                          ? "Dados demonstrativos"
                          : "Fonte de dados interna"}
                      </p>
                      <p>
                        Atualizado em{" "}
                        {formatPanoramaTimestamp(data.dataAtualizacao)}
                      </p>
                      <p>
                        Os valores usam os mesmos indicadores e filtros do
                        Panorama.
                      </p>
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
