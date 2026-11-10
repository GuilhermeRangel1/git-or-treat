import { useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import { X } from "lucide-react";
import * as L from "leaflet";
import "leaflet/dist/leaflet.css";
import type { MunicipalityMetric } from "./contract";
import { decodeTerritoryMap, type TerritoryMapGeoJSON } from "./contract";
import { classifyMapValues } from "./map-scale";
import { valueForLayer } from "./map-values";
import type { MapLayer } from "./map-state";
import { fitView, prefersReducedMotion } from "./map-view";
import "./map.css";

type Props = {
  items: MunicipalityMetric[];
  layer: MapLayer;
  selectedCode: string;
  partialCodes: ReadonlySet<string>;
  onSelect: (code: string) => void;
  onClearSelection?: () => void;
};

export default function MunicipalityMap({
  items,
  layer,
  selectedCode,
  partialCodes,
  onSelect,
  onClearSelection,
}: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<L.Map | null>(null);
  const layerRef = useRef<L.GeoJSON | null>(null);
  const selectRef = useRef(onSelect);
  const [geojson, setGeojson] = useState<TerritoryMapGeoJSON | null>(null);
  const [geoError, setGeoError] = useState(false);
  const [mapReady, setMapReady] = useState(false);
  const itemByCode = useMemo(
    () => new Map(items.map((item) => [item.municipality.code, item])),
    [items],
  );
  const scale = useMemo(
    () =>
      classifyMapValues(
        items.map((item) => valueForLayer(item.item, layer)),
        layer.endsWith("change") ? "diverging" : "absolute",
        partialCodes,
      ),
    [items, layer, partialCodes],
  );
  const visualRef = useRef({
    itemByCode,
    scale,
    layer,
    selectedCode,
    partialCodes,
  });
  useLayoutEffect(() => {
    visualRef.current = {
      itemByCode,
      scale,
      layer,
      selectedCode,
      partialCodes,
    };
    selectRef.current = onSelect;
  }, [itemByCode, scale, layer, selectedCode, partialCodes, onSelect]);

  useEffect(() => {
    let active = true;
    fetch("/geography/rmr.geojson")
      .then((response) => {
        if (!response.ok) throw new Error("GeoJSON indisponível");
        return response.json() as Promise<unknown>;
      })
      .then((value) => {
        if (active) setGeojson(decodeTerritoryMap(value));
      })
      .catch(() => {
        if (active) setGeoError(true);
      });
    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;
    const map = L.map(container, {
      zoomControl: true,
      scrollWheelZoom: false,
      preferCanvas: false,
      keyboard: true,
      attributionControl: false,
    });
    mapRef.current = map;
    setMapReady(true);
    const onResize = () => {
      map.invalidateSize({ pan: false, debounceMoveend: true });
      // O enquadramento pode ter sido calculado antes do layout assentar
      // (barra lateral, rolagem): refaz para o mapa nunca ficar cortado.
      fitView(map, layerRef.current, visualRef.current.selectedCode, false);
    };
    const resizeObserver =
      typeof ResizeObserver === "undefined"
        ? null
        : new ResizeObserver(onResize);
    if (resizeObserver) resizeObserver.observe(container);
    else window.addEventListener("resize", onResize, { passive: true });
    return () => {
      if (resizeObserver) resizeObserver.disconnect();
      else window.removeEventListener("resize", onResize);
      layerRef.current?.remove();
      layerRef.current = null;
      map.remove();
      mapRef.current = null;
      setMapReady(false);
    };
  }, []);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !geojson) return;
    layerRef.current?.remove();
    const keyboardHandlers: Array<{
      element: Element;
      handler: EventListener;
    }> = [];
    const polygons = L.geoJSON(geojson as GeoJSON.GeoJsonObject, {
      style: (feature) => {
        const code = String(feature?.properties?.code ?? "");
        const visual = visualRef.current;
        const result = visual.scale.classify(
          valueForLayer(
            visual.itemByCode.get(code)?.item ?? null,
            visual.layer,
          ),
          code,
        );
        const selected = code === visual.selectedCode;
        return {
          color: selected ? "var(--accent-goiaba)" : "var(--border-control)",
          weight: selected ? 3 : 1,
          opacity: 1,
          fillColor: `var(${result.color})`,
          fillOpacity: selected ? 0.9 : 0.76,
          lineCap: "round",
          lineJoin: "round",
        };
      },
      onEachFeature: (feature, polygon) => {
        const code = String(feature.properties?.code ?? "");
        const name = String(feature.properties?.name ?? "Município");
        const tooltip = document.createElement("span");
        tooltip.textContent = name;
        polygon.bindTooltip(tooltip, {
          sticky: true,
          direction: "top",
          opacity: 0.96,
        });
        const select = () => {
          selectRef.current(code);
          // A seleção muda a URL e o efeito abaixo enquadra o município. Se ele
          // já estava selecionado, não há mudança de URL: enquadra aqui.
          if (code === visualRef.current.selectedCode)
            fitView(map, layerRef.current, code, !prefersReducedMotion());
        };
        polygon.on("click", select);
        polygon.on("add", () => {
          if (!(polygon instanceof L.Path)) return;
          const element = polygon.getElement();
          if (!element) return;
          element.setAttribute("tabindex", "0");
          element.setAttribute("role", "button");
          element.setAttribute(
            "aria-label",
            `${name}${visualRef.current.selectedCode === code ? ", selecionado" : ""}`,
          );
          const handler: EventListener = (event) => {
            const keyboard = event as KeyboardEvent;
            if (keyboard.key === "Enter" || keyboard.key === " ") {
              keyboard.preventDefault();
              select();
            }
          };
          element.addEventListener("keydown", handler);
          keyboardHandlers.push({ element, handler });
        });
      },
    }).addTo(map);
    layerRef.current = polygons;
    fitView(map, polygons, "", !prefersReducedMotion());
    return () => {
      keyboardHandlers.forEach(({ element, handler }) =>
        element.removeEventListener("keydown", handler),
      );
      polygons.remove();
    };
  }, [geojson]);

  useEffect(() => {
    const polygons = layerRef.current;
    if (!polygons) return;
    polygons.setStyle((feature) => {
      const code = String(feature?.properties?.code ?? "");
      const result = scale.classify(
        valueForLayer(itemByCode.get(code)?.item ?? null, layer),
        code,
      );
      const selected = code === selectedCode;
      return {
        color: selected ? "var(--accent-goiaba)" : "var(--border-control)",
        weight: selected ? 3 : 1,
        opacity: 1,
        fillColor: `var(${result.color})`,
        fillOpacity: selected ? 0.9 : 0.76,
      };
    });
    polygons.eachLayer((polygon) => {
      const feature = (polygon as L.Layer & { feature?: GeoJSON.Feature })
        .feature;
      const code = String(feature?.properties?.code ?? "");
      const name = String(feature?.properties?.name ?? "Município");
      if (polygon instanceof L.Path)
        polygon
          .getElement()
          ?.setAttribute(
            "aria-label",
            `${name}${selectedCode === code ? ", selecionado" : ""}`,
          );
    });
  }, [itemByCode, layer, scale, selectedCode]);

  // Escolher um município (no mapa, na lista ou por link) enquadra aquele
  // município; limpar a seleção volta a mostrar a RMR inteira.
  const previousSelected = useRef(selectedCode);
  useEffect(() => {
    const had = previousSelected.current;
    previousSelected.current = selectedCode;
    const map = mapRef.current;
    if (!map || (!selectedCode && !had)) return;
    fitView(map, layerRef.current, selectedCode, !prefersReducedMotion());
  }, [selectedCode, geojson]);

  function resetBounds() {
    const map = mapRef.current;
    if (map) fitView(map, layerRef.current, "", !prefersReducedMotion());
  }

  return (
    <section
      className="rmr-map-panel min-w-0 overflow-hidden rounded-xl border border-border bg-surface"
      aria-label="Mapa interativo da Região Metropolitana do Recife"
    >
      <div className="flex min-h-14 items-center justify-between gap-3 border-b border-border px-4 py-2">
        <div>
          <h2 className="font-heading text-sm font-semibold text-content">
            Região Metropolitana do Recife
          </h2>
          <p className="text-xs text-muted">Contornos municipais da RMR</p>
        </div>
        <div className="flex shrink-0 items-center gap-2">
          {selectedCode && onClearSelection ? (
            <button
              type="button"
              className="inline-flex min-h-10 items-center gap-1.5 rounded-lg border border-control px-3 text-xs font-medium text-content hover:bg-surface-hover focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand"
              onClick={onClearSelection}
            >
              <X aria-hidden="true" className="size-4" />
              Limpar seleção
            </button>
          ) : null}
          <button
            type="button"
            className="min-h-10 shrink-0 rounded-lg border border-control px-3 text-xs font-medium text-content hover:bg-surface-hover focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand"
            onClick={resetBounds}
            disabled={!mapReady}
          >
            Enquadrar RMR
          </button>
        </div>
      </div>
      <div
        ref={containerRef}
        className="rmr-map"
        role="application"
        aria-label="Mapa. Use a lista acessível para selecionar municípios."
      />
      <details className="border-t border-border px-4 py-2 text-[11px] leading-4 text-muted">
        <summary className="cursor-pointer select-none">
          Fonte dos contornos
        </summary>
        <p className="mt-1">
          Contornos municipais: IBGE, Malhas Territoriais Municipais 2022. A
          região segue a composição metropolitana após a LC-PE 426/2020;
          atualização legal mais recente consultada em 2026.
        </p>
      </details>
      {geoError ? (
        <p
          role="status"
          className="border-t border-border px-4 py-3 text-sm text-muted"
        >
          A geometria local não está disponível. A lista e os dados analíticos
          continuam disponíveis.
        </p>
      ) : null}
    </section>
  );
}
