import { useEffect, useRef, useState } from "react";
import { SlidersHorizontal } from "lucide-react";
import { filterLabels } from "./queue-query";
import { inspectionAction, inspectionControl } from "./inspection-ui";
import type { Metadata } from "./contract";

function territory(params: URLSearchParams) {
  const neighborhood = params.get("bairro");
  const municipality = params.get("municipio");
  if (neighborhood)
    return municipality ? `${neighborhood} · ${municipality}` : neighborhood;
  return municipality ?? "Todos os municípios";
}

function periodLabel(start?: string, end?: string) {
  if (!start || !end) return "Consultando…";
  const formatMonth = (value: string) => {
    const [year, month] = value.split("-");
    const names = [
      "jan",
      "fev",
      "mar",
      "abr",
      "mai",
      "jun",
      "jul",
      "ago",
      "set",
      "out",
      "nov",
      "dez",
    ];
    return `${names[Number(month) - 1] ?? month}/${year}`;
  };
  return `${formatMonth(start)} – ${formatMonth(end)}`;
}

export default function InspectionFilters({
  params,
  options,
  metadata,
  onChange,
}: {
  params: URLSearchParams;
  request: string;
  options: Record<string, string[]>;
  metadata?: Metadata;
  onChange: (next: URLSearchParams) => void;
}) {
  const searchKey = params.toString();
  const [open, setOpen] = useState(false);
  const [draft, setDraft] = useState(() => new URLSearchParams(params));
  const [previousSearchKey, setPreviousSearchKey] = useState(searchKey);
  const dialogRef = useRef<HTMLDialogElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const restoreFocusRef = useRef(false);

  if (searchKey !== previousSearchKey && !open) {
    setPreviousSearchKey(searchKey);
    setDraft(new URLSearchParams(params));
  }

  useEffect(() => {
    const dialog = dialogRef.current;
    if (!dialog) return;
    if (open && !dialog.open) {
      if (typeof dialog.showModal === "function") dialog.showModal();
      else dialog.setAttribute("open", "");
    }
    if (!open && dialog.open) {
      if (typeof dialog.close === "function") dialog.close();
      else dialog.removeAttribute("open");
    }
  }, [open]);

  useEffect(() => {
    if (!open && restoreFocusRef.current) {
      triggerRef.current?.focus();
      restoreFocusRef.current = false;
    }
  }, [open]);

  function close() {
    restoreFocusRef.current = true;
    setOpen(false);
  }

  function apply(next: URLSearchParams) {
    next.set("page", "1");
    onChange(next);
    close();
  }

  function updateDraft(key: string, value: string) {
    const next = new URLSearchParams(draft);
    if (value) next.set(key, value);
    else next.delete(key);
    setDraft(next);
  }

  return (
    <>
      <section
        className="flex min-h-[92px] min-w-0 flex-wrap items-center justify-between gap-4 rounded-xl bg-surface px-4 py-4"
        aria-label="Filtros aplicados"
      >
        <div className="grid min-w-0 flex-1 grid-cols-2 gap-x-5 gap-y-2 text-sm md:grid-cols-4">
          <div>
            <p className="text-xs text-muted">Competência</p>
            <p className="mt-1 font-medium">
              {periodLabel(metadata?.period.start, metadata?.period.end)}
            </p>
          </div>
          <div>
            <p className="text-xs text-muted">Comparar com</p>
            <p className="mt-1 font-medium">Não aplicada</p>
          </div>
          <div className="min-w-0">
            <p className="text-xs text-muted">Território</p>
            <p className="mt-1 truncate font-medium">{territory(params)}</p>
            {params.get("alimentador") ? (
              <p className="mt-1 break-words text-xs font-medium text-muted">
                Alimentador: {params.get("alimentador")}
              </p>
            ) : null}
          </div>
          <div className="min-w-0">
            <p className="text-xs text-muted">Classe</p>
            <p className="mt-1 truncate font-medium">
              {params.get("classe") ?? "Todas as classes"}
            </p>
          </div>
        </div>
        <button
          ref={triggerRef}
          type="button"
          className="min-h-11 w-full shrink-0 rounded-lg border border-control bg-canvas px-4 text-sm font-semibold text-content hover:bg-surface-hover focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand lg:w-auto"
          onClick={() => {
            setDraft(new URLSearchParams(params));
            setPreviousSearchKey(searchKey);
            setOpen(true);
          }}
        >
          <SlidersHorizontal
            size={16}
            aria-hidden="true"
            className="mr-2 inline size-4"
          />
          Ajustar filtros
        </button>
      </section>

      <dialog
        ref={dialogRef}
        aria-labelledby="inspection-filters-title"
        aria-label="Ajustar filtros da fila"
        className="fixed inset-0 m-auto max-h-[90vh] w-[min(720px,calc(100vw-2rem))] min-w-0 overflow-y-auto rounded-2xl border border-border bg-surface p-0 text-content shadow-2xl backdrop:bg-black/50"
        onCancel={(event) => {
          event.preventDefault();
          close();
        }}
        onKeyDown={(event) => {
          if (event.key === "Escape") close();
        }}
        onClose={() => {
          if (open) close();
        }}
      >
        <section className="grid gap-4 p-5 sm:p-6">
          <div className="flex items-start justify-between gap-4">
            <div>
              <h2
                id="inspection-filters-title"
                className="font-heading text-xl font-semibold"
              >
                Ajustar filtros
              </h2>
              <p className="mt-1 text-sm text-muted">
                Escolha o recorte, a ordenação e o tamanho da página da fila.
              </p>
            </div>
            <button
              type="button"
              aria-label="Fechar filtros"
              className="grid size-10 shrink-0 place-items-center rounded-lg border border-control hover:bg-surface-hover focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand"
              onClick={close}
            >
              ×
            </button>
          </div>
          <form
            key={open ? searchKey : "closed"}
            aria-label="Filtros da fila"
            className="grid gap-4 rounded-xl border border-border bg-surface p-4 shadow-sm sm:grid-cols-2 lg:grid-cols-3"
            onSubmit={(event) => {
              event.preventDefault();
              const fields = new FormData(event.currentTarget);
              const next = new URLSearchParams();
              for (const [key, value] of fields.entries()) {
                if (typeof value === "string" && value) next.set(key, value);
              }
              apply(next);
            }}
          >
            {Object.entries(filterLabels).map(([key, label]) => (
              <label key={key} className="space-y-2 text-sm">
                <span>{label}</span>
                <select
                  name={key}
                  className={inspectionControl}
                  value={draft.get(key) ?? ""}
                  onChange={(event) => {
                    const next = new URLSearchParams(draft);
                    if (event.target.value) next.set(key, event.target.value);
                    else next.delete(key);
                    if (key === "municipio") next.delete("bairro");
                    setDraft(next);
                  }}
                >
                  <option value="">Todos</option>
                  {Array.from(
                    new Set([
                      ...(options[key] ?? []),
                      ...(draft.get(key) ? [draft.get(key)!] : []),
                    ]),
                  ).map((value) => (
                    <option key={value} value={value}>
                      {value}
                    </option>
                  ))}
                </select>
              </label>
            ))}
            <label className="space-y-2 text-sm">
              <span>Ordenar por</span>
              <select
                name="order_by"
                className={inspectionControl}
                value={draft.get("order_by") ?? "priority"}
                onChange={(event) =>
                  updateDraft("order_by", event.target.value)
                }
              >
                <option value="priority">Prioridade</option>
                <option value="potential_recoverable_energy_kwh">
                  Energia estimada
                </option>
                <option value="uc_id">Número da UC</option>
              </select>
            </label>
            <label className="space-y-2 text-sm">
              <span>Direção</span>
              <select
                name="direction"
                className={inspectionControl}
                value={draft.get("direction") ?? "desc"}
                onChange={(event) =>
                  updateDraft("direction", event.target.value)
                }
              >
                <option value="desc">Decrescente</option>
                <option value="asc">Crescente</option>
              </select>
            </label>
            <label className="space-y-2 text-sm">
              <span>UCs por página</span>
              <select
                name="page_size"
                className={inspectionControl}
                value={draft.get("page_size") ?? "10"}
                onChange={(event) =>
                  updateDraft("page_size", event.target.value)
                }
              >
                {Array.from(
                  new Set([
                    1,
                    10,
                    20,
                    50,
                    Number(draft.get("page_size") ?? 10),
                  ]),
                )
                  .sort((a, b) => a - b)
                  .map((size) => (
                    <option key={size} value={size}>
                      {size}
                    </option>
                  ))}
              </select>
            </label>
            <div className="flex flex-wrap items-end gap-2 sm:col-span-2 lg:col-span-3">
              <button
                type="submit"
                className="min-h-11 rounded-lg bg-brand px-5 text-sm font-semibold text-[var(--accent-goiaba-text)] hover:opacity-90 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand"
              >
                Aplicar filtros
              </button>
              <button
                type="button"
                className={inspectionAction}
                onClick={() => apply(new URLSearchParams())}
              >
                Limpar filtros
              </button>
            </div>
          </form>
        </section>
      </dialog>
    </>
  );
}
