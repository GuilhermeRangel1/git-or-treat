import { useRef, useState, type FormEvent } from "react";
import { SlidersHorizontal } from "lucide-react";
import Button from "@/shared/ui/Button";
import Modal from "@/shared/ui/Modal";
import MonthYearField from "@/shared/ui/MonthYearField";
import {
  parseOperationParams,
  type OperationUrlQuery,
} from "./operations-state";
import { formatMonth } from "./operation-format";

const controlClass =
  "min-h-11 w-full rounded-lg border border-control bg-surface px-3 py-2 text-sm text-content focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand";

export default function OperationFilters({
  query,
  feederOptions,
  onApply,
}: {
  query: OperationUrlQuery;
  feederOptions: string[];
  onApply: (filters: {
    start: string;
    end: string;
    feederId: string | null;
  }) => void;
}) {
  const [open, setOpen] = useState(false);
  const [start, setStart] = useState(query.start);
  const [end, setEnd] = useState(query.end);
  const [feederId, setFeederId] = useState(query.feederId ?? "");
  const [errors, setErrors] = useState<string[]>([]);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const startRef = useRef<HTMLInputElement>(null);
  const endRef = useRef<HTMLInputElement>(null);
  const feederRef = useRef<HTMLInputElement>(null);

  function showDialog() {
    setStart(query.start);
    setEnd(query.end);
    setFeederId(query.feederId ?? "");
    setErrors([]);
    setOpen(true);
  }

  function apply(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const params = new URLSearchParams({
      competencia_inicio: start,
      competencia_fim: end,
    });
    if (feederId.trim()) params.set("alimentador", feederId.trim());
    const parsed = parseOperationParams(params);
    if (!parsed.query) {
      setErrors(parsed.errors);
      const first = parsed.errors[0] ?? "";
      if (first.includes("alimentador")) feederRef.current?.focus();
      else if (first.includes("fim") || first.includes("120 meses"))
        endRef.current?.focus();
      else startRef.current?.focus();
      return;
    }
    setErrors([]);
    onApply({ start, end, feederId: feederId.trim() || null });
    setOpen(false);
  }

  return (
    <>
      <section
        aria-label="Filtros aplicados"
        className="flex min-h-[92px] min-w-0 flex-wrap items-center justify-between gap-4 rounded-xl bg-surface p-4"
      >
        <div className="grid min-w-0 flex-1 grid-cols-2 gap-x-5 gap-y-2 text-sm md:grid-cols-3">
          <div>
            <p className="text-xs text-muted">Período</p>
            <p className="mt-1 font-medium">
              {formatMonth(query.start)} – {formatMonth(query.end)}
            </p>
          </div>
          <div className="min-w-0">
            <p className="text-xs text-muted">Alimentador</p>
            <p className="mt-1 truncate font-medium">
              {query.feederId ?? "Todos os alimentadores"}
            </p>
          </div>
          <div className="min-w-0">
            <p className="text-xs text-muted">Ordenação do ranking</p>
            <p className="mt-1 font-medium">
              {query.metric === "dec" ? "DEC decrescente" : "FEC decrescente"}
            </p>
          </div>
        </div>
        <Button
          ref={triggerRef}
          type="button"
          variant="control"
          className="w-full lg:w-auto"
          leftIcon={<SlidersHorizontal size={16} aria-hidden="true" />}
          onClick={showDialog}
        >
          Ajustar filtros
        </Button>
      </section>

      <Modal
        open={open}
        onClose={() => setOpen(false)}
        triggerRef={triggerRef}
        title="Ajustar filtros de operação"
        description="Escolha o intervalo mensal e, se necessário, um alimentador."
        closeLabel="Fechar filtros"
        size="md"
        header="inline"
      >
        <form className="grid gap-4 sm:grid-cols-2" onSubmit={apply} noValidate>
          <MonthYearField
            label="Mês inicial"
            monthLabel="Mês de início"
            yearLabel="Ano de início"
            value={start}
            onChange={setStart}
            yearRef={startRef}
            invalid={errors.some((item) =>
              /início|Mês inv|Informe início|120 meses/.test(item),
            )}
            describedBy={errors.length ? "operation-filter-errors" : undefined}
          />
          <MonthYearField
            label="Mês final"
            monthLabel="Mês do fim"
            yearLabel="Ano do fim"
            value={end}
            onChange={setEnd}
            yearRef={endRef}
            invalid={errors.some((item) =>
              /fim|final|anterior ao fim|120 meses/.test(item),
            )}
            describedBy={errors.length ? "operation-filter-errors" : undefined}
          />
          <label className="grid gap-1.5 text-sm font-medium sm:col-span-2">
            Alimentador
            <input
              className={controlClass}
              ref={feederRef}
              type="text"
              list="operation-feeder-options"
              value={feederId}
              aria-invalid={errors.some((item) => /alimentador/.test(item))}
              aria-describedby={
                errors.length ? "operation-filter-errors" : undefined
              }
              onChange={(event) => setFeederId(event.target.value)}
              placeholder="Todos os alimentadores"
              autoComplete="off"
            />
            <datalist id="operation-feeder-options">
              {feederOptions.map((id) => (
                <option key={id} value={id} />
              ))}
            </datalist>
          </label>
          {errors.length > 0 ? (
            <div
              id="operation-filter-errors"
              role="alert"
              className="text-sm text-danger sm:col-span-2"
            >
              <p>Revise o período e o alimentador:</p>
              <ul className="list-inside list-disc">
                {errors.map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
            </div>
          ) : null}
          <div className="flex flex-wrap gap-2 sm:col-span-2">
            <Button type="submit" variant="accent">
              Aplicar filtros
            </Button>
            <Button
              type="button"
              variant="outline"
              onClick={() => setOpen(false)}
            >
              Cancelar
            </Button>
          </div>
        </form>
      </Modal>
    </>
  );
}
