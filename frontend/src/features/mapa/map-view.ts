import * as L from "leaflet";

export function prefersReducedMotion() {
  return Boolean(
    window.matchMedia?.("(prefers-reduced-motion: reduce)").matches,
  );
}

/**
 * Decide o que o mapa mostra: o município selecionado (se ele existir na
 * malha) ou a RMR inteira. Clique no mapa, clique na lista, link com município,
 * "Limpar seleção" e redimensionamento passam todos por aqui e dão o mesmo
 * enquadramento.
 */
export function fitView(
  map: L.Map,
  polygons: L.GeoJSON | null,
  selectedCode: string,
  animate: boolean,
) {
  if (!polygons) return;
  const found: L.LatLngBounds[] = [];
  if (selectedCode) {
    polygons.eachLayer((layer) => {
      const feature = (layer as L.Layer & { feature?: GeoJSON.Feature })
        .feature;
      if (
        layer instanceof L.Polygon &&
        String(feature?.properties?.code ?? "") === selectedCode
      )
        found.push(layer.getBounds());
    });
  }
  const selected = found[0];
  const bounds = selected ?? polygons.getBounds();
  if (!bounds.isValid()) return;
  map.fitBounds(
    bounds,
    selected
      ? { padding: [18, 18], maxZoom: 10, animate }
      : { padding: [20, 20], maxZoom: 9, animate },
  );
}
