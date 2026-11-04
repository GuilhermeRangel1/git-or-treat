import { useRef, useState } from "react";
import { ChevronDown, RotateCcw, SlidersHorizontal } from "lucide-react";
import Button from "@/shared/ui/Button";
import Modal from "@/shared/ui/Modal";
import { filterLabels } from "./queue-query";

const filterControl =
  "min-h-11 w-full appearance-none rounded-lg border border-control bg-canvas px-3 pr-10 text-sm text-content focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand";

export default function InspectionFilters({
  params,
  options,
  neighborhoods,
  onChange,
}: {
  params: URLSearchParams;
  options: Record<string, string[]>;
  neighborhoods: { municipio: string; bairro: string }[];
  onChange: (next: URLSearchParams) => void;
}) {
  const emptyFilterLabels: Record<string, string> = {
    municipio: "Todos os municípios",
    bairro: "Todos os bairros",
    classe: "Todas as classes",
    alimentador: "Todos os alimentadores",
  };
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

  function clearDraft() {
    const next = new URLSearchParams(draft);
    Object.keys(filterLabels).forEach((key) => next.delete(key));
    setDraft(next);
  }

  return (
    <>
      <section
        className="flex min-w-0 flex-wrap items-center justify-between gap-4 rounded-xl bg-surface px-4 py-4"
        aria-label="Filtros aplicados"
      >
        <div className="grid min-w-0 flex-1 grid-cols-2 gap-x-5 gap-y-3 text-sm md:grid-cols-4">
          {Object.entries(filterLabels).map(([key, label]) => (
            <div className="min-w-0" key={key}>
              <p className="text-xs text-muted">{label}</p>
              <p className="mt-1 truncate font-medium">
                {params.get(key) ?? emptyFilterLabels[key]}
              </p>
            </div>
          ))}
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
        description="Escolha município, bairro, classe e alimentador para filtrar a fila."
        closeLabel="Fechar filtros"
        size="md"
        header="inline"
      >
        <form
          key={open ? searchKey : "closed"}
          aria-label="Filtros da fila"
          className="grid gap-4 rounded-xl border border-border bg-surface p-4 shadow-sm sm:grid-cols-2"
          onSubmit={(event) => {
            event.preventDefault();
            const fields = new FormData(event.currentTarget);
            const next = new URLSearchParams(params);
            Object.keys(filterLabels).forEach((key) => next.delete(key));
            for (const [key, value] of fields.entries()) {
              if (typeof value === "string" && value) next.set(key, value);
            }
            apply(next);
          }}
        >
          {Object.entries(filterLabels).map(([key, label]) => (
            <label
              key={key}
              className="grid gap-1.5 text-sm font-medium text-content"
            >
              {label}
              <span className="relative">
                <select
                  name={key}
                  className={`${filterControl} ${key === "bairro" ? "disabled:cursor-not-allowed disabled:opacity-50" : ""}`}
                  value={draft.get(key) ?? ""}
                  onChange={(event) => {
                    const next = new URLSearchParams(draft);
                    if (event.target.value) next.set(key, event.target.value);
                    else next.delete(key);
                    if (key === "municipio") next.delete("bairro");
                    setDraft(next);
                  }}
                  disabled={key === "bairro" && !draft.get("municipio")}
                >
                  <option value="">
                    {key === "bairro" && !draft.get("municipio")
                      ? "Selecione um município primeiro"
                      : key === "municipio"
                        ? "Todos os municípios"
                        : key === "bairro"
                          ? "Todos os bairros"
                          : key === "classe"
                            ? "Todas as classes"
                            : "Todos os alimentadores"}
                  </option>
                  {Array.from(
                    new Set([
                      ...(key === "bairro" &&
                      draft.get("municipio") &&
                      neighborhoods.length
                        ? neighborhoods
                            .filter(
                              (item) =>
                                item.municipio === draft.get("municipio"),
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
                <ChevronDown
                  aria-hidden="true"
                  className="pointer-events-none absolute right-3 top-1/2 size-4 -translate-y-1/2 text-muted"
                />
              </span>
            </label>
          ))}
          <div className="flex flex-col-reverse justify-between gap-3 border-t border-divider pt-4 sm:col-span-2 sm:flex-row sm:items-center">
            <Button
              type="button"
              variant="ghost"
              size="sm"
              onClick={clearDraft}
              leftIcon={<RotateCcw className="size-3.5" aria-hidden="true" />}
            >
              Limpar filtros
            </Button>
            <div className="flex justify-end gap-2">
              <Button type="button" variant="outline" onClick={close}>
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
