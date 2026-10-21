import { usePanoramaData } from "../../shared/analytics/usePanoramaData";
import FilterBar from "../../shared/filters/FilterBar";
import { usePanoramaFilters } from "../../shared/filters/usePanoramaFilters";
import ContentState from "../../shared/ui/ContentState";
import MetricCard from "../../shared/ui/MetricCard";
import PanoramaArtwork from "./PanoramaArtwork";
import PanoramaSeriesChart from "./PanoramaSeriesChart";

export default function PanoramaPage() {
  const { filters, setFilter, resetFilters, hasActiveFilters } =
    usePanoramaFilters();
  const { data, isLoading, isError, refetch } = usePanoramaData(filters);

  const comparacaoLabel =
    filters.comparacao === "anterior"
      ? "vs. mês anterior (m-1)"
      : filters.comparacao === "ano_anterior"
        ? "vs. mesmo mês ano anterior (m-12)"
        : "Sem comparação";

  const isVazio = data && data.totalRegistros === 0;

  return (
    <div className="relative space-y-6 pb-12">
      {/* Topo e Arte do Panorama (Preservando Identidade Visual do Figma) */}
      <div className="relative">
        <div className="relative z-10 w-full lg:w-[calc(100%_-_278px)]">
          <h1 className="font-heading text-[26px] leading-[34px] font-semibold lg:w-fit lg:text-[32px] lg:leading-10 lg:tracking-[-0.64px]">
            Sua rede, em perspectiva.
          </h1>
          <p className="mt-2 text-sm leading-[22px] text-muted">
            Um panorama da operação comercial, do atendimento e da continuidade.
          </p>
        </div>
        <PanoramaArtwork />
      </div>

      {/* Alerta de Período Incompleto / Preliminar */}
      {data?.periodoIncompleto && (
        <ContentState
          type="partial"
          title="Competência 2024-05 em aberto · Dados preliminares"
          description="Os faturamentos e medições desta competência ainda não foram consolidados pelo fechamento mensal. Os números exibidos são parciais e podem sofrer alterações até a homologação."
        />
      )}

      {/* Barra de Filtros Integrada à URL */}
      <FilterBar
        filters={filters}
        onFilterChange={setFilter}
        onReset={resetFilters}
        hasActiveFilters={hasActiveFilters}
      />

      {/* Estados de Carregamento, Erro e Vazio */}
      {isLoading && <ContentState type="loading" />}

      {isError && (
        <ContentState
          type="error"
          title="Erro na consulta dos indicadores"
          description="Não foi possível carregar os dados agregados para os filtros informados. Tente recarregar ou verificar sua conexão."
          onRetry={() => refetch()}
        />
      )}

      {isVazio && !isLoading && !isError && (
        <ContentState
          type="empty"
          title="Nenhum registro para o recorte selecionado"
          description="Não encontramos faturas ou medições para a combinação de filtros selecionada (competência, município ou classe sem clientes ativos nesta concessão)."
          onResetFilters={resetFilters}
        />
      )}

      {/* Conteúdo Principal (Métricas e Séries) quando há dados */}
      {data && !isVazio && !isLoading && !isError && (
        <>
          {/* Grid de KPIs do Panorama (Diretoria · WEB-01) */}
          <section aria-label="Indicadores principais do Panorama">
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
              <MetricCard
                metric={data.metricas.receitaFaturada}
                comparacaoLabel={comparacaoLabel}
                loteVersao={data.loteVersao}
              />
              <MetricCard
                metric={data.metricas.receitaPaga}
                comparacaoLabel={comparacaoLabel}
                loteVersao={data.loteVersao}
              />
              <MetricCard
                metric={data.metricas.energiaConsumida}
                comparacaoLabel={comparacaoLabel}
                loteVersao={data.loteVersao}
              />
              <MetricCard
                metric={data.metricas.energiaFaturada}
                comparacaoLabel={comparacaoLabel}
                loteVersao={data.loteVersao}
              />
              <MetricCard
                metric={data.metricas.precoMedioEfetivo}
                comparacaoLabel={comparacaoLabel}
                loteVersao={data.loteVersao}
              />
              <MetricCard
                metric={data.metricas.ucsAtivas}
                comparacaoLabel={comparacaoLabel}
                loteVersao={data.loteVersao}
              />
              <MetricCard
                metric={data.metricas.continuidadeDec}
                comparacaoLabel={comparacaoLabel}
                loteVersao={data.loteVersao}
              />
              <MetricCard
                metric={data.metricas.continuidadeFec}
                comparacaoLabel={comparacaoLabel}
                loteVersao={data.loteVersao}
              />
            </div>
          </section>

          {/* Gráfico de Séries Históricas das Competências */}
          <PanoramaSeriesChart data={data.serieMensal} />

          {/* Nota de Governança e Rastreabilidade */}
          <footer className="mt-8 pt-4 border-t border-[var(--line-subtle)] flex flex-wrap items-center justify-between gap-3 text-xs text-muted font-mono">
            <div>
              <span>Fonte: </span>
              <strong className="text-content font-medium">
                {data.loteVersao}
              </strong>{" "}
              <span>· Base sintética auditada (PRD WEB-01)</span>
            </div>
            <div>
              <span>Última atualização: </span>
              <span className="text-content">
                {new Date(data.dataAtualizacao).toLocaleDateString("pt-BR", {
                  day: "2-digit",
                  month: "2-digit",
                  year: "numeric",
                })}
              </span>
            </div>
          </footer>
        </>
      )}
    </div>
  );
}
