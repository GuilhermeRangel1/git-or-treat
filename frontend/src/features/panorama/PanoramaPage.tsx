import { useRef, useState } from "react";
import { Link } from "react-router-dom";
import { Activity, Bot, ChartNoAxesCombined } from "lucide-react";
import { usePanoramaData } from "../../shared/analytics/usePanoramaData";
import { useSourceOptions } from "../../shared/analytics/sourceOptions";
import FilterBar from "../../shared/filters/FilterBar";
import { usePanoramaFilters } from "../../shared/filters/usePanoramaFilters";
import ContentState from "../../shared/ui/ContentState";
import Button from "../../shared/ui/Button";
import Modal from "../../shared/ui/Modal";
import PanoramaMetricCard from "./PanoramaMetricCard";
import PanoramaFoundations from "./PanoramaFoundations";
import PanoramaStatus from "./PanoramaStatus";
import AIInsightCard from "./AIInsightCard";
import PanoramaSeriesChart from "./PanoramaSeriesChart";
import { usePanoramaInsight } from "./usePanoramaInsight";
import { formatPanoramaTimestamp } from "./panorama-format";
import { formatCompetenciaLabel } from "../../shared/analytics/syntheticData";

export default function PanoramaPage() {
  const options = useSourceOptions();
  const {
    filters,
    setFilters,
    resetFilters,
    hasActiveFilters,
    errors,
    isValid,
  } = usePanoramaFilters(options.data?.data);
  const { data, isLoading, isError, isFetching, refetch } = usePanoramaData(
    filters,
    isValid,
  );
  const [continuityOpen, setContinuityOpen] = useState(false);
  const continuityRef = useRef<HTMLButtonElement>(null);
  const isEmpty = Boolean(data && data.totalRegistros === 0);
  const insight = usePanoramaInsight(
    filters,
    data,
    isValid && Boolean(data) && !isLoading && !isError,
  );
  const comparisonLabel =
    filters.comparacao === "anterior"
      ? "vs. mês anterior"
      : filters.comparacao === "ano_anterior"
        ? "vs. mesmo mês do ano anterior"
        : "Sem comparação";
  const comparisonUnavailable = Boolean(
    data?.periodoIncompleto && filters.comparacao !== "nenhuma",
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

      {data && (
        <p className="text-xs leading-[18px] text-muted">
          Atualizado em {formatPanoramaTimestamp(data.dataAtualizacao)}{" "}
          <span aria-hidden="true">·</span> Base sintética
        </p>
      )}

      {isValid && data?.periodoIncompleto && (
        <ContentState
          type="partial"
          title={`Competência ${formatCompetenciaLabel(filters.periodo)} em aberto · Dados preliminares`}
          description="Os dados desta competência ainda são parciais. A comparação entre períodos completos fica indisponível até o fechamento."
        />
      )}

      <FilterBar
        options={options.data?.data}
        filters={filters}
        onApply={setFilters}
        hasActiveFilters={hasActiveFilters}
        errors={errors}
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
          <section
            aria-label="Indicadores principais do Panorama"
            className="grid grid-cols-2 gap-3 xl:grid-cols-4 xl:gap-4"
          >
            <PanoramaMetricCard
              metric={data.metricas.receitaFaturada}
              title="Valor faturado"
              period={filters.periodo}
              comparison={filters.comparacao}
              comparisonUnavailable={comparisonUnavailable}
            />
            <PanoramaMetricCard
              metric={data.metricas.energiaFaturada}
              title="Energia faturada"
              period={filters.periodo}
              comparison={filters.comparacao}
              comparisonUnavailable={comparisonUnavailable}
            />
            <PanoramaMetricCard
              metric={data.metricas.energiaConsumida}
              title="Consumo apurado"
              period={filters.periodo}
              comparison={filters.comparacao}
              comparisonUnavailable={comparisonUnavailable}
            />
            <PanoramaMetricCard
              metric={data.metricas.ucsAtivas}
              title="Base de UCs"
              period={filters.periodo}
              comparison={filters.comparacao}
              comparisonUnavailable={comparisonUnavailable}
            />
          </section>

          <div className="grid min-w-0 grid-cols-1 items-start gap-6 xl:items-stretch xl:grid-cols-[minmax(0,1fr)_340px]">
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
              <Button
                ref={continuityRef}
                variant="outline"
                size="md"
                leftIcon={<Activity className="size-4" aria-hidden="true" />}
                onClick={() => setContinuityOpen(true)}
              >
                Ver continuidade
              </Button>
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
                {data.metricas.continuidadeDec.valorAtual.toLocaleString(
                  "pt-BR",
                  { maximumFractionDigits: 2 },
                )}{" "}
                h/UC
                <span aria-hidden="true"> · </span>
                FEC{" "}
                {data.metricas.continuidadeFec.valorAtual.toLocaleString(
                  "pt-BR",
                  { maximumFractionDigits: 2 },
                )}{" "}
                interrupções/UC. Indicadores simplificados para uso interno, não
                regulatórios.
              </p>
            </aside>
            <div className="flex flex-col items-start justify-between gap-4 sm:flex-row sm:items-center">
              <span className="text-xs text-muted">
                Fonte sintética · Sem Gold
              </span>
              <div className="flex flex-wrap items-center gap-2">
                <PanoramaFoundations
                  data={data}
                  comparisonLabel={comparisonLabel}
                  comparisonUnavailable={
                    comparisonUnavailable
                      ? "Comparação indisponível · período incompleto"
                      : undefined
                  }
                />
              </div>
            </div>
          </footer>
        </>
      )}

      <Modal
        open={continuityOpen}
        onClose={() => setContinuityOpen(false)}
        triggerRef={continuityRef}
        title="Continuidade da rede"
        description="Indicadores internos simplificados para apoiar a exploração do Panorama."
        closeLabel="Fechar continuidade"
        size="md"
        header="inline"
      >
        <p className="text-sm leading-6 text-muted">
          DEC e FEC nesta demonstração são métricas internas simplificadas. Não
          representam indicadores regulatórios nem substituem a apuração
          oficial. Os valores e suas fórmulas podem ser auditados em Ver
          fundamentos.
        </p>
        <div className="mt-5">
          <Link
            className="inline-flex min-h-11 items-center rounded-lg border border-control px-4 text-sm font-medium focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand"
            to="/operacao"
          >
            Abrir operação
          </Link>
        </div>
      </Modal>
    </div>
  );
}
