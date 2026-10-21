import { useState, type FormEvent } from "react";
import {
  validateKpisFilters,
  type KpisFilters,
  type KpisFilterErrors,
} from "./kpis-filters";

type KpisFiltersFormProps = {
  navigationKey: string;
  initialFilters: KpisFilters;
  initialErrors?: KpisFilterErrors;
  onApply: (filters: KpisFilters) => void;
};

export function KpisFiltersForm({
  navigationKey,
  initialFilters,
  initialErrors = {},
  onApply,
}: KpisFiltersFormProps) {
  const [draft, setDraft] = useState(initialFilters);
  const [errors, setErrors] = useState(initialErrors);
  const [previousNavigationKey, setPreviousNavigationKey] =
    useState(navigationKey);

  // Reset the local draft on navigation while preserving the focused DOM control.
  if (navigationKey !== previousNavigationKey) {
    setPreviousNavigationKey(navigationKey);
    setDraft(initialFilters);
    setErrors(initialErrors);
  }

  function fieldAttributes(field: keyof KpisFilters) {
    return {
      name: field,
      "aria-invalid": errors[field] ? true : undefined,
      "aria-describedby": errors[field] ? `kpis-error-${field}` : undefined,
    } as const;
  }

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const filters = {
      ...draft,
      municipio: draft.municipio.trim(),
      classe: draft.classe.trim(),
    };
    const nextErrors = validateKpisFilters(filters);
    setErrors(nextErrors);
    const firstError = Object.keys(nextErrors)[0];
    if (firstError) {
      const field = event.currentTarget.elements.namedItem(firstError);
      if (field instanceof HTMLElement) field.focus();
      return;
    }
    onApply(filters);
  }

  return (
    <form
      className="grid gap-4 rounded-xl border border-border bg-surface p-4 shadow-sm sm:grid-cols-2 lg:grid-cols-5 lg:items-end"
      onSubmit={submit}
      noValidate
    >
      <label className="grid gap-1.5 text-sm font-medium">
        Competência inicial
        <input
          className="min-h-11 rounded-lg border border-control bg-canvas px-3 text-content focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand"
          type="month"
          {...fieldAttributes("competencia_inicio")}
          value={draft.competencia_inicio}
          onChange={(event) =>
            setDraft({ ...draft, competencia_inicio: event.target.value })
          }
          required
        />
      </label>
      <label className="grid gap-1.5 text-sm font-medium">
        Competência final
        <input
          className="min-h-11 rounded-lg border border-control bg-canvas px-3 text-content focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand"
          type="month"
          {...fieldAttributes("competencia_fim")}
          value={draft.competencia_fim}
          onChange={(event) =>
            setDraft({ ...draft, competencia_fim: event.target.value })
          }
          required
        />
      </label>
      <label className="grid gap-1.5 text-sm font-medium">
        Município
        <input
          className="min-h-11 rounded-lg border border-control bg-canvas px-3 text-content focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand"
          type="text"
          {...fieldAttributes("municipio")}
          value={draft.municipio}
          onChange={(event) =>
            setDraft({ ...draft, municipio: event.target.value })
          }
          autoComplete="address-level2"
        />
      </label>
      <label className="grid gap-1.5 text-sm font-medium">
        Classe
        <input
          className="min-h-11 rounded-lg border border-control bg-canvas px-3 text-content focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand"
          type="text"
          {...fieldAttributes("classe")}
          value={draft.classe}
          onChange={(event) =>
            setDraft({ ...draft, classe: event.target.value })
          }
        />
      </label>
      <button
        className="min-h-11 rounded-lg bg-brand px-4 text-sm font-semibold text-[var(--accent-goiaba-text)] hover:opacity-90 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand"
        type="submit"
      >
        Consultar
      </button>
      {Object.keys(errors).length > 0 ? (
        <div
          role="alert"
          className="space-y-2 text-sm text-danger sm:col-span-2 lg:col-span-5"
        >
          <h2 className="font-semibold">Filtros inválidos</h2>
          <p>
            Corrija os filtros e selecione Consultar para aplicar o recorte.
          </p>
          <ul className="list-inside list-disc">
            {Object.entries(errors).map(([field, message]) => (
              <li id={`kpis-error-${field}`} key={field}>
                {message}
              </li>
            ))}
          </ul>
        </div>
      ) : null}
    </form>
  );
}
