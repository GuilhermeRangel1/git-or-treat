import { formatNumber } from "./format";

export default function PriorityScore({ value }: { value: number }) {
  return (
    <div className="min-w-24 space-y-2">
      <p className="whitespace-nowrap font-mono text-base font-semibold text-brand">
        {formatNumber(value)}{" "}
        <span className="text-xs font-normal text-muted">/ 1</span>
      </p>
      <div
        role="meter"
        aria-label="Pontuação sintética de prioridade"
        aria-valuenow={value}
        aria-valuemin={0}
        aria-valuemax={1}
        className="h-1.5 overflow-hidden rounded-full bg-selected"
      >
        <div
          className="h-full rounded-full bg-brand"
          style={{ width: `${value * 100}%` }}
        />
      </div>
    </div>
  );
}
