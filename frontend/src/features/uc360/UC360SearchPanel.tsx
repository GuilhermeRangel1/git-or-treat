import { useState, type FormEvent } from "react";
import { Search } from "lucide-react";
import { ApiError } from "@/shared/api/client";
import type { SourceOptions } from "@/shared/analytics/sourceOptions";
import UCPagination from "./UCPagination";
import type { UCSearchResponse } from "./contract";

const inputClass =
  "min-h-11 rounded-lg border border-control bg-canvas px-3 text-content focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand";

type Props = {
  query: string;
  municipio: string;
  classe: string;
  options: Pick<SourceOptions, "municipio" | "classe"> | undefined;
  optionsLoading: boolean;
  optionsError: Error | null;
  page: number;
  results: UCSearchResponse | undefined;
  isFetching: boolean;
  error: Error | null;
  onSearch: (criteria: {
    q: string;
    municipio: string;
    classe: string;
  }) => void;
  onPageChange: (page: number) => void;
  onSelect: (ucId: string) => void;
  onRetry: () => void;
  onRetryOptions: () => void;
};

export default function UC360SearchPanel({
  query,
  municipio,
  classe,
  options,
  optionsLoading,
  optionsError,
  page,
  results,
  isFetching,
  error,
  onSearch,
  onPageChange,
  onSelect,
  onRetry,
  onRetryOptions,
}: Props) {
  const applied = { q: query, municipio, classe };
  const appliedKey = JSON.stringify(applied);
  const [draft, setDraft] = useState({ appliedKey, value: applied });
  const [validation, setValidation] = useState("");
  const value = draft.appliedKey === appliedKey ? draft.value : applied;
  const errorMessage =
    error instanceof ApiError && error.status === 422
      ? "Busca inválida. Use de 1 a 100 caracteres."
      : "Não foi possível buscar unidades.";

  function submit(event: FormEvent) {
    event.preventDefault();
    const normalized = value.q.trim();
    if (normalized.length > 100) {
      setValidation("Informe um identificador de até 100 caracteres.");
      return;
    }
    if (!normalized && !value.municipio && !value.classe) {
      setValidation("Informe um número, município ou classe para buscar.");
      return;
    }
    setValidation("");
    onSearch({ ...value, q: normalized });
  }

  return (
    <section
      className="grid gap-3 rounded-xl bg-surface p-4 sm:p-5"
      aria-labelledby="uc-search-title"
    >
      <div>
        <h2 id="uc-search-title" className="font-heading text-lg font-semibold">
          Buscar unidade consumidora
        </h2>
        <p className="mt-1 text-sm text-muted">
          A UC identifica um ponto de consumo. Digite o número informado durante
          o atendimento ou use os filtros de município e classe.
        </p>
      </div>
      <form className="grid w-full gap-3" onSubmit={submit}>
        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
          <label
            className="grid w-full gap-1 text-sm font-medium"
            htmlFor="uc-number"
          >
            Número da UC
            <input
              id="uc-number"
              className={`${inputClass} w-full`}
              autoComplete="off"
              value={value.q}
              onChange={(event) => {
                setDraft({
                  appliedKey,
                  value: { ...value, q: event.target.value },
                });
                setValidation("");
              }}
              aria-describedby={
                error
                  ? "uc-search-error"
                  : validation
                    ? "uc-search-validation"
                    : undefined
              }
              aria-invalid={Boolean(error || validation)}
            />
          </label>
          <label
            className="grid w-full gap-1 text-sm font-medium"
            htmlFor="uc-municipality"
          >
            Município
            <select
              id="uc-municipality"
              className={`${inputClass} w-full`}
              value={value.municipio}
              disabled={optionsLoading || Boolean(optionsError)}
              onChange={(event) => {
                setDraft({
                  appliedKey,
                  value: { ...value, municipio: event.target.value },
                });
                setValidation("");
              }}
            >
              <option value="">Todos os municípios</option>
              {value.municipio &&
                !options?.municipio.includes(value.municipio) && (
                  <option value={value.municipio}>
                    {value.municipio} (aplicado)
                  </option>
                )}
              {(options?.municipio ?? [])
                .filter((item) => item.trim())
                .map((item) => (
                  <option key={item} value={item}>
                    {item}
                  </option>
                ))}
            </select>
          </label>
          <label
            className="grid w-full gap-1 text-sm font-medium"
            htmlFor="uc-class"
          >
            Classe de consumo
            <select
              id="uc-class"
              className={`${inputClass} w-full`}
              value={value.classe}
              disabled={optionsLoading || Boolean(optionsError)}
              onChange={(event) => {
                setDraft({
                  appliedKey,
                  value: { ...value, classe: event.target.value },
                });
                setValidation("");
              }}
            >
              <option value="">Todas as classes</option>
              {value.classe && !options?.classe.includes(value.classe) && (
                <option value={value.classe}>{value.classe} (aplicada)</option>
              )}
              {(options?.classe ?? [])
                .filter((item) => item.trim())
                .map((item) => (
                  <option key={item} value={item}>
                    {item}
                  </option>
                ))}
            </select>
          </label>
        </div>
        <button
          className="inline-flex min-h-11 w-full items-center justify-center gap-2 rounded-lg bg-content px-4 text-sm font-medium text-canvas hover:opacity-90 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-content sm:w-fit"
          type="submit"
        >
          <Search size={16} aria-hidden="true" />
          Buscar UC
        </button>
      </form>

      {optionsLoading && (
        <p className="text-sm text-muted" role="status">
          Carregando opções dos filtros…
        </p>
      )}
      {optionsError && (
        <p className="text-sm text-danger" role="alert">
          Não foi possível carregar municípios e classes. A busca por número
          continua disponível.{" "}
          <button type="button" onClick={onRetryOptions} className="underline">
            Tentar carregar filtros
          </button>
        </p>
      )}
      {validation && (
        <p
          id="uc-search-validation"
          className="text-sm text-danger"
          role="alert"
        >
          {validation}
        </p>
      )}
      {error && (
        <p id="uc-search-error" className="text-sm text-danger" role="alert">
          {errorMessage}{" "}
          <button type="button" onClick={onRetry} className="underline">
            Tentar novamente
          </button>
        </p>
      )}
      {isFetching && (
        <p role="status" className="text-sm text-muted">
          Buscando unidades…
        </p>
      )}
      {results && !results.data.items.length && (
        <p className="text-sm text-muted" role="status">
          Nenhuma unidade corresponde aos critérios informados.
        </p>
      )}
      {results && results.data.items.length > 0 && (
        <ul className="grid gap-2" aria-label="Resultados da busca">
          {results.data.items.map((item) => (
            <li key={item.uc_id}>
              <button
                type="button"
                onClick={() => onSelect(item.uc_id)}
                className="grid w-full gap-1 rounded-lg border border-control p-3 text-left hover:bg-canvas focus-visible:outline-2 focus-visible:outline-brand sm:grid-cols-[1fr_auto]"
              >
                <span className="font-medium text-content">
                  {item.uc_id} · {item.classe}
                </span>
                <span className="text-sm text-muted">
                  {item.municipio} · {item.bairro} · Alimentador{" "}
                  {item.alimentador}
                </span>
              </button>
            </li>
          ))}
        </ul>
      )}
      {results && results.pagination.total_pages > 1 && (
        <UCPagination
          label="Paginação dos resultados da busca"
          page={page}
          totalPages={results.pagination.total_pages}
          onPageChange={onPageChange}
        />
      )}
    </section>
  );
}
