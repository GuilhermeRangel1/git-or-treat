import { useState, type FormEvent } from "react";
import { Search } from "lucide-react";
import { ApiError } from "@/shared/api/client";
import DataProvenance from "@/shared/analytics/DataProvenance";
import type { UCSearchResponse } from "./contract";

const inputClass =
  "min-h-11 rounded-lg border border-control bg-canvas px-3 text-content focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand";

type Props = {
  query: string;
  page: number;
  results: UCSearchResponse | undefined;
  isFetching: boolean;
  error: Error | null;
  onSearch: (query: string) => void;
  onPageChange: (page: number) => void;
  onSelect: (ucId: string) => void;
  onRetry: () => void;
};

export default function UC360SearchPanel({
  query,
  page,
  results,
  isFetching,
  error,
  onSearch,
  onPageChange,
  onSelect,
  onRetry,
}: Props) {
  const [draft, setDraft] = useState({ applied: query, value: query });
  const [validation, setValidation] = useState("");
  const provenance = results?.metadata.provenance;
  const value = draft.applied === query ? draft.value : query;
  const errorMessage =
    error instanceof ApiError && error.status === 422
      ? "Busca inválida. Use de 1 a 100 caracteres."
      : "Não foi possível buscar unidades.";

  function submit(event: FormEvent) {
    event.preventDefault();
    const normalized = value.trim();
    if (!normalized || normalized.length > 100) {
      setValidation("Informe um identificador de 1 a 100 caracteres.");
      return;
    }
    setValidation("");
    onSearch(normalized);
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
          o atendimento.
        </p>
      </div>
      <form className="grid w-full gap-3" onSubmit={submit}>
        <label
          className="grid w-full max-w-80 gap-1 text-sm font-medium"
          htmlFor="uc-number"
        >
          Número da UC
          <input
            id="uc-number"
            className={`${inputClass} w-full`}
            autoComplete="off"
            value={value}
            onChange={(event) => {
              setDraft({ applied: query, value: event.target.value });
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
        <button
          className="inline-flex min-h-11 w-full items-center justify-center gap-2 rounded-lg bg-content px-4 text-sm font-medium text-canvas hover:opacity-90 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-content sm:w-fit"
          type="submit"
        >
          <Search size={16} aria-hidden="true" />
          Buscar UC
        </button>
      </form>
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
          Nenhuma unidade corresponde a “{query}”.
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
        <div className="flex flex-wrap items-center gap-3 text-sm text-muted">
          <button
            type="button"
            disabled={page <= 1}
            onClick={() => onPageChange(page - 1)}
            className="min-h-10 rounded border border-control px-3 disabled:opacity-50"
          >
            Anterior
          </button>
          <span>
            Página {results.pagination.page} de {results.pagination.total_pages}
          </span>
          <button
            type="button"
            disabled={page >= results.pagination.total_pages}
            onClick={() => onPageChange(page + 1)}
            className="min-h-10 rounded border border-control px-3 disabled:opacity-50"
          >
            Próxima
          </button>
        </div>
      )}
      {provenance?.source.kind === "gold_csv" && (
        <DataProvenance
          source={provenance.source}
          period={provenance.period}
          units={["UCs"]}
          limitations={provenance.limitations}
          periodLabel="Cobertura do consumo no lote"
          periodNote="A busca consulta o cadastro atual; esta cobertura mensal não representa sua vigência histórica."
        />
      )}
    </section>
  );
}
