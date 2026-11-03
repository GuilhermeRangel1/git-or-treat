import type { KpiMetric, PanoramaDistribution, PanoramaFilters } from "./types";
import { decodeVisualReading } from "./visualReading";

export function decodeDistribution(
  value: unknown,
  filters: PanoramaFilters,
  metric: KpiMetric,
): PanoramaDistribution | null {
  if (value == null) return null;
  const fail = (): never => {
    throw new Error("Distribuição incompatível com o Panorama.");
  };
  if (typeof value !== "object" || Array.isArray(value)) return fail();
  const v = value as PanoramaDistribution;
  if (
    Object.keys(v).some(
      (k) =>
        ![
          "dimension",
          "periodo",
          "metricId",
          "unidade",
          "total",
          "completo",
          "pontos",
          "visual",
          "agrupados",
          "reading",
        ].includes(k),
    )
  )
    return fail();
  const dimension =
    filters.municipio === "todos"
      ? "municipio"
      : filters.classe === "todas"
        ? "classe"
        : null;
  if (
    !dimension ||
    v.dimension !== dimension ||
    v.periodo !== filters.periodo ||
    v.metricId !== metric.id ||
    v.unidade !== metric.unidade ||
    typeof v.total !== "number" ||
    !Number.isFinite(v.total) ||
    v.total !== metric.valorAtual ||
    typeof v.completo !== "boolean" ||
    !Array.isArray(v.pontos) ||
    v.pontos.length < 2 ||
    v.pontos.length > 1000
  )
    return fail();
  if (
    v.pontos.some(
      (p) =>
        !p ||
        Object.keys(p).some(
          (k) => !["segmento", "valor", "percentual"].includes(k),
        ) ||
        typeof p.segmento !== "string" ||
        !p.segmento.trim() ||
        p.segmento.length > 120 ||
        (p.valor !== null &&
          (typeof p.valor !== "number" || !Number.isFinite(p.valor))) ||
        (p.percentual !== null &&
          (typeof p.percentual !== "number" ||
            !Number.isFinite(p.percentual) ||
            p.percentual < 0 ||
            p.percentual > 100)),
    )
  )
    return fail();
  if (new Set(v.pontos.map((p) => p.segmento)).size !== v.pontos.length)
    return fail();
  // Numeric reconciliation checks the server payload; it does not create business values.
  const sum = v.pontos.reduce((n, p) => n + (p.valor ?? 0), 0);
  if (
    Math.abs(sum - v.total) >
    Math.max(0.005, Math.abs(v.total) * Number.EPSILON * v.pontos.length)
  )
    return fail();
  if (v.completo) {
    if (
      v.total <= 0 ||
      v.pontos.some(
        (p) =>
          p.valor === null ||
          p.valor < 0 ||
          p.percentual === null ||
          Math.abs(p.percentual - (p.valor / v.total) * 100) > 0.011,
      )
    )
      return fail();
  } else if (v.pontos.some((p) => p.percentual !== null)) return fail();
  if (v.visual !== undefined) {
    if (
      !Array.isArray(v.visual) ||
      v.visual.length < 2 ||
      v.visual.length > 10 ||
      !Number.isInteger(v.agrupados) ||
      (v.agrupados ?? 0) < 0
    )
      return fail();
    const grouped = v.agrupados ?? 0;
    if (
      grouped > 0 &&
      (!v.completo ||
        v.pontos.length <= 6 ||
        v.visual.length !== 6 ||
        grouped !== v.pontos.length - 5)
    )
      return fail();
    const individual = grouped > 0 ? v.visual.slice(0, 5) : v.visual;
    if (
      individual.some(
        (p, i) =>
          !p ||
          p.segmento !== v.pontos[i].segmento ||
          p.valor !== v.pontos[i].valor ||
          p.percentual !== v.pontos[i].percentual,
      )
    )
      return fail();
    if (
      !grouped &&
      v.visual.length !==
        Math.min(v.pontos.length, v.pontos.length <= 6 ? 6 : 10)
    )
      return fail();
    if (grouped) {
      const last = v.visual[5];
      const label =
        v.dimension === "municipio"
          ? `Demais municípios (${grouped})`
          : `Demais classes (${grouped})`;
      const rest = v.pontos.slice(5).reduce((n, p) => n + (p.valor ?? 0), 0);
      if (
        !last ||
        last.segmento !== label ||
        typeof last.valor !== "number" ||
        !Number.isFinite(last.valor) ||
        Math.abs(last.valor - rest) >
          Math.max(0.005, Math.abs(rest) * Number.EPSILON * v.pontos.length) ||
        typeof last.percentual !== "number" ||
        !Number.isFinite(last.percentual) ||
        Math.abs(last.percentual - (rest / v.total) * 100) > 0.011
      )
        return fail();
    }
  } else if (v.pontos.length > 24) return fail();
  return {
    ...v,
    reading: decodeVisualReading(
      v.reading,
      (v.visual ?? v.pontos).map((_, i) => `row_${i + 1}`),
    ),
  };
}
