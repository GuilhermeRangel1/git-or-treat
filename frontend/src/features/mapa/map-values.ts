import type { MunicipalityMetric } from "./contract";
import type { MapLayer } from "./map-state";

export function valueForLayer(
  item: MunicipalityMetric["item"],
  layer: MapLayer,
) {
  if (!item) return null;
  const comparison = item.comparison;
  switch (layer) {
    case "revenue":
      return comparison.final.billed_amount;
    case "consumption":
      return comparison.final.measured_energy_kwh;
    case "revenue_change":
      return comparison.billed_amount_change_brl;
    case "consumption_change":
      return comparison.measured_energy_change_kwh;
  }
}
