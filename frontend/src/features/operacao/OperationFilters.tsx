import { useRef, useState, type FormEvent } from "react";
import { ChevronDown, RotateCcw, SlidersHorizontal } from "lucide-react";
import Button from "@/shared/ui/Button";
import Modal from "@/shared/ui/Modal";
import MonthYearField from "@/shared/ui/MonthYearField";
import {
  parseOperationParams,
  type OperationUrlQuery,
} from "./operations-state";
import { formatMonth } from "./operation-format";

const controlClass =
  "min-h-11 w-full appearance-none rounded-lg border border-control bg-canvas px-3 pr-10 text-sm text-content focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand";

function SelectField({
  label,
  value,
  options,
  onChange,
}: {
  label: string;
  value: string;
  options: { value: string; label: string }[];
  onChange: (value: string) => void;
}) {
  return (
    <label className="grid gap-1.5 text-sm font-medium text-content">
      {label}
      <span className="relative">
        <select
          className={controlClass}
          value={value}
          onChange={(event) => onChange(event.target.value)}
        >
          {options.map((item) => (
            <option key={item.value} value={item.value}>
              {item.label}
            </option>
          ))}
        </select>
        <ChevronDown
          aria-hidden="true"
          className="pointer-events-none absolute right-3 top-1/2 size-4 -translate-y-1/2 text-muted"
        />
      </span>
    </label>
  );
}

export default function OperationFilters({
  query,
  feederOptions,
  municipalityOptions,
  competencyOptions,
  onApply,
}: {
  query: OperationUrlQuery;
  feederOptions: string[];
  municipalityOptions: string[];
  competencyOptions: string[];
  onApply: (filters: {
    start: string;
    end: string;
    feederId: string | null;
    municipality: string | null;
  }) => void;
}) {
  const [open, setOpen] = useState(false);
  const [start, setStart] = useState(query.start);
  const [end, setEnd] = useState(query.end);
  const [feederId, setFeederId] = useState(query.feederId ?? "");
  const [municipality, setMunicipality] = useState(query.municipality ?? "");
  const [errors, setErrors] = useState<string[]>([]);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const startRef = useRef<HTMLInputElement>(null);
  const endRef = useRef<HTMLInputElement>(null);
  const feederRef = useRef<HTMLInputElement>(null);

  function showDialog() {
    setStart(query.start);
    setEnd(query.end);
    setFeederId(query.feederId ?? "");
    setMunicipality(query.municipality ?? "");
    setErrors([]);
    setOpen(true);
  }

  function resetDraft() {
    setStart(competencyOptions.at(-1) ?? "2025-01");
    setEnd(competencyOptions.at(-1) ?? "2025-02");
    setFeederId("");
    setMunicipality("");
    setErrors([]);
  }

  function apply(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const params = new URLSearchParams({
      competencia_inicio: start,
      competencia_fim: end,
    });
    if (feederId.trim()) params.set("alimentador", feederId.trim());
    if (municipality.trim()) params.set("municipio", municipality.trim());
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
    onApply({
      start,
      end,
      feederId: feederId.trim() || null,
      municipality: municipality.trim() || null,
    });
    setOpen(false);
  }

  const summary = [
    {
      label: "Período",
      value:
        query.start === query.end
          ? formatMonth(query.start)
          : `${formatMonth(query.start)} – ${formatMonth(query.end)}`,
    },
    ...(municipalityOptions.length > 0
      ? [
          {
            label: "Município",
            value: query.municipality ?? "Todos os municípios",
          },
        ]
      : []),
    {
      label: "Alimentador",
      value: query.feederId ?? "Todos os alimentadores",
    },
    {
      label: "Ordenação do ranking",
      value: query.metric === "dec" ? "DEC decrescente" : "FEC decrescente",
    },
  ];
  const canReset =
    Boolean(query.feederId || query.municipality) ||
    start !== (competencyOptions.at(-1) ?? "2025-01") ||
    end !== (competencyOptions.at(-1) ?? "2025-02");

  return (
    <>
      <section
        aria-label="Filtros aplicados"
        className="mt-2 flex min-h-[92px] min-w-0 flex-wrap items-center justify-between gap-4 rounded-xl bg-surface px-4 py-4"
      >
        <dl className="grid min-w-0 flex-1 grid-cols-2 gap-x-5 gap-y-2 text-sm md:grid-cols-4">
          {summary.map((item) => (
            <div className="min-w-0" key={item.label}>
              <dt className="text-xs text-muted">{item.label}</dt>
              <dd className="mt-1 truncate font-medium text-content">
                {item.value}
              </dd>
            </div>
          ))}
        </dl>
        <Button
          ref={triggerRef}
          type="button"
          variant="control"
          className="w-full lg:w-auto"
          leftIcon={
            <SlidersHorizontal
              className="size-4 text-muted"
              aria-hidden="true"
            />
          }
          onClick={showDialog}
        >
          Ajustar filtros
        </Button>
      </section>

      <Modal
        open={open}
        onClose={() => setOpen(false)}
        triggerRef={triggerRef}
        title="Ajustar filtros"
        description="Escolha o período e o território para consultar a continuidade."
        closeLabel="Fechar filtros"
        size="md"
        header="inline"
      >
        <form
          aria-label="Filtros de operação"
          className="grid gap-4 rounded-xl border border-border bg-surface p-4 shadow-sm sm:grid-cols-2"
          onSubmit={apply}
        >
          {competencyOptions.length > 0 ? (
            <SelectField
              label="Mês inicial"
              value={start}
              onChange={setStart}
              options={competencyOptions.map((item) => ({
                value: item,
                label: formatMonth(item),
              }))}
            />
          ) : (
            <MonthYearField
              label="Mês inicial"
              monthLabel="Mês de início"
              yearLabel="Ano de início"
              value={start}
              onChange={setStart}
              yearRef={startRef}
              invalid={errors.some((item) =>
                /início|Mês inv|120 meses/.test(item),
              )}
              describedBy={
                errors.length ? "operation-filter-errors" : undefined
              }
            />
          )}
          {competencyOptions.length > 0 ? (
            <SelectField
              label="Mês final"
              value={end}
              onChange={setEnd}
              options={competencyOptions.map((item) => ({
                value: item,
                label: formatMonth(item),
              }))}
            />
          ) : (
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
              describedBy={
                errors.length ? "operation-filter-errors" : undefined
              }
            />
          )}
          {feederOptions.length > 0 && competencyOptions.length > 0 ? (
            <SelectField
              label="Alimentador"
              value={feederId}
              onChange={setFeederId}
              options={[
                { value: "", label: "Todos os alimentadores" },
                ...feederOptions.map((item) => ({ value: item, label: item })),
              ]}
            />
          ) : (
            <label className="grid gap-1.5 text-sm font-medium text-content sm:col-span-2">
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
          )}
          {municipalityOptions.length > 0 ? (
            <SelectField
              label="Município"
              value={municipality}
              onChange={setMunicipality}
              options={[
                { value: "", label: "Todos os municípios" },
                ...municipalityOptions.map((item) => ({
                  value: item,
                  label: item,
                })),
              ]}
            />
          ) : null}
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
          <div className="flex flex-col-reverse justify-between gap-3 border-t border-divider pt-4 sm:col-span-2 sm:flex-row sm:items-center">
            {canReset ? (
              <Button
                type="button"
                variant="ghost"
                size="sm"
                onClick={resetDraft}
                leftIcon={<RotateCcw className="size-3.5" aria-hidden="true" />}
              >
                Limpar filtros
              </Button>
            ) : (
              <span />
            )}
            <div className="flex justify-end gap-2">
              <Button
                type="button"
                variant="outline"
                onClick={() => setOpen(false)}
              >
                Cancelar
              </Button>
              <Button type="submit" variant="primary">
                Aplicar filtros
              </Button>
            </div>
          </div>
        </form>
      </Modal>
    </>
  );
}
