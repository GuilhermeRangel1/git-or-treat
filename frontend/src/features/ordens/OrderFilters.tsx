import { useRef, useState, type FormEvent } from "react";
import { SlidersHorizontal } from "lucide-react";
import Button from "@/shared/ui/Button";
import Modal from "@/shared/ui/Modal";
import { orderStatuses } from "@/shared/api/orders";
import {
  orderPriorityLabel,
  orderStatusLabel,
  type OrdersQuery,
} from "./ordens-query";

type OrderFiltersProps = {
  params: URLSearchParams;
  filters: OrdersQuery;
  onChange: (next: URLSearchParams) => void;
};

const controlClass =
  "min-h-11 w-full rounded-lg border border-control bg-canvas px-3 text-sm text-content focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand";

export default function OrderFilters({
  params,
  filters,
  onChange,
}: OrderFiltersProps) {
  const [open, setOpen] = useState(false);
  const [draft, setDraft] = useState(() => new URLSearchParams(params));
  const [ucError, setUcError] = useState<string | null>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const ucInputRef = useRef<HTMLInputElement>(null);

  function updateDraft(key: string, value: string) {
    if (key === "uc_id") setUcError(null);
    setDraft((current) => {
      const next = new URLSearchParams(current);
      if (value) next.set(key, value);
      else next.delete(key);
      return next;
    });
  }

  function apply(next: URLSearchParams) {
    next.set("page", "1");
    onChange(next);
    setOpen(false);
  }

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const ucId = draft.get("uc_id")?.trim() ?? "";
    if (
      ucId.length > 50 ||
      Array.from(ucId).some((character) => {
        const codePoint = character.codePointAt(0);
        return (
          codePoint !== undefined &&
          (codePoint < 32 || (codePoint >= 127 && codePoint <= 159))
        );
      })
    ) {
      setUcError(
        "A UC deve ter até 50 caracteres e não pode conter controles.",
      );
      ucInputRef.current?.focus();
      return;
    }
    setUcError(null);
    const next = new URLSearchParams(params);
    if (ucId) next.set("uc_id", ucId);
    else next.delete("uc_id");
    for (const key of ["status", "has_result"]) {
      const value = draft.get(key);
      if (value) next.set(key, value);
      else next.delete(key);
    }
    apply(next);
  }

  function openFilters() {
    setDraft(new URLSearchParams(params));
    setUcError(null);
    setOpen(true);
  }

  const summary = [
    { label: "UC", value: filters.ucId ?? "Todas as UCs" },
    {
      label: "Estado",
      value: filters.status
        ? orderStatusLabel(filters.status)
        : "Todos os estados",
    },
    {
      label: "Resultado",
      value:
        filters.hasResult === null
          ? "Todos"
          : filters.hasResult
            ? "Com resultado"
            : "Sem resultado",
    },
    filters.priority
      ? { label: "Prioridade", value: orderPriorityLabel(filters.priority) }
      : null,
  ].filter((item): item is { label: string; value: string } => item !== null);

  return (
    <>
      <section
        aria-label="Filtros aplicados"
        className="flex min-h-[92px] min-w-0 flex-wrap items-center justify-between gap-4 rounded-xl bg-surface px-4 py-4"
      >
        <div className="grid min-w-0 flex-1 grid-cols-2 gap-x-5 gap-y-2 text-sm md:grid-cols-4">
          {summary.map((item) => (
            <div className="min-w-0" key={item.label}>
              <p className="text-xs text-muted">{item.label}</p>
              <p className="mt-1 truncate font-medium">{item.value}</p>
            </div>
          ))}
          {filters.pageSize !== 20 ? (
            <div>
              <p className="text-xs text-muted">Por página</p>
              <p className="mt-1 font-medium">{filters.pageSize}</p>
            </div>
          ) : null}
        </div>
        <Button
          ref={triggerRef}
          type="button"
          variant="control"
          className="w-full lg:w-auto"
          leftIcon={<SlidersHorizontal size={16} aria-hidden="true" />}
          onClick={openFilters}
        >
          Ajustar filtros
        </Button>
      </section>

      <Modal
        open={open}
        onClose={() => setOpen(false)}
        triggerRef={triggerRef}
        title="Ajustar filtros"
        description="Escolha quais ordens deseja consultar."
        closeLabel="Fechar filtros"
        size="md"
        header="inline"
      >
        <form
          aria-label="Filtros de ordens"
          className="grid gap-4 rounded-xl border border-border bg-surface p-4 shadow-sm sm:grid-cols-2"
          onSubmit={submit}
        >
          <label className="space-y-2 text-sm">
            UC exata
            <input
              ref={ucInputRef}
              className={controlClass}
              type="text"
              maxLength={50}
              autoComplete="off"
              aria-invalid={ucError !== null}
              aria-describedby={ucError ? "uc-filter-error" : undefined}
              value={draft.get("uc_id") ?? ""}
              onChange={(event) => updateDraft("uc_id", event.target.value)}
            />
            {ucError ? (
              <span id="uc-filter-error" className="text-xs text-danger">
                {ucError}
              </span>
            ) : null}
          </label>
          <label className="space-y-2 text-sm">
            Estado
            <select
              className={controlClass}
              value={draft.get("status") ?? ""}
              onChange={(event) => updateDraft("status", event.target.value)}
            >
              <option value="">Todos os estados</option>
              {orderStatuses.map((status) => (
                <option key={status} value={status}>
                  {orderStatusLabel(status)}
                </option>
              ))}
            </select>
          </label>
          <label className="space-y-2 text-sm sm:col-span-2">
            Resultado
            <select
              className={controlClass}
              value={draft.get("has_result") ?? ""}
              onChange={(event) =>
                updateDraft("has_result", event.target.value)
              }
            >
              <option value="">Todos</option>
              <option value="true">Com resultado</option>
              <option value="false">Sem resultado</option>
            </select>
          </label>
          <div className="flex flex-wrap items-end gap-2 sm:col-span-2">
            <Button type="submit" variant="accent" size="wide">
              Aplicar filtros
            </Button>
            <Button
              type="button"
              variant="outline"
              onClick={() => {
                const next = new URLSearchParams(params);
                for (const key of ["uc_id", "status", "has_result"])
                  next.delete(key);
                setDraft(new URLSearchParams(next));
                apply(next);
              }}
            >
              Limpar filtros
            </Button>
            <Button
              type="button"
              variant="ghost"
              onClick={() => setOpen(false)}
            >
              Cancelar
            </Button>
          </div>
        </form>
      </Modal>
    </>
  );
}
