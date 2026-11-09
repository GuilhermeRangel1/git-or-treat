import { signedCompactMoney, signedMoney } from "./revenue-diagnosis-format";

export type DiagnosisColumn = {
  label: string;
  value: number;
  /** Coluna de total: tom um pouco mais forte, e o valor acompanha a cor do sinal. */
  emphasis?: boolean;
};

function barClass({ value, emphasis }: DiagnosisColumn) {
  if (value === 0) return "bg-muted/70";
  if (value > 0) return emphasis ? "bg-success/70" : "bg-success/50";
  return emphasis ? "bg-danger/70" : "bg-danger/50";
}

function valueClass({ value, emphasis }: DiagnosisColumn) {
  if (!emphasis || value === 0) return "text-content";
  return value > 0
    ? "text-[var(--status-success-text)]"
    : "text-[var(--action-danger-text)]";
}

function Column({
  column,
  zero,
  span,
}: {
  column: DiagnosisColumn;
  zero: number;
  span: number;
}) {
  const height = span > 0 ? (Math.abs(column.value) / span) * 100 : 0;
  const exact = `${column.label}: ${signedMoney(column.value)}`;
  return (
    <div role="img" aria-label={exact} title={exact}>
      <div className="relative h-36">
        <div className="absolute inset-x-0 bottom-6 top-6">
          <div
            className="absolute inset-x-0 h-px bg-control"
            style={{ top: `${zero}%` }}
          />
          <div
            data-column-bar=""
            className={`absolute left-1/2 min-h-0.5 w-10 -translate-x-1/2 sm:w-14 ${column.value < 0 ? "rounded-b-sm" : "rounded-t-sm"} ${barClass(column)}`}
            style={
              column.value < 0
                ? { top: `${zero}%`, height: `${height}%` }
                : { bottom: `${100 - zero}%`, height: `${height}%` }
            }
          >
            <span
              className={`absolute left-1/2 -translate-x-1/2 whitespace-nowrap text-xs font-medium ${valueClass(column)} ${column.value < 0 ? "top-full mt-1" : "bottom-full mb-1"}`}
            >
              {signedCompactMoney(column.value)}
            </span>
          </div>
        </div>
      </div>
      <p className="px-1 text-center text-xs font-medium text-muted">
        {column.label}
      </p>
    </div>
  );
}

/** Todas as colunas partem da mesma linha de zero, na mesma escala e sem acumular. */
export default function PanoramaDiagnosisColumns({
  columns,
}: {
  columns: DiagnosisColumn[];
}) {
  const highest = Math.max(0, ...columns.map((column) => column.value));
  const lowest = Math.max(0, ...columns.map((column) => -column.value));
  const span = highest + lowest;
  const zero = span > 0 ? (highest / span) * 100 : 100;

  return (
    <div
      className="grid"
      style={{
        gridTemplateColumns: `repeat(${columns.length}, minmax(0, 1fr))`,
      }}
    >
      {columns.map((column) => (
        <Column key={column.label} column={column} zero={zero} span={span} />
      ))}
    </div>
  );
}
