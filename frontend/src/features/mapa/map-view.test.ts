import * as L from "leaflet";
import { describe, expect, it, vi } from "vitest";
import { fitView } from "./map-view";

function square(code: string, west: number, south: number) {
  return {
    type: "Feature",
    properties: { code, name: code },
    geometry: {
      type: "Polygon",
      coordinates: [
        [
          [west, south],
          [west, south + 1],
          [west + 1, south + 1],
          [west + 1, south],
          [west, south],
        ],
      ],
    },
  };
}

// A ocupa lng 0–1 / lat 0–1; B ocupa lng 10–11 / lat 10–11.
const regions = L.geoJSON({
  type: "FeatureCollection",
  features: [square("A", 0, 0), square("B", 10, 10)],
} as GeoJSON.GeoJsonObject);

function fakeMap() {
  const fitBounds = vi.fn();
  return { map: { fitBounds } as unknown as L.Map, fitBounds };
}

describe("fitView", () => {
  it("enquadra o município selecionado, e não a região inteira", () => {
    const { map, fitBounds } = fakeMap();
    fitView(map, regions, "B", true);

    const [bounds, options] = fitBounds.mock.calls[0] as [
      L.LatLngBounds,
      L.FitBoundsOptions,
    ];
    expect([bounds.getWest(), bounds.getEast()]).toEqual([10, 11]);
    expect([bounds.getSouth(), bounds.getNorth()]).toEqual([10, 11]);
    expect(options).toEqual({ padding: [18, 18], maxZoom: 10, animate: true });
  });

  it("sem seleção, mostra a região inteira", () => {
    const { map, fitBounds } = fakeMap();
    fitView(map, regions, "", false);

    const [bounds, options] = fitBounds.mock.calls[0] as [
      L.LatLngBounds,
      L.FitBoundsOptions,
    ];
    expect([bounds.getWest(), bounds.getEast()]).toEqual([0, 11]);
    expect([bounds.getSouth(), bounds.getNorth()]).toEqual([0, 11]);
    expect(options).toEqual({ padding: [20, 20], maxZoom: 9, animate: false });
  });

  it("volta à região inteira quando o município não existe na malha", () => {
    const { map, fitBounds } = fakeMap();
    fitView(map, regions, "inexistente", false);

    const [bounds] = fitBounds.mock.calls[0] as [L.LatLngBounds];
    expect([bounds.getWest(), bounds.getEast()]).toEqual([0, 11]);
  });

  it("não faz nada enquanto a malha não carregou", () => {
    const { map, fitBounds } = fakeMap();
    fitView(map, null, "A", true);
    expect(fitBounds).not.toHaveBeenCalled();
  });
});
