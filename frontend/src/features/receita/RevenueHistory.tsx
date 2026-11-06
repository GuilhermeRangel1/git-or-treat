import { useState, type FormEvent } from "react";
import { ChevronDown } from "lucide-react";
import Button from "@/shared/ui/Button";
import type { RevenueEnvelope } from "./contract";
import RevenueSeries from "./RevenueSeries";

export default function RevenueHistory({
  envelope,
  start,
  end,
  competencies,
  onApply,
}: {
  envelope?: RevenueEnvelope;
  start: string;
  end: string;
  competencies: string[];
  onApply: (start: string, end: string) => void;
}) {
  const [initial, setInitial] = useState(start),
    [final, setFinal] = useState(end),
    [error, setError] = useState("");
  const monthNames = [
    "Jan",
    "Fev",
    "Mar",
    "Abr",
    "Mai",
    "Jun",
    "Jul",
    "Ago",
    "Set",
    "Out",
    "Nov",
    "Dez",
  ];
  const monthOptions = Array.from(new Set([...competencies, start, end]))
    .filter((month) => /^\d{4}-(0[1-9]|1[0-2])$/.test(month))
    .sort();
  const monthOptionLabel = (value: string) =>
    `${monthNames[Number(value.slice(5, 7)) - 1]}/${value.slice(0, 4)}`;
  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (
      !/^\d{4}-(0[1-9]|1[0-2])$/.test(initial) ||
      !/^\d{4}-(0[1-9]|1[0-2])$/.test(final) ||
      initial > final
    ) {
      setError("Selecione meses válidos e em ordem.");
      return;
    }
    setError("");
    onApply(initial, final);
  }
  return (
    <div className="grid gap-4">
      <p className="text-sm text-muted">
        Use o histórico para localizar quando o faturamento mudou neste recorte.
        Este período altera apenas o histórico mensal; a comparação de receita
        mantém as janelas publicadas.
      </p>
      <form
        onSubmit={submit}
        className="grid items-end gap-3 sm:grid-cols-[1fr_1fr_auto]"
      >
        <label className="grid min-w-0 gap-1.5 text-sm font-medium text-content">
          Mês inicial
          <span className="relative">
            <select
              aria-label="Mês inicial do histórico"
              className="min-h-11 w-full appearance-none rounded-lg border border-control bg-canvas px-3 pr-10 text-sm text-content focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand"
              value={initial}
              onChange={(event) => setInitial(event.target.value)}
            >
              {monthOptions.map((month) => (
                <option key={month} value={month}>
                  {monthOptionLabel(month)}
                </option>
              ))}
            </select>
            <ChevronDown
              aria-hidden="true"
              className="pointer-events-none absolute right-3 top-1/2 size-4 -translate-y-1/2 text-muted"
            />
          </span>
        </label>
        <label className="grid min-w-0 gap-1.5 text-sm font-medium text-content">
          Mês final
          <span className="relative">
            <select
              aria-label="Mês final do histórico"
              className="min-h-11 w-full appearance-none rounded-lg border border-control bg-canvas px-3 pr-10 text-sm text-content focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand"
              value={final}
              onChange={(event) => setFinal(event.target.value)}
            >
              {monthOptions.map((month) => (
                <option key={month} value={month}>
                  {monthOptionLabel(month)}
                </option>
              ))}
            </select>
            <ChevronDown
              aria-hidden="true"
              className="pointer-events-none absolute right-3 top-1/2 size-4 -translate-y-1/2 text-muted"
            />
          </span>
        </label>
        <Button type="submit" variant="control">
          Consultar histórico
        </Button>
        {error ? (
          <p role="alert" className="text-sm text-danger sm:col-span-3">
            {error}
          </p>
        ) : null}
      </form>
      {envelope ? (
        <RevenueSeries envelope={envelope} inlineTable />
      ) : (
        <p role="status" className="text-sm text-muted">
          Carregando histórico…
        </p>
      )}
    </div>
  );
}
