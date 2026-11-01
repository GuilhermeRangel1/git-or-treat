import { decodeGoldMetadata, isGoldMetadata } from "./goldContract";
import type { PanoramaData, PanoramaFilters, KpiMetric } from "./types";

function object(value: unknown): Record<string, unknown> {
  if (!value || typeof value !== "object" || Array.isArray(value))
    throw new Error("Resposta inválida do Panorama.");
  return value as Record<string, unknown>;
}
function finiteOrNull(value: unknown): value is number | null {
  return (
    value === null || (typeof value === "number" && Number.isFinite(value))
  );
}
function stringArray(value: unknown): value is string[] {
  return (
    Array.isArray(value) && value.every((item) => typeof item === "string")
  );
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
const statuses = ["available", "partial", "empty", "unavailable"];

function decodeMetric(value: unknown, gold: boolean): KpiMetric {
  const metric = object(value);
  const fail = () => {
    throw new Error("Resposta inválida do Panorama.");
  };
  for (const field of ["id", "nome", "unidade", "definicao", "formula"])
    if (typeof metric[field] !== "string") fail();
  if (
    !["faturado", "pago", "consumido", "operacao"].includes(
      String(metric.tipoGrandeza),
    ) ||
    !["financeiro", "fisico", "operacional"].includes(
      String(metric.categoria),
    ) ||
    !(gold
      ? finiteOrNull(metric.valorAtual)
      : typeof metric.valorAtual === "number" &&
        Number.isFinite(metric.valorAtual))
  )
    fail();
  for (const field of [
    "valorAnterior",
    "variacaoAbsoluta",
    "variacaoPercentual",
  ])
    if (
      metric[field] != null &&
      (typeof metric[field] !== "number" || !Number.isFinite(metric[field]))
    )
      fail();
  if (gold) {
    if (
      !statuses.includes(String(metric.status)) ||
      !statuses.includes(String(metric.statusComparacao)) ||
      !stringArray(metric.limitacoes) ||
      !stringArray(metric.limitacoesComparacao)
    )
      fail();
    if (metric.status === "available" && metric.valorAtual === null) fail();
    if (
      (metric.status === "empty" || metric.status === "unavailable") &&
      metric.valorAtual !== null
    )
      fail();
    if (metric.statusComparacao === "available" && metric.valorAnterior == null)
      fail();
    if (
      (metric.statusComparacao === "empty" ||
        metric.statusComparacao === "unavailable") &&
      metric.valorAnterior != null
    )
      fail();
  }
  return metric as unknown as KpiMetric;
}

export function decodePanorama(
  value: unknown,
  filters: PanoramaFilters,
  bootstrap = false,
): PanoramaData {
  const envelope = object(value);
  const data = object(envelope.data);
  const gold = isGoldMetadata(envelope.metadata);
  const metadata = gold ? decodeGoldMetadata(envelope.metadata) : undefined;
  const applied = object(data.filtros);
  const metrics = object(data.metricas);
  const fail = () => {
    throw new Error("Resposta inválida do Panorama.");
  };

  if (!gold) {
    for (const key of Object.keys(filters) as (keyof PanoramaFilters)[])
      if (applied[key] !== filters[key]) fail();
  } else if (
    metadata?.source.kind !== "gold" ||
    metadata.source.is_demo ||
    !metadata.fingerprint ||
    metadata.schema_version !== "gold-csv-v2" ||
    metadata.temporal_scope !== "monthly" ||
    applied.comparacao !== filters.comparacao ||
    applied.municipio !== filters.municipio ||
    applied.classe !== filters.classe ||
    typeof applied.periodo !== "string" ||
    (!bootstrap && applied.periodo !== filters.periodo) ||
    metadata.source.version !== data.loteVersao ||
    metadata.period?.start !== applied.periodo ||
    metadata.period?.end !== applied.periodo
  )
    fail();
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

  if (gold) {
    if (!metadata) return fail();
    const expectedMunicipio =
      applied.municipio === "todos" ? null : applied.municipio;
    const expectedClasse = applied.classe === "todas" ? null : applied.classe;
    if (
      metadata.filters.municipio !== expectedMunicipio ||
      metadata.filters.classe !== expectedClasse ||
      metadata.status !==
        ((data.totalRegistros as number) > 0 ? "partial" : "empty")
    )
      fail();
  }

  const decodedMetrics: Record<string, KpiMetric> = {};
  for (const key of metricKeys)
    decodedMetrics[key] = decodeMetric(metrics[key], gold);
  if (gold)
    decodedMetrics.ucsFaturadasNoMes = decodeMetric(
      metrics.ucsFaturadasNoMes,
      true,
    );
  const serieMensal = (data.serieMensal as unknown[]).map((point) => {
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
      if (
        gold
          ? !finiteOrNull(row[key])
          : typeof row[key] !== "number" || !Number.isFinite(row[key] as number)
      )
        fail();
    if (gold && !statuses.includes(String(row.status))) fail();
    if (
      gold &&
      row.status === "available" &&
      row.receitaFaturada === null &&
      row.energiaConsumidaKwh === null
    )
      fail();
    return row as unknown as PanoramaData["serieMensal"][number];
  });
  let opcoesFiltros;
  if (gold) {
    const options = object(data.opcoesFiltros);
    if (
      !stringArray(options.competencias) ||
      !stringArray(options.municipios) ||
      !stringArray(options.classes)
    )
      fail();
    opcoesFiltros = {
      competencias: options.competencias as string[],
      municipios: options.municipios as string[],
      classes: options.classes as string[],
    };
  }
  const normalizedFilters = gold
    ? {
        periodo: applied.periodo as string,
        comparacao: applied.comparacao as PanoramaFilters["comparacao"],
        municipio: applied.municipio as string,
        classe: applied.classe as string,
      }
    : filters;
  return {
    filtros: normalizedFilters,
    periodoIncompleto: data.periodoIncompleto as boolean,
    fechamentoMensalDeclarado: gold
      ? data.fechamentoMensalDeclarado === true
      : undefined,
    totalRegistros: data.totalRegistros as number,
    dataAtualizacao:
      metadata?.source.updated_at ?? (data.dataAtualizacao as string),
    loteVersao: metadata?.source.version ?? (data.loteVersao as string),
    metricas: decodedMetrics as PanoramaData["metricas"],
    serieMensal,
    opcoesFiltros,
    origem: metadata
      ? {
          kind: "gold",
          isDemo: false,
          version: metadata.source.version,
          fingerprint: metadata.fingerprint,
          schemaVersion: metadata.schema_version,
          contractVersion: metadata.contract_version,
          temporalScope: metadata.temporal_scope,
          limitations: metadata.limitations,
        }
      : {
          kind: "synthetic",
          isDemo: true,
          version: data.loteVersao as string,
          contractVersion: "synthetic",
          limitations: [],
        },
  };
}
