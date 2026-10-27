import type { PanoramaData, PanoramaFilters } from "./types";

function object(value: unknown): Record<string, unknown> {
  if (!value || typeof value !== "object" || Array.isArray(value))
    throw new Error("Resposta inválida do Panorama.");
  return value as Record<string, unknown>;
}
function finite(value: unknown) {
  return typeof value === "number" && Number.isFinite(value);
}
const metricKeys = [
  "receitaFaturada",
  "receitaPaga",
  "energiaConsumida",
  "energiaFaturada",
  "precoMedioEfetivo",
  "ucsAtivas",
  "continuidadeDec",
  "continuidadeFec",
];
export function decodePanorama(
  value: unknown,
  filters: PanoramaFilters,
): PanoramaData {
  const data = object(object(value).data);
  const applied = object(data.filtros);
  const metrics = object(data.metricas);
  const fail = () => {
    throw new Error("Resposta inválida do Panorama.");
  };
  for (const key of Object.keys(filters) as (keyof PanoramaFilters)[])
    if (applied[key] !== filters[key]) fail();
  if (
    !Number.isInteger(data.totalRegistros) ||
    (data.totalRegistros as number) < 0 ||
    typeof data.periodoIncompleto !== "boolean" ||
    typeof data.loteVersao !== "string" ||
    typeof data.dataAtualizacao !== "string" ||
    !Number.isFinite(Date.parse(data.dataAtualizacao)) ||
    !Array.isArray(data.serieMensal)
  )
    fail();
  for (const key of metricKeys) {
    const metric = object(metrics[key]);
    for (const field of ["id", "nome", "unidade", "definicao", "formula"])
      if (typeof metric[field] !== "string") fail();
    if (
      !["faturado", "pago", "consumido", "operacao"].includes(
        String(metric.tipoGrandeza),
      ) ||
      !["financeiro", "fisico", "operacional"].includes(
        String(metric.categoria),
      ) ||
      !finite(metric.valorAtual)
    )
      fail();
    for (const field of [
      "valorAnterior",
      "variacaoAbsoluta",
      "variacaoPercentual",
    ])
      if (metric[field] != null && !finite(metric[field])) fail();
  }
  for (const point of data.serieMensal as unknown[]) {
    const row = object(point);
    if (typeof row.competencia !== "string" || typeof row.label !== "string")
      fail();
    for (const key of [
      "receitaFaturada",
      "receitaPaga",
      "energiaConsumidaKwh",
      "energiaFaturadaKwh",
      "ucsAtivas",
      "decHoras",
      "fecVezes",
    ])
      if (!finite(row[key])) fail();
  }
  return data as unknown as PanoramaData;
}
