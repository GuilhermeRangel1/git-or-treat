import { useId, useRef, useState } from "react";
import { ChevronDown, RotateCcw, SlidersHorizontal } from "lucide-react";
import {
  CLASSES_DISPONIVEIS,
  COMPETENCIAS_DISPONIVEIS,
  MUNICIPIOS_DISPONIVEIS,
} from "../analytics/syntheticData";
import type { ComparisonType, PanoramaFilters } from "../analytics/types";
import { DEFAULT_FILTERS } from "./usePanoramaFilters";
import Button from "../ui/Button";
import Modal from "../ui/Modal";

interface FilterBarProps {
  filters: PanoramaFilters;
  onApply: (filters: PanoramaFilters) => void;
  hasActiveFilters: boolean;
  errors?: Partial<Record<keyof PanoramaFilters, string>>;
}

const COMPARACAO_OPTIONS = [
  { value: "anterior", label: "Mês anterior" },
  { value: "ano_anterior", label: "Mesmo mês do ano anterior" },
  { value: "nenhuma", label: "Sem comparação" },
];
const MONTHS = [
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
const FILTER_CONTROL =
  "min-h-11 w-full appearance-none rounded-lg border border-control bg-canvas px-3 pr-10 text-sm text-content focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand";

function FilterSelect({
  label,
  value,
  options,
  error,
  ariaLabel,
  onChange,
}: {
  label: string;
  value: string;
  options: { value: string; label: string }[];
  error?: string;
  ariaLabel?: string;
  onChange: (value: string) => void;
}) {
  const id = useId();
  const helpId = `${id}-error`;
  return (
    <label
      htmlFor={id}
      className="grid gap-1.5 text-sm font-medium text-content"
    >
      {label}
      <span className="relative">
        <select
          id={id}
          aria-label={ariaLabel ?? label}
          aria-invalid={Boolean(error)}
          aria-describedby={error ? helpId : undefined}
          className={`${FILTER_CONTROL} ${error ? "border-danger" : ""}`}
          value={value}
          onChange={(event) => onChange(event.target.value)}
        >
          {options.map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>
        <ChevronDown
          aria-hidden="true"
          className="pointer-events-none absolute right-3 top-1/2 size-4 -translate-y-1/2 text-muted"
        />
      </span>
      {error ? (
        <span id={helpId} className="text-xs text-danger">
          {error}
        </span>
      ) : null}
    </label>
  );
}

function periodLabel(period: string) {
  if (!/^(?!0000)\d{4}-(0[1-9]|1[0-2])$/.test(period))
    return "Competência inválida";
  const [year, month] = period.split("-");
  return `${MONTHS[Number(month) - 1]}/${year}`;
}

function comparisonLabel(filters: PanoramaFilters) {
  if (filters.comparacao === "nenhuma") return "Sem comparação";
  if (!/^(?!0000)\d{4}-(0[1-9]|1[0-2])$/.test(filters.periodo))
    return "Competência inválida";
  const [year, month] = filters.periodo.split("-").map(Number);
  const date = new Date(0);
  date.setUTCFullYear(year, month - 1, 1);
  if (filters.comparacao === "anterior")
    date.setUTCMonth(date.getUTCMonth() - 1);
  else date.setUTCFullYear(year - 1);
  return periodLabel(
    `${String(date.getUTCFullYear()).padStart(4, "0")}-${String(date.getUTCMonth() + 1).padStart(2, "0")}`,
  );
}

export default function FilterBar({
  filters,
  onApply,
  hasActiveFilters,
  errors = {},
}: FilterBarProps) {
  const [open, setOpen] = useState(Object.keys(errors).length > 0);
  const [draft, setDraft] = useState(filters);
  const triggerRef = useRef<HTMLButtonElement>(null);

  const summary = [
    {
      label: "Competência",
      value: errors.periodo
        ? "Competência inválida"
        : periodLabel(filters.periodo),
    },
    {
      label: "Comparar com",
      value: errors.comparacao
        ? "Comparação inválida"
        : comparisonLabel(filters),
    },
    {
      label: "Território",
      value:
        MUNICIPIOS_DISPONIVEIS.find((item) => item.value === filters.municipio)
          ?.label || "Município inválido",
    },
    {
      label: "Classe",
      value:
        CLASSES_DISPONIVEIS.find((item) => item.value === filters.classe)
          ?.label || "Classe inválida",
    },
  ];
  const change = <K extends keyof PanoramaFilters>(
    key: K,
    value: PanoramaFilters[K],
  ) => setDraft((current) => ({ ...current, [key]: value }));
  const draftErrors = Object.fromEntries(
    (Object.keys(errors) as (keyof PanoramaFilters)[])
      .filter((key) => draft[key] === filters[key])
      .map((key) => [key, errors[key]]),
  ) as Partial<Record<keyof PanoramaFilters, string>>;
  const canResetDraft =
    hasActiveFilters ||
    Object.keys(errors).length > 0 ||
    (Object.keys(DEFAULT_FILTERS) as (keyof PanoramaFilters)[]).some(
      (key) => draft[key] !== DEFAULT_FILTERS[key],
    );

  return (
    <section
      aria-label="Filtros do Panorama"
      className="mt-2 flex min-h-[92px] min-w-0 flex-wrap items-center justify-between gap-4 rounded-xl bg-surface px-4 py-4"
    >
      <dl className="grid min-w-0 flex-1 grid-cols-2 gap-x-5 gap-y-2 text-sm md:grid-cols-4">
        {summary.map((item) => (
          <div key={item.label} className="min-w-0">
            <dt className="text-xs text-muted">{item.label}</dt>
            <dd className="mt-1 truncate font-medium text-content">
              {item.value}
            </dd>
          </div>
        ))}
      </dl>
      <Button
        ref={triggerRef}
        variant="control"
        className="w-full lg:w-auto"
        leftIcon={
          <SlidersHorizontal className="size-4 text-muted" aria-hidden="true" />
        }
        onClick={() => {
          setDraft(filters);
          setOpen(true);
        }}
      >
        Ajustar filtros
      </Button>
      <Modal
        open={open}
        onClose={() => setOpen(false)}
        triggerRef={triggerRef}
        title="Ajustar filtros"
        description="Escolha o recorte e aplique para atualizar os indicadores."
        closeLabel="Fechar filtros"
        size="md"
        header="inline"
      >
        <form
          aria-label="Filtros do Panorama"
          className="grid gap-4 rounded-xl border border-border bg-surface p-4 shadow-sm sm:grid-cols-2"
          onSubmit={(event) => {
            event.preventDefault();
            onApply(draft);
            setOpen(false);
          }}
        >
          <FilterSelect
            label="Período"
            aria-label="Período (Competência)"
            value={draft.periodo}
            error={draftErrors.periodo}
            options={[
              ...(!COMPETENCIAS_DISPONIVEIS.some(
                (c) => c.value === draft.periodo,
              )
                ? [
                    {
                      value: draft.periodo,
                      label: draft.periodo || "Valor vazio",
                    },
                  ]
                : []),
              ...COMPETENCIAS_DISPONIVEIS.map((c) => ({
                value: c.value,
                label: c.label,
              })),
            ]}
            onChange={(value) => change("periodo", value)}
          />
          <FilterSelect
            label="Comparação"
            value={draft.comparacao}
            error={draftErrors.comparacao}
            options={[
              ...(!COMPARACAO_OPTIONS.some(
                (item) => item.value === draft.comparacao,
              )
                ? [{ value: draft.comparacao, label: "Comparação inválida" }]
                : []),
              ...COMPARACAO_OPTIONS,
            ]}
            onChange={(value) => change("comparacao", value as ComparisonType)}
          />
          <FilterSelect
            label="Município"
            value={draft.municipio}
            error={draftErrors.municipio}
            options={[
              ...(!MUNICIPIOS_DISPONIVEIS.some(
                (item) => item.value === draft.municipio,
              )
                ? [{ value: draft.municipio, label: "Município inválido" }]
                : []),
              ...MUNICIPIOS_DISPONIVEIS,
            ]}
            onChange={(value) => change("municipio", value)}
          />
          <FilterSelect
            label="Classe de Consumo"
            value={draft.classe}
            error={draftErrors.classe}
            options={[
              ...(!CLASSES_DISPONIVEIS.some(
                (item) => item.value === draft.classe,
              )
                ? [{ value: draft.classe, label: "Classe inválida" }]
                : []),
              ...CLASSES_DISPONIVEIS,
            ]}
            onChange={(value) => change("classe", value)}
          />
          <div className="flex flex-col-reverse justify-between gap-3 border-t border-divider pt-4 sm:col-span-2 sm:flex-row sm:items-center">
            {canResetDraft ? (
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setDraft(DEFAULT_FILTERS)}
                leftIcon={<RotateCcw className="size-3.5" aria-hidden="true" />}
              >
                Limpar filtros
              </Button>
            ) : (
              <span />
            )}
            <div className="flex justify-end gap-2">
              <Button variant="outline" onClick={() => setOpen(false)}>
                Cancelar
              </Button>
              <Button type="submit" variant="primary">
                Aplicar filtros
              </Button>
            </div>
          </div>
        </form>
      </Modal>
    </section>
  );
}
