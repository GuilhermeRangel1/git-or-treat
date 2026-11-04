import { useState, type FormEvent } from "react";
import { ChevronDown, RotateCcw } from "lucide-react";
import Button from "@/shared/ui/Button";
import MonthYearField from "@/shared/ui/MonthYearField";
import type { SourceOptions } from "@/shared/analytics/sourceOptions";
import type { RevenueEnvelope } from "./contract";
import type { RevenueBaseFilters } from "./revenue-filters";

type RevenueFiltersFormProps = {
  initialFilters: RevenueBaseFilters;
  defaultFilters: RevenueBaseFilters;
  searchKey: string;
  envelope?: RevenueEnvelope;
  options?: SourceOptions;
  onApply: (filters: RevenueBaseFilters) => void;
  onCancel: () => void;
};

const textInputClass =
  "min-h-11 w-full rounded-lg border border-control bg-canvas px-3 text-content focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand";
const selectControlClass =
  "min-h-11 w-full appearance-none rounded-lg border border-control bg-canvas px-3 pr-10 text-sm text-content focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand";

function SelectField({
  label,
  value,
  options,
  onChange,
}: {
  label: string;
  value: string;
  options: string[];
  onChange: (value: string) => void;
}) {
  return (
    <label className="grid gap-1.5 text-sm font-medium text-content">
      {label}
      <span className="relative">
        <select
          className={selectControlClass}
          value={value}
          onChange={(event) => onChange(event.target.value)}
        >
          {options.map((competencia) => (
            <option key={competencia} value={competencia}>
              {competenceLabel(competencia)}
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

function competenceLabel(value: string) {
  const month = Number(value.slice(5, 7));
  const names = [
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
  return `${names[month - 1] ?? value.slice(5, 7)}/${value.slice(0, 4)}`;
}

function monthValid(value: string) {
  return /^(?!0000)\d{4}-(0[1-9]|1[0-2])$/.test(value);
}

export default function RevenueFiltersForm({
  initialFilters,
  defaultFilters,
  searchKey,
  envelope,
  options,
  onApply,
  onCancel,
}: RevenueFiltersFormProps) {
  const [draft, setDraft] = useState(initialFilters);
  const [errors, setErrors] = useState<string[]>([]);
  const [previousSearchKey, setPreviousSearchKey] = useState(searchKey);
  if (searchKey !== previousSearchKey) {
    setPreviousSearchKey(searchKey);
    setDraft(initialFilters);
    setErrors([]);
  }

  const municipalityOptions = new Set(
    envelope?.data.filter_options.municipios ?? [],
  );
  if (draft.municipio) municipalityOptions.add(draft.municipio);
  const neighborhoodOptions = Array.from(
    new Set(
      (envelope?.data.filter_options.bairros ?? [])
        .filter(
          (item) => !draft.municipio || item.municipio === draft.municipio,
        )
        .map((item) => item.bairro),
    ),
  );
  if (draft.bairro && !neighborhoodOptions.includes(draft.bairro)) {
    neighborhoodOptions.push(draft.bairro);
  }
  const classOptions = new Set(envelope?.data.filter_options.classes ?? []);
  if (draft.classe) classOptions.add(draft.classe);

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const nextErrors: string[] = [];
    if (!monthValid(draft.competencia_inicio)) {
      nextErrors.push("O mês inicial precisa ser válido.");
    }
    if (!monthValid(draft.competencia_fim)) {
      nextErrors.push("O mês final precisa ser válido.");
    }
    if (
      monthValid(draft.competencia_inicio) &&
      monthValid(draft.competencia_fim) &&
      draft.competencia_inicio > draft.competencia_fim
    ) {
      nextErrors.push(
        "O mês final deve ser igual ou posterior ao mês inicial.",
      );
    }
    for (const [field, label] of [
      ["municipio", "Município"],
      ["bairro", "Bairro"],
      ["classe", "Classe"],
      ["alimentador", "Alimentador"],
    ] as const) {
      if (Array.from(draft[field]).length > 100) {
        nextErrors.push(`${label} deve ter no máximo 100 caracteres.`);
      }
    }
    setErrors(nextErrors);
    if (nextErrors.length === 0) {
      onApply({
        ...draft,
        municipio: draft.municipio.trim(),
        bairro: draft.bairro.trim(),
        classe: draft.classe.trim(),
        alimentador: draft.alimentador.trim(),
      });
    }
  }

  function resetDraft() {
    setDraft(defaultFilters);
    setErrors([]);
  }

  return (
    <form
      className="grid gap-4 rounded-xl border border-border bg-surface p-4 shadow-sm sm:grid-cols-2"
      onSubmit={submit}
      noValidate
      aria-label="Filtros de receita"
    >
      {options?.competencias.length ? (
        <SelectField
          label="Mês inicial"
          value={draft.competencia_inicio}
          options={[
            ...(!options.competencias.includes(draft.competencia_inicio)
              ? [draft.competencia_inicio]
              : []),
            ...options.competencias,
          ]}
          onChange={(competencia_inicio) =>
            setDraft({ ...draft, competencia_inicio })
          }
        />
      ) : (
        <MonthYearField
          label="Mês inicial"
          monthLabel="Mês de início"
          yearLabel="Ano de início"
          value={draft.competencia_inicio}
          onChange={(competencia_inicio) =>
            setDraft({ ...draft, competencia_inicio })
          }
        />
      )}
      {options?.competencias.length ? (
        <SelectField
          label="Mês final"
          value={draft.competencia_fim}
          options={[
            ...(!options.competencias.includes(draft.competencia_fim)
              ? [draft.competencia_fim]
              : []),
            ...options.competencias,
          ]}
          onChange={(competencia_fim) =>
            setDraft({ ...draft, competencia_fim })
          }
        />
      ) : (
        <MonthYearField
          label="Mês final"
          monthLabel="Mês do fim"
          yearLabel="Ano do fim"
          value={draft.competencia_fim}
          onChange={(competencia_fim) =>
            setDraft({ ...draft, competencia_fim })
          }
        />
      )}
      <label className="grid gap-1.5 text-sm font-medium">
        Município
        <select
          className={textInputClass}
          value={draft.municipio}
          onChange={(event) =>
            setDraft({ ...draft, municipio: event.target.value, bairro: "" })
          }
        >
          <option value="">Todos os municípios</option>
          {[...municipalityOptions].sort().map((municipio) => (
            <option key={municipio} value={municipio}>
              {municipio === "__grid360_missing__"
                ? "Não informado"
                : municipio}
            </option>
          ))}
        </select>
      </label>
      <label className="grid gap-1.5 text-sm font-medium">
        Bairro
        <select
          className={`${textInputClass} disabled:cursor-not-allowed disabled:opacity-50`}
          value={draft.bairro}
          disabled={!draft.municipio}
          onChange={(event) =>
            setDraft({ ...draft, bairro: event.target.value })
          }
        >
          <option value="">
            {draft.municipio
              ? "Todos os bairros"
              : "Selecione um município primeiro"}
          </option>
          {neighborhoodOptions.sort().map((bairro) => (
            <option key={bairro} value={bairro}>
              {bairro === "__grid360_missing__" ? "Não informado" : bairro}
            </option>
          ))}
        </select>
      </label>
      <label className="grid gap-1.5 text-sm font-medium">
        Classe
        <select
          className={textInputClass}
          value={draft.classe}
          onChange={(event) =>
            setDraft({ ...draft, classe: event.target.value })
          }
        >
          <option value="">Todas as classes</option>
          {[...classOptions].sort().map((classe) => (
            <option key={classe} value={classe}>
              {classe === "__grid360_missing__" ? "Não informado" : classe}
            </option>
          ))}
        </select>
      </label>
      <label className="grid gap-1.5 text-sm font-medium">
        Alimentador
        <select
          className={textInputClass}
          value={draft.alimentador}
          onChange={(event) =>
            setDraft({ ...draft, alimentador: event.target.value })
          }
        >
          <option value="">Todos os alimentadores</option>
          {Array.from(
            new Set([
              ...(options?.alimentador ?? []),
              ...(draft.alimentador ? [draft.alimentador] : []),
            ]),
          )
            .sort()
            .map((value) => (
              <option key={value} value={value}>
                {value}
              </option>
            ))}
        </select>
      </label>
      {errors.length > 0 ? (
        <div
          role="alert"
          className="space-y-1 text-sm text-danger sm:col-span-2"
        >
          <h3 className="font-semibold">Filtros inválidos</h3>
          <ul className="list-inside list-disc">
            {errors.map((error) => (
              <li key={error}>{error}</li>
            ))}
          </ul>
        </div>
      ) : null}
      <div className="flex flex-col-reverse justify-between gap-3 border-t border-divider pt-4 sm:col-span-2 sm:flex-row sm:items-center">
        <Button
          type="button"
          variant="ghost"
          size="sm"
          onClick={resetDraft}
          leftIcon={<RotateCcw className="size-3.5" aria-hidden="true" />}
        >
          Limpar filtros
        </Button>
        <div className="flex justify-end gap-2">
          <Button type="button" variant="outline" onClick={onCancel}>
            Cancelar
          </Button>
          <Button type="submit" variant="primary">
            Aplicar filtros
          </Button>
        </div>
      </div>
    </form>
  );
}
