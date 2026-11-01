import { useRef, useState } from "react";
import { SlidersHorizontal } from "lucide-react";
import Button from "@/shared/ui/Button";
import Modal from "@/shared/ui/Modal";
import { filterLabels } from "./queue-query";
import { inspectionControl } from "./inspection-ui";
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
  neighborhoods,
  onChange,
}: {
  params: URLSearchParams;
  request: string;
  options: Record<string, string[]>;
  metadata?: Metadata;
  neighborhoods: { municipio: string; bairro: string }[];
  onChange: (next: URLSearchParams) => void;
}) {
  const gold = metadata?.contract_version === "2.0.0";
  const legacyGold = metadata?.source.kind === "gold_csv";
  const searchKey = params.toString();
  const [open, setOpen] = useState(false);
  const [draft, setDraft] = useState(() => new URLSearchParams(params));
  const [previousSearchKey, setPreviousSearchKey] = useState(searchKey);
  const triggerRef = useRef<HTMLButtonElement>(null);

  if (searchKey !== previousSearchKey && !open) {
    setPreviousSearchKey(searchKey);
    setDraft(new URLSearchParams(params));
  }

  function close() {
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
              {gold
                ? "Cadastro atual · sem competência"
                : periodLabel(metadata?.period?.start, metadata?.period?.end)}
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
        <Button
          ref={triggerRef}
          type="button"
          variant="control"
          className="w-full lg:w-auto"
          leftIcon={<SlidersHorizontal size={16} aria-hidden="true" />}
          onClick={() => {
            setDraft(new URLSearchParams(params));
            setPreviousSearchKey(searchKey);
            setOpen(true);
          }}
        >
          Ajustar filtros
        </Button>
      </section>

      <Modal
        open={open}
        onClose={close}
        triggerRef={triggerRef}
        title="Ajustar filtros"
        description="Escolha o recorte, a ordenação e o tamanho da página da fila."
        closeLabel="Fechar filtros"
        size="md"
        header="inline"
      >
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
                    ...(key === "bairro" &&
                    draft.get("municipio") &&
                    neighborhoods.length
                      ? neighborhoods
                          .filter(
                            (item) => item.municipio === draft.get("municipio"),
                          )
                          .map((item) => item.bairro)
                      : (options[key] ?? [])),
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
              value={
                draft.get("order_by") ?? (gold ? "queue_position" : "priority")
              }
              onChange={(event) => updateDraft("order_by", event.target.value)}
            >
              {gold ? (
                <>
                  <option value="queue_position">
                    Posição oficial da fila
                  </option>
                  <option value="uc_id">Número da UC</option>
                  <option value="category">Categoria</option>
                </>
              ) : (
                <>
                  <option value="priority">Prioridade demonstrativa</option>
                  <option
                    value="potential_recoverable_energy_kwh"
                    disabled={legacyGold}
                  >
                    Energia estimada{legacyGold ? " (indisponível)" : ""}
                  </option>
                  <option value="uc_id">Número da UC</option>
                </>
              )}
            </select>
          </label>
          <label className="space-y-2 text-sm">
            <span>Direção</span>
            <select
              name="direction"
              className={inspectionControl}
              value={draft.get("direction") ?? (gold ? "asc" : "desc")}
              onChange={(event) => updateDraft("direction", event.target.value)}
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
              onChange={(event) => updateDraft("page_size", event.target.value)}
            >
              {Array.from(
                new Set([1, 10, 20, 50, Number(draft.get("page_size") ?? 10)]),
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
            <Button type="submit" variant="accent" size="wide">
              Aplicar filtros
            </Button>
            <Button
              type="button"
              variant="outline"
              onClick={() => apply(new URLSearchParams())}
            >
              Limpar filtros
            </Button>
          </div>
        </form>
      </Modal>
    </>
  );
}
