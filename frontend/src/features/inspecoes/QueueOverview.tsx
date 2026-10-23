import { ClipboardList, Gauge, ScanSearch } from "lucide-react";
import type { QueueEnvelope } from "./contract";
import { formatNumber } from "./format";

export default function QueueOverview({
  summary,
}: {
  summary: QueueEnvelope["data"]["summary"];
}) {
  const cards = [
    {
      label: "UCs para investigar",
      value: String(summary.total_units),
      note: "Suspeitas no recorte completo",
      Icon: ClipboardList,
    },
    {
      label: "Maior pontuação",
      value:
        summary.highest_priority === null
          ? "—"
          : `${formatNumber(summary.highest_priority)} / 1`,
      note: "Prioridade sintética, não probabilidade",
      Icon: Gauge,
    },
    {
      label: "Com estimativa de energia",
      value: `${summary.estimated_units} de ${summary.total_units}`,
      note: `${summary.unavailable_estimate_units} sem estimativa · ausência não é zero`,
      Icon: ScanSearch,
    },
  ];
  return (
    <section
      aria-label="Resumo do recorte da fila"
      className="grid grid-cols-2 gap-3 sm:grid-cols-3"
    >
      {cards.map(({ label, value, note, Icon }) => (
        <article
          key={label}
          className="relative overflow-hidden rounded-xl border border-border bg-surface p-4 first:col-span-2 sm:first:col-span-1"
        >
          <div className="flex items-start justify-between gap-2">
            <h2 className="text-sm text-muted">{label}</h2>
            <Icon
              aria-hidden="true"
              size={18}
              className="shrink-0 text-brand"
            />
          </div>
          <p className="mt-2 font-heading text-2xl font-semibold tracking-tight">
            {value}
          </p>
          <p className="mt-1 text-xs leading-5 text-muted">{note}</p>
        </article>
      ))}
    </section>
  );
}
