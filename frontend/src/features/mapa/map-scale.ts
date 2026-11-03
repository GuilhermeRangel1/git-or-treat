export type MapValueState = "observed" | "partial" | "missing";
export type ScaleMode = "absolute" | "diverging";

export type MapClassification = {
  state: MapValueState;
  color: string;
  label: string;
};

const sequential = [
  "--map-seq-1",
  "--map-seq-2",
  "--map-seq-3",
  "--map-seq-4",
  "--map-seq-5",
];
const negative = ["--map-neg-1", "--map-neg-2", "--map-neg-3", "--map-neg-4"];
const positive = ["--map-pos-1", "--map-pos-2", "--map-pos-3", "--map-pos-4"];
const missing = "--map-missing";

export function classifyMapValues(
  values: readonly (number | null)[],
  mode: ScaleMode,
  partialCodes: ReadonlySet<string> = new Set(),
) {
  const observed = values.filter(
    (value): value is number =>
      typeof value === "number" && Number.isFinite(value),
  );
  const min = observed.length ? Math.min(...observed) : null;
  const max = observed.length ? Math.max(...observed) : null;
  const absoluteBound = observed.reduce(
    (bound, value) => Math.max(bound, Math.abs(value)),
    0,
  );
  const domainMin =
    mode === "diverging" && observed.length ? -absoluteBound : min;
  const domainMax =
    mode === "diverging" && observed.length ? absoluteBound : max;
  const indexFor = (value: number, colors: readonly string[]) => {
    if (max === min) return Math.floor((colors.length - 1) / 2);
    const ratio =
      mode === "diverging"
        ? Math.min(1, Math.abs(value) / (absoluteBound || 1))
        : Math.min(
            1,
            Math.max(
              0,
              (value - (min ?? value)) / ((max ?? value) - (min ?? value)),
            ),
          );
    return mode === "diverging"
      ? Math.min(
          colors.length - 1,
          Math.max(0, Math.ceil(ratio * colors.length) - 1),
        )
      : Math.min(colors.length - 1, Math.floor(ratio * colors.length));
  };

  return {
    min,
    max,
    domainMin,
    domainMax,
    mode,
    classify(value: number | null, code?: string): MapClassification {
      if (value === null || !Number.isFinite(value))
        return { state: "missing", color: missing, label: "Sem observação" };
      if (value === 0) {
        return {
          state: code && partialCodes.has(code) ? "partial" : "observed",
          color: "--map-zero",
          label:
            code && partialCodes.has(code)
              ? "Zero observado · cobertura parcial"
              : "Zero observado",
        };
      }
      if (code && partialCodes.has(code)) {
        const colors =
          mode === "diverging" ? (value < 0 ? negative : positive) : sequential;
        return {
          state: "partial",
          color: colors[indexFor(value, colors)],
          label: "Valor observado · cobertura parcial",
        };
      }
      if (mode === "diverging") {
        const colors = value < 0 ? negative : positive;
        return {
          state: "observed",
          color: colors[indexFor(value, colors)],
          label: value < 0 ? "Queda observada" : "Alta observada",
        };
      }
      return {
        state: "observed",
        color: sequential[indexFor(value, sequential)],
        label: "Valor observado",
      };
    },
  };
}
