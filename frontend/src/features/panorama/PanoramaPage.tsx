import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Bot, ChartNoAxesCombined } from "lucide-react";
import { usePanoramaData } from "../../shared/analytics/usePanoramaData";
import FilterBar from "../../shared/filters/FilterBar";
import { usePanoramaFilters } from "../../shared/filters/usePanoramaFilters";
import ContentState from "../../shared/ui/ContentState";
import Button from "../../shared/ui/Button";
import PanoramaMetricCard from "./PanoramaMetricCard";
import PanoramaFoundations from "./PanoramaFoundations";
import PanoramaStatus from "./PanoramaStatus";
import AIInsightCard from "./AIInsightCard";
import PanoramaSeriesChart from "./PanoramaSeriesChart";
import { usePanoramaInsight } from "./usePanoramaInsight";
import { formatCompetenciaLabel } from "../../shared/analytics/syntheticData";
import type { PanoramaFilterOptions } from "../../shared/analytics/types";
import { useGoldPublicationKey } from "../../shared/analytics/goldPublication";

export default function PanoramaPage() {
  const publicationKey = useGoldPublicationKey();
  const [catalogState, setCatalogState] = useState<{
    publicationKey: string;
    sourceKind: "gold" | "synthetic";
    options?: PanoramaFilterOptions;
  }>();
  const catalog =
    catalogState?.publicationKey === publicationKey ? catalogState : undefined;
  const {
    filters,
    periodoExplicit,
    needsSourceDiscovery,
    setFilters,
    setBootstrapPeriod,
    resetFilters,
    hasActiveFilters,
    errors,
    isValid,
  } = usePanoramaFilters(catalog?.options, catalog?.sourceKind);
  const {
    data: receivedData,
    isLoading,
    isError,
    isFetching,
    refetch,
  } = usePanoramaData(filters, isValid, !periodoExplicit, needsSourceDiscovery);
  const bootstrap = !periodoExplicit;

  /* eslint-disable react/set-state-in-effect -- captures publication options from the external API response. */
  useEffect(() => {
    if (receivedData?.origem?.kind === "gold" && receivedData.opcoesFiltros) {
      setCatalogState({
        publicationKey,
        sourceKind: "gold",
        options: receivedData.opcoesFiltros,
      });
    } else if (receivedData?.origem?.kind === "synthetic") {
      setCatalogState({ publicationKey, sourceKind: "synthetic" });
    }
  }, [publicationKey, receivedData]);
  /* eslint-enable react/set-state-in-effect */

  const responseMatchesUrl =
    receivedData &&
    (Object.keys(filters) as (keyof typeof filters)[]).every(
      (key) => receivedData.filtros[key] === filters[key],
    );
  const data = responseMatchesUrl ? receivedData : undefined;

  useEffect(() => {
    if (
      bootstrap &&
      receivedData?.origem?.kind === "gold" &&
      receivedData.filtros.periodo !== filters.periodo
    ) {
      // Replace URL state with the latest observed period selected by the API.
      // eslint-disable-next-line react/set-state-in-effect
      setBootstrapPeriod(receivedData.filtros.periodo);
    }
  }, [bootstrap, receivedData, filters.periodo, setBootstrapPeriod]);
  const isEmpty = Boolean(data && data.totalRegistros === 0);
  const insight = usePanoramaInsight(
    filters,
    data,
    isValid && Boolean(data) && !isLoading && !isError,
  );
  const revenueParams = new URLSearchParams({
    competencia_inicio: filters.periodo,
    competencia_fim: filters.periodo,
  });
  if (filters.municipio !== "todos")
    revenueParams.set("municipio", filters.municipio);
  if (filters.classe !== "todas") revenueParams.set("classe", filters.classe);

  return (
    <div className="relative grid w-full min-w-0 gap-4 pb-12">
      <header className="mb-2">
        <div>
          <h1 className="font-heading text-[26px] font-semibold leading-[34px] lg:text-[32px] lg:leading-10 lg:tracking-[-0.64px]">
            Sua rede, em perspectiva.
          </h1>
          <p className="mt-2 text-sm leading-[22px] text-muted">
            Um panorama da operação comercial, do atendimento e da continuidade.
          </p>
        </div>
      </header>

      {isValid && data?.periodoIncompleto && (
        <ContentState
          type="partial"
          title={`Competência ${formatCompetenciaLabel(filters.periodo)} · dados preliminares`}
          description={
            data.origem?.kind === "gold"
              ? "Os dados observados nesta competência são parciais. A fonte não declara o fechamento mensal."
              : "Os dados observados nesta competência são parciais. Consulte os detalhes do indicador para as condições de comparação."
          }
        />
      )}

      <FilterBar
        filters={filters}
        onApply={setFilters}
        hasActiveFilters={hasActiveFilters}
        errors={errors}
        availableOptions={
          data?.origem?.kind === "gold" ? data.opcoesFiltros : undefined
        }
      />

      {!isValid && (
        <ContentState
          type="error"
          title="Filtros inválidos na URL"
          description="Corrija os campos indicados ou restaure os filtros padrão. Nenhuma consulta foi enviada com estes filtros."
          onResetFilters={resetFilters}
        />
      )}
      {isLoading && <ContentState type="loading" />}
      {isValid && isError && !data && (
        <ContentState
          type="error"
          title="Erro na consulta dos indicadores"
          description="Não foi possível carregar os dados agregados para os filtros informados. Tente recarregar ou verificar sua conexão."
          onRetry={() => void refetch()}
        />
      )}

      {isValid && isError && data && (
        <div
          role="status"
          className="flex flex-col items-start justify-between gap-3 rounded-xl border border-[var(--status-warning)]/30 bg-[var(--status-warning)]/10 p-4 text-sm sm:flex-row sm:items-center"
        >
          <p className="text-content">
            Atualização pendente · exibindo o último conjunto válido.
          </p>
          <Button variant="outline" onClick={() => void refetch()}>
            Tentar atualizar novamente
          </Button>
        </div>
      )}

      {isValid && isEmpty && !isLoading && !isError && data && (
        <>
          <ContentState
            type="empty"
            title="Nenhum registro para o recorte selecionado"
            description="Não encontramos faturas ou medições para a combinação de filtros selecionada."
            onResetFilters={resetFilters}
          />
          <div className="xl:max-w-[460px]">
            <AIInsightCard
              filters={filters}
              data={data}
              query={insight}
              onRefreshIndicators={() => void refetch()}
            />
          </div>
        </>
      )}

      {isValid && data && !isEmpty && !isLoading && (
        <>
          <p className="text-sm text-muted">
            Competência dos indicadores:{" "}
            {formatCompetenciaLabel(filters.periodo)}
          </p>
          <section
            aria-label="Indicadores principais do Panorama"
            className="grid grid-cols-2 gap-3 xl:grid-cols-4 xl:gap-4"
          >
            <PanoramaMetricCard
              metric={data.metricas.receitaFaturada}
              title="Valor faturado"
              comparison={filters.comparacao}
            />
            <PanoramaMetricCard
              metric={data.metricas.energiaConsumida}
              title="Consumo apurado"
              comparison={filters.comparacao}
            />
            <PanoramaMetricCard
              metric={data.metricas.ucsAtivas}
              title={
                data.origem?.kind === "gold"
                  ? "UCs cadastradas no lote"
                  : "Base de UCs"
              }
              comparison={filters.comparacao}
            />
            <PanoramaMetricCard
              metric={
                data.metricas.ucsFaturadasNoMes ?? {
                  id: "ucs_fat",
                  nome: "UCs faturadas no mês",
                  categoria: "operacional",
                  tipoGrandeza: "operacao",
                  valorAtual: null,
                  unidade: "UCs",
                  definicao:
                    "Contagem de UCs com fatura observada na competência.",
                  formula: "Não informado pela API",
                  status: "unavailable",
                  limitacoes: ["Este contrato não disponibiliza a contagem."],
                }
              }
              title="UCs faturadas no mês"
              comparison={filters.comparacao}
            />
          </section>

          <div className="grid min-w-0 grid-cols-1 items-stretch gap-4 xl:grid-cols-[minmax(0,1fr)_minmax(280px,320px)]">
            <PanoramaSeriesChart
              data={data.serieMensal}
              selectedPeriod={filters.periodo}
              partialPeriod={
                data.periodoIncompleto ? filters.periodo : undefined
              }
            />
            <AIInsightCard
              filters={filters}
              data={data}
              query={insight}
              onRefreshIndicators={() => void refetch()}
            />
          </div>

          <footer className="space-y-6">
            <div className="flex flex-col items-stretch gap-4 sm:flex-row sm:flex-wrap sm:items-center">
              <Link
                className="inline-flex min-h-11 items-center justify-center gap-2 rounded-lg bg-content px-4 text-sm font-medium text-canvas hover:opacity-90 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand"
                to={`/receita?${revenueParams.toString()}`}
              >
                <ChartNoAxesCombined className="size-4" aria-hidden="true" />
                Explorar receita
              </Link>
              <Link
                className="inline-flex min-h-11 items-center justify-center rounded-lg border border-control px-4 text-sm font-medium text-content hover:bg-surface-hover focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand"
                to={`/operacao?competencia_inicio=${filters.periodo}&competencia_fim=${filters.periodo}${filters.municipio === "todos" ? "" : `&municipio=${encodeURIComponent(filters.municipio)}`}`}
              >
                Abrir operação
              </Link>
              <Link
                className="inline-flex min-h-11 items-center justify-center gap-2 rounded-lg px-4 text-sm font-medium text-content hover:bg-surface-hover focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand"
                to="/assistente"
              >
                <Bot className="size-4" aria-hidden="true" />
                Perguntar à IA
              </Link>
              <PanoramaStatus
                data={data}
                isFetching={isFetching}
                onRefresh={() => void refetch()}
              />
            </div>
            <aside
              role="note"
              className="rounded-xl bg-[var(--status-info-bg)] p-4 text-sm text-[var(--status-info-text)]"
            >
              <h2 className="font-semibold">Continuidade interna</h2>
              <p className="mt-1 leading-5">
                DEC{" "}
                {data.metricas.continuidadeDec.valorAtual?.toLocaleString(
                  "pt-BR",
                  { maximumFractionDigits: 2 },
                ) ?? "indisponível"}{" "}
                h/UC
                <span aria-hidden="true"> · </span>
                FEC{" "}
                {data.metricas.continuidadeFec.valorAtual?.toLocaleString(
                  "pt-BR",
                  { maximumFractionDigits: 2 },
                ) ?? "indisponível"}{" "}
                interrupções/UC. Indicadores simplificados para uso interno, não
                regulatórios.
              </p>
            </aside>
            <div className="flex flex-col items-start justify-between gap-4 sm:flex-row sm:items-center">
              <div className="flex flex-wrap items-center gap-2">
                <PanoramaFoundations data={data} />
              </div>
            </div>
          </footer>
        </>
      )}
    </div>
  );
}
