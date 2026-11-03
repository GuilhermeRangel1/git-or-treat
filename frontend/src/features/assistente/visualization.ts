import type { AIAnalysisContext } from "./contract";
export interface ChatVisualPoint {
  observation_id: string;
  label: string;
  value: number;
}
export interface ChatVisualization {
  contract_version: "v1";
  kind: "bars" | "horizontal" | "line";
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
  ];
  if (
    Object.keys(v).some((k) => !allowed.includes(k)) ||
    v.contract_version !== "v1" ||
    !Number.isInteger(v.precision) ||
    v.precision < 0 ||
    v.precision > 6 ||
    !["bars", "horizontal", "line"].includes(v.kind) ||
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
  const plot = points(v.plot_points, 24);
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
  return { ...v, points: all, plot_points: plot };
}
