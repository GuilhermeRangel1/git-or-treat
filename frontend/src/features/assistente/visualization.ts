import type { AIAnalysisContext } from "./contract";
import {
  decodeVisualReading,
  type VisualReading,
} from "@/shared/analytics/visualReading";
export interface ChatVisualPoint {
  observation_id: string;
  label: string;
  value: number;
}
export interface ChatVisualization {
  reading?: VisualReading | null;
  total?: number | null;
  sectors?:
    | {
        label: string;
        value: number;
        percentage: number;
        observation_ids: string[];
      }[]
    | null;
  contract_version: "v1";
  kind: "bars" | "horizontal" | "line" | "donut";
  metric: string;
  title: string;
  unit: string;
  precision: number;
  dimension_ids: string[];
  period: string;
  category_label: string;
  note: string;
  points: ChatVisualPoint[];
  plot_points: ChatVisualPoint[];
}
export function decodeChatVisualization(
  value: unknown,
  context: AIAnalysisContext | null | undefined,
): ChatVisualization | undefined {
  if (value == null) return undefined;
  const fail = (): never => {
    throw new Error("Visualização incompatível com a resposta.");
  };
  if (typeof value !== "object" || Array.isArray(value)) return fail();
  const v = value as ChatVisualization;
  const allowed = [
    "contract_version",
    "kind",
    "metric",
    "title",
    "unit",
    "precision",
    "dimension_ids",
    "period",
    "category_label",
    "note",
    "points",
    "plot_points",
    "reading",
    "total",
    "sectors",
  ];
  if (
    Object.keys(v).some((k) => !allowed.includes(k)) ||
    v.contract_version !== "v1" ||
    !Number.isInteger(v.precision) ||
    v.precision < 0 ||
    v.precision > 6 ||
    !["bars", "horizontal", "line", "donut"].includes(v.kind) ||
    !context?.batch_reference?.startsWith("gold-csv-v2:") ||
    v.metric !== context.metric ||
    v.unit !== context.unit ||
    v.period !== context.period
  )
    return fail();
  if (
    [v.metric, v.title, v.unit, v.period, v.category_label, v.note].some(
      (s) => typeof s !== "string" || !s.trim() || s.length > 300,
    )
  )
    return fail();
  if (
    !Array.isArray(v.dimension_ids) ||
    v.dimension_ids.length > 10 ||
    new Set(v.dimension_ids).size !== v.dimension_ids.length ||
    v.dimension_ids.some(
      (id) =>
        typeof id !== "string" ||
        !/^[a-z][a-z0-9]*(?:[._:-][a-z0-9]+)*$/.test(id) ||
        id.length > 120,
    ) ||
    Object.keys(context.filters).some((id) => !v.dimension_ids.includes(id))
  )
    return fail();
  const points = (raw: unknown, limit: number): ChatVisualPoint[] => {
    if (!Array.isArray(raw) || !raw.length || raw.length > limit) return fail();
    return raw.map((p) => {
      if (
        !p ||
        typeof p !== "object" ||
        Object.keys(p).some(
          (k) => !["observation_id", "label", "value"].includes(k),
        ) ||
        typeof p.observation_id !== "string" ||
        !/^row_[1-9][0-9]{0,2}$/.test(p.observation_id) ||
        typeof p.label !== "string" ||
        !p.label.trim() ||
        p.label.length > 200 ||
        typeof p.value !== "number" ||
        !Number.isFinite(p.value)
      )
        return fail();
      return p as ChatVisualPoint;
    });
  };
  const all = points(v.points, 100);
  const plot = points(v.plot_points, v.kind === "donut" ? 100 : 24);
  if (
    all.some((p, i) => p.observation_id !== `row_${i + 1}`) ||
    new Set(plot.map((p) => p.observation_id)).size !== plot.length ||
    plot.some(
      (p) =>
        !all.some(
          (a) =>
            a.observation_id === p.observation_id &&
            a.label === p.label &&
            a.value === p.value,
        ),
    )
  )
    return fail();
  if (
    v.kind === "donut" &&
    (!["billing.revenue", "energy.consumption"].includes(v.metric) ||
      all.length < 2 ||
      plot.length !== all.length ||
      new Set(all.map((p) => p.label)).size !== all.length ||
      all.some((p) => p.value < 0) ||
      !(all.reduce((sum, p) => sum + p.value, 0) > 0) ||
      !Number.isFinite(all.reduce((sum, p) => sum + p.value, 0)))
  )
    return fail();
  if (v.kind === "donut") {
    const total = all.reduce((sum, p) => sum + p.value, 0);
    if (
      typeof v.total !== "number" ||
      !Number.isFinite(v.total) ||
      Math.abs(v.total - total) > total * 1e-12 ||
      !Array.isArray(v.sectors) ||
      !v.sectors.length ||
      v.sectors.length > 6
    )
      return fail();
    const ids: string[] = [];
    for (const sector of v.sectors) {
      if (
        !sector ||
        typeof sector !== "object" ||
        Object.keys(sector).some(
          (k) =>
            !["label", "value", "percentage", "observation_ids"].includes(k),
        ) ||
        typeof sector.label !== "string" ||
        !sector.label.trim() ||
        sector.label.length > 200 ||
        typeof sector.value !== "number" ||
        !Number.isFinite(sector.value) ||
        sector.value < 0 ||
        typeof sector.percentage !== "number" ||
        !Number.isFinite(sector.percentage) ||
        sector.percentage < 0 ||
        sector.percentage > 100 ||
        !Array.isArray(sector.observation_ids) ||
        !sector.observation_ids.length ||
        sector.observation_ids.some(
          (id) => !all.some((p) => p.observation_id === id),
        )
      )
        return fail();
      const amount = sector.observation_ids.reduce(
        (sum, id) => sum + all.find((p) => p.observation_id === id)!.value,
        0,
      );
      if (
        Math.abs(sector.value - amount) > total * 1e-12 ||
        Math.abs(sector.percentage - (amount / total) * 100) > 1e-8
      )
        return fail();
      ids.push(...sector.observation_ids);
    }
    if (ids.length !== all.length || new Set(ids).size !== ids.length)
      return fail();
  } else if (v.total != null || v.sectors != null) return fail();
  return {
    ...v,
    points: all,
    plot_points: plot,
    reading: decodeVisualReading(
      v.reading,
      plot.map((p) => p.observation_id),
    ),
  };
}

/** Reutiliza a rosca do portal; tabela e CSV conservam cada grupo da consulta. */
export function chatChartPoints(
  visual: ChatVisualization,
  label: (value: string) => string,
) {
  const tablePoints = visual.points.map((p) => ({
    label: label(p.label),
    value: p.value,
  }));
  if (visual.kind !== "donut")
    return {
      points: visual.plot_points.map((p) => ({
        label: label(p.label),
        value: p.value,
      })),
      tablePoints,
    };
  return {
    total: visual.total!,
    points: visual.sectors!.map((p) => ({
      label: label(p.label),
      value: p.value,
      percentage: p.percentage,
    })),
    tablePoints,
  };
}
