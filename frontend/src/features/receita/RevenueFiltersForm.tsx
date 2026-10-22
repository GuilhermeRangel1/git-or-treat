import { useState, type FormEvent } from "react";
import type { RevenueEnvelope } from "./contract";
import type { RevenueBaseFilters } from "./revenue-filters";

type RevenueFiltersFormProps = {
  initialFilters: RevenueBaseFilters;
  searchKey: string;
  envelope?: RevenueEnvelope;
  onApply: (filters: RevenueBaseFilters) => void;
};

const textInputClass =
  "min-h-11 w-full rounded-lg border border-control bg-canvas px-3 text-content focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand";

function monthValid(value: string) {
  return /^(?!0000)\d{4}-(0[1-9]|1[0-2])$/.test(value);
}

export default function RevenueFiltersForm({
  initialFilters,
  searchKey,
  envelope,
  onApply,
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
  const neighborhoodOptions = (
    envelope?.data.filter_options.bairros.filter(
      (item) => item.municipio === draft.municipio,
    ) ?? []
  ).map((item) => item.bairro);
  if (draft.bairro && !neighborhoodOptions.includes(draft.bairro)) {
    neighborhoodOptions.push(draft.bairro);
  }
  const classOptions = new Set(envelope?.data.filter_options.classes ?? []);
  if (draft.classe) classOptions.add(draft.classe);

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const nextErrors: string[] = [];
    if (!monthValid(draft.competencia_inicio)) {
      nextErrors.push("A competência inicial precisa ser válida.");
    }
    if (!monthValid(draft.competencia_fim)) {
      nextErrors.push("A competência final precisa ser válida.");
    }
    if (
      monthValid(draft.competencia_inicio) &&
      monthValid(draft.competencia_fim) &&
      draft.competencia_inicio > draft.competencia_fim
    ) {
      nextErrors.push(
        "A competência final deve ser igual ou posterior à inicial.",
      );
    }
    if (draft.bairro && !draft.municipio) {
      nextErrors.push("Selecione o município para filtrar um bairro.");
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

  return (
    <form
      className="grid gap-4 rounded-xl border border-border bg-surface p-4 shadow-sm sm:grid-cols-2 lg:grid-cols-3"
      onSubmit={submit}
      noValidate
      aria-label="Filtros de receita"
    >
      <label className="grid gap-1.5 text-sm font-medium">
        Competência inicial
        <input
          className={textInputClass}
          type="month"
          required
          value={draft.competencia_inicio}
          onChange={(event) =>
            setDraft({ ...draft, competencia_inicio: event.target.value })
          }
        />
      </label>
      <label className="grid gap-1.5 text-sm font-medium">
        Competência final
        <input
          className={textInputClass}
          type="month"
          required
          value={draft.competencia_fim}
          onChange={(event) =>
            setDraft({ ...draft, competencia_fim: event.target.value })
          }
        />
      </label>
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
          className={textInputClass}
          value={draft.bairro}
          disabled={!draft.municipio}
          onChange={(event) =>
            setDraft({ ...draft, bairro: event.target.value })
          }
        >
          <option value="">Todos os bairros</option>
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
      <div className="flex items-end sm:col-span-2 lg:col-span-3">
        <button
          className="min-h-11 rounded-lg bg-brand px-5 text-sm font-semibold text-[var(--accent-goiaba-text)] hover:opacity-90 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand"
          type="submit"
        >
          Aplicar filtros
        </button>
      </div>
      {errors.length > 0 ? (
        <div
          role="alert"
          className="space-y-1 text-sm text-danger sm:col-span-2 lg:col-span-3"
        >
          <h3 className="font-semibold">Filtros inválidos</h3>
          <ul className="list-inside list-disc">
            {errors.map((error) => (
              <li key={error}>{error}</li>
            ))}
          </ul>
        </div>
      ) : null}
      {!draft.municipio ? (
        <p className="text-sm text-muted sm:col-span-2 lg:col-span-3">
          Escolha um município antes de selecionar um bairro.
        </p>
      ) : null}
    </form>
  );
}
