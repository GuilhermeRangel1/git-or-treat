export interface VisualReading {
  summary: string;
  next_step: string;
  observation_ids: string[];
}
export function decodeVisualReading(
  value: unknown,
  ids: string[],
): VisualReading | undefined {
  if (value == null) return undefined;
  const v = value as VisualReading;
  if (
    typeof v !== "object" ||
    Array.isArray(v) ||
    Object.keys(v).some(
      (k) => !["summary", "next_step", "observation_ids"].includes(k),
    ) ||
    typeof v.summary !== "string" ||
    !v.summary.trim() ||
    v.summary.length > 900 ||
    typeof v.next_step !== "string" ||
    !v.next_step.trim() ||
    v.next_step.length > 300 ||
    !Array.isArray(v.observation_ids) ||
    !v.observation_ids.length ||
    v.observation_ids.length > 24 ||
    new Set(v.observation_ids).size !== v.observation_ids.length ||
    v.observation_ids.some((id) => !ids.includes(id))
  )
    throw new Error("Leitura incompatível com as observações do gráfico.");
  return v;
}
