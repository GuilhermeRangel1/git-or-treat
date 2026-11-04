import { useMemo } from "react";
import { useQueryClient } from "@tanstack/react-query";
import {
  isGoldPublicationStale,
  resetGoldPublication,
} from "@/shared/analytics/goldPublication";
import Button from "@/shared/ui/Button";
import { useSearchParams } from "react-router-dom";
import { municipalityByCode, municipalities } from "./municipalities";
import MunicipalityMap from "./MunicipalityMap";
import MapFilters from "./MapFilters";
import MapLegend from "./MapLegend";
import MunicipalityTable from "./MunicipalityTable";
import MunicipalityPanel from "./MunicipalityPanel";
import { classifyMapValues } from "./map-scale";
import {
  updateMapSearchParams,
  buildRevenueDestination,
  type MapLayer,
} from "./map-state";
import { valueForLayer } from "./map-values";
import { useTerritoryMap } from "./useTerritoryMap";

export default function MapaPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const queryClient = useQueryClient();
  const map = useTerritoryMap();
  const stalePublication = isGoldPublicationStale();
  const query = map.parsed.query;
  const layer: MapLayer = query?.camada ?? "revenue";
  const rawValues = {
    competencia_inicio: searchParams.get("competencia_inicio") ?? undefined,
    competencia_fim: searchParams.get("competencia_fim") ?? undefined,
    classe: searchParams.get("classe") ?? undefined,
    municipio: searchParams.get("municipio") ?? undefined,
    camada: (searchParams.get("camada") ?? undefined) as MapLayer | undefined,
  };
  const metrics = useMemo(() => {
    return (
      map.mapped?.items ??
      municipalities.map((municipality) => ({ municipality, item: null }))
    );
  }, [map.mapped]);
  const partialCodes = useMemo(
    () =>
      new Set(
        metrics.flatMap(({ municipality, item }) =>
          item?.comparison.final.status === "partial" ||
          item?.comparison.initial.status === "partial"
            ? [municipality.code]
            : [],
        ),
      ),
    [metrics],
  );
  const numericValues = metrics.map(({ item }) => valueForLayer(item, layer));
  const scale = useMemo(
    () =>
      classifyMapValues(
        numericValues,
        layer.endsWith("change") ? "diverging" : "absolute",
        partialCodes,
      ),
    [numericValues, layer, partialCodes],
  );
  const selected = query?.municipio
    ? (municipalityByCode(query.municipio) ?? null)
    : null;
  const selectedItem = selected
    ? (metrics.find(({ municipality }) => municipality.code === selected.code)
        ?.item ?? null)
    : null;
  const revenueHref =
    query && selected && map.detailRequest && !stalePublication
      ? buildRevenueDestination(query, map.detailRequest.municipio)
      : null;
  const detailError = map.detail.isError;
  const summaryEnvelope = map.summaryEnvelope;
  const detailEnvelope = map.detailEnvelope;

  function update(changes: Parameters<typeof updateMapSearchParams>[1]) {
    setSearchParams(updateMapSearchParams(searchParams, changes), {
      preventScrollReset: true,
    });
  }

  function refreshPublication() {
    resetGoldPublication();
    void Promise.all([
      queryClient.invalidateQueries({ queryKey: ["analytics", "options"] }),
      queryClient.invalidateQueries({ queryKey: ["territory-map"] }),
    ]);
  }

  return (
    <div className="rmr-page mt-5 grid min-w-0 gap-4">
      <MapFilters
        months={map.catalog.data?.data.competencias ?? []}
        classes={map.catalog.data?.data.classe ?? []}
        searchValues={query ?? rawValues}
        onApply={update}
      />

      {map.catalog.isPending ? (
        <p
          role="status"
          className="rounded-xl border border-border bg-surface p-3 text-sm text-muted"
        >
          Carregando competências e classes…
        </p>
      ) : null}
      {map.catalog.isError ? (
        <div
          role="alert"
          className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-danger bg-surface p-3 text-sm text-content"
        >
          <p>Não foi possível carregar as opções de filtro.</p>
          <Button
            variant="outline"
            size="sm"
            onClick={() => void map.catalog.refetch()}
          >
            Tentar novamente
          </Button>
        </div>
      ) : null}
      {map.catalog.data && map.parsed.errors.length ? (
        <div
          role="alert"
          className="rounded-xl border border-danger bg-surface p-4 text-sm text-content"
        >
          <h2 className="font-semibold">O link contém filtros inválidos.</h2>
          <ul className="mt-2 list-inside list-disc">
            {map.parsed.errors.map((error) => (
              <li key={error}>{error}</li>
            ))}
          </ul>
          <p className="mt-2 text-muted">
            Revise os campos e aplique os filtros.
          </p>
        </div>
      ) : null}
      {stalePublication ? (
        <div
          role="alert"
          className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-danger bg-surface p-3 text-sm text-content"
        >
          <p>A publicação mudou. Atualize os dados para continuar.</p>
          <Button variant="primary" onClick={refreshPublication}>
            Atualizar publicação
          </Button>
        </div>
      ) : null}
      {map.summary.isPending && query ? (
        <p
          role="status"
          className="rounded-xl border border-border bg-surface p-3 text-sm text-muted"
        >
          Carregando indicadores municipais para {query.competencia_inicio} a{" "}
          {query.competencia_fim}…
        </p>
      ) : null}
      {map.summary.isError && !stalePublication ? (
        <div
          role="alert"
          className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-danger bg-surface p-3 text-sm text-content"
        >
          <p>
            Não foi possível carregar os indicadores do mapa. A lista permanece
            disponível; tente novamente.
          </p>
          <Button
            variant="outline"
            size="sm"
            onClick={() => void map.summary.refetch()}
          >
            Tentar novamente
          </Button>
        </div>
      ) : null}
      {summaryEnvelope?.metadata.source.is_demo ? (
        <p role="status" className="text-xs text-muted">
          Demonstração · dados sintéticos da fonte atual.
        </p>
      ) : null}

      {query ? (
        <MapLegend
          layer={layer}
          start={query.competencia_inicio}
          end={query.competencia_fim}
          min={scale.domainMin}
          max={scale.domainMax}
          diverging={layer.endsWith("change")}
        />
      ) : null}
      {map.mapped?.unmatched.length ? (
        <p
          role="status"
          className="rounded-xl border border-control bg-surface p-3 text-sm text-muted"
        >
          Algumas linhas não puderam ser associadas a um município oficial:{" "}
          {map.mapped.unmatched.join(", ")}.
        </p>
      ) : null}

      <div className="grid min-w-0 gap-4 xl:grid-cols-[minmax(0,1fr)_minmax(360px,0.85fr)]">
        <MunicipalityMap
          items={metrics}
          layer={layer}
          selectedCode={query?.municipio ?? ""}
          partialCodes={partialCodes}
          onSelect={(code) => update({ municipio: code })}
        />
        <MunicipalityTable
          items={metrics}
          selectedCode={query?.municipio ?? ""}
          layer={layer}
          partialCodes={partialCodes}
          dataAvailable={Boolean(summaryEnvelope)}
          onSelect={(code) => update({ municipio: code })}
        />
      </div>
      {selected && map.detailRequest && map.detail.isFetching && query ? (
        <p
          role="status"
          className="rounded-lg border border-border bg-surface p-3 text-sm text-muted"
        >
          Carregando série e bairros de {selected.name}…
        </p>
      ) : null}
      {selected && !map.detailRequest && map.catalog.isSuccess ? (
        <p
          role="status"
          className="rounded-lg border border-control bg-surface p-3 text-sm text-muted"
        >
          Os dados detalhados deste município não estão disponíveis nesta
          publicação.
        </p>
      ) : null}
      <MunicipalityPanel
        municipality={selected}
        item={selectedItem}
        detail={detailEnvelope}
        detailError={detailError && !stalePublication}
        query={query}
        layer={layer}
        revenueHref={revenueHref}
        onRetryDetail={() => void map.detail.refetch()}
      />
    </div>
  );
}
