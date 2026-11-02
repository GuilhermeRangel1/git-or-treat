import { useRef, useState } from "react";
import { apiClient } from "@/shared/api/client";
import Modal from "@/shared/ui/Modal";
import { withGoldPublication } from "@/shared/analytics/goldPublication";
import { inspectionControl } from "./inspection-ui";
import Button from "@/shared/ui/Button";
import { Download, ArrowUpRight } from "lucide-react";

function download(name: string, content: string) {
  const url = URL.createObjectURL(
    new Blob(["\ufeff", content], { type: "text/csv;charset=utf-8" }),
  );
  const link = document.createElement("a");
  link.href = url;
  link.download = name;
  link.click();
  URL.revokeObjectURL(url);
}

export default function FieldFiles({ request }: { request: string }) {
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [open, setOpen] = useState(false);
  const [scope, setScope] = useState("all");
  const [options, setOptions] = useState<Record<string, string[]>>({});
  const [filters, setFilters] = useState<Record<string, string>>({});
  const trigger = useRef<HTMLButtonElement>(null);
  async function openExport() {
    setOpen(true);
    setMessage("");
    setBusy(true);
    try {
      const value = await apiClient<unknown>(
        `/api/v1/inspections/field-queue/export?${withGoldPublication(new URLSearchParams({ options_only: "true" }))}`,
      );
      if (
        !value ||
        typeof value !== "object" ||
        !("options" in value) ||
        !value.options ||
        typeof value.options !== "object"
      )
        throw new Error("Opções inválidas.");
      const decoded: Record<string, string[]> = {};
      for (const [key, values] of Object.entries(value.options)) {
        if (
          !Array.isArray(values) ||
          !values.every((v) => typeof v === "string")
        )
          throw new Error("Opções inválidas.");
        decoded[key] = values;
      }
      setOptions(decoded);
    } catch (error) {
      setMessage(
        error instanceof Error ? error.message : "Falha ao consultar opções.",
      );
    } finally {
      setBusy(false);
    }
  }
  async function exportQueue() {
    setBusy(true);
    setMessage("");
    try {
      const params = new URLSearchParams();
      const current = new URLSearchParams(request);
      for (const key of ["order_by", "direction"])
        if (current.has(key)) params.set(key, current.get(key)!);
      if (scope === "filtered")
        for (const [key, value] of Object.entries(filters))
          if (value) params.set(key, value);
      const response = await apiClient<unknown>(
        `/api/v1/inspections/field-queue/export?${withGoldPublication(params)}`,
      );
      if (
        !response ||
        typeof response !== "object" ||
        !("csv" in response) ||
        typeof response.csv !== "string" ||
        !("count" in response) ||
        !Number.isSafeInteger(response.count)
      )
        throw new Error("Arquivo de exportação inválido.");
      download("fila-inspecao.csv", response.csv);
      setMessage(`${response.count} UC(s) exportada(s).`);
      setOpen(false);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Falha ao exportar.");
    } finally {
      setBusy(false);
    }
  }
  return (
    <section
      aria-label="Arquivos de campo"
      className="overflow-hidden rounded-xl border border-border bg-surface"
    >
      <header className="border-b border-border px-5 py-4 sm:px-6">
        <h2 className="font-heading text-lg font-semibold text-content">
          Arquivos de campo
        </h2>
        <p className="mt-1 text-sm leading-6 text-muted">
          Prepare a fila para a equipe de campo.
        </p>
      </header>
      <div className="grid">
        <div className="flex flex-col items-start gap-4 p-5 sm:p-6">
          <span className="flex size-10 items-center justify-center rounded-lg border border-border bg-canvas text-muted">
            <ArrowUpRight size={20} aria-hidden="true" />
          </span>
          <div>
            <h3 className="text-sm font-semibold text-content">
              Enviar a fila para a equipe
            </h3>
            <p className="mt-2 max-w-md text-sm leading-6 text-muted">
              Exporte todas as UCs ou escolha um recorte por categoria,
              município, bairro e classe.
            </p>
          </div>
          <Button
            variant="outline"
            className="mt-auto w-full sm:w-auto"
            disabled={busy}
            ref={trigger}
            leftIcon={<Download size={16} aria-hidden="true" />}
            onClick={() => void openExport()}
          >
            Exportar fila
          </Button>
        </div>
      </div>
      <Modal
        open={open}
        onClose={() => setOpen(false)}
        triggerRef={trigger}
        size="md"
        header="inline"
        title="Exportar fila de inspeção"
        closeLabel="Fechar exportação"
      >
        <div className="space-y-5">
          <fieldset className="grid gap-3 sm:grid-cols-2">
            <legend className="mb-3 text-sm font-medium">
              O que você quer exportar?
            </legend>
            <label
              className={`flex cursor-pointer items-center gap-3 rounded-lg border p-4 text-sm ${scope === "all" ? "border-brand bg-canvas" : "border-border"}`}
            >
              <input
                type="radio"
                name="export-scope"
                checked={scope === "all"}
                onChange={() => setScope("all")}
                className="size-4 accent-brand"
              />{" "}
              Toda a fila
            </label>
            <label
              className={`flex cursor-pointer items-center gap-3 rounded-lg border p-4 text-sm ${scope === "filtered" ? "border-brand bg-canvas" : "border-border"}`}
            >
              <input
                type="radio"
                name="export-scope"
                checked={scope === "filtered"}
                onChange={() => setScope("filtered")}
                className="size-4 accent-brand"
              />{" "}
              Escolher filtros
            </label>
          </fieldset>
          <div className="grid gap-4 sm:grid-cols-2">
            {scope === "filtered"
              ? Object.entries({
                  categoria: "Categoria",
                  municipio: "Município",
                  bairro: "Bairro",
                  classe: "Classe",
                }).map(([key, label]) => (
                  <label className="block space-y-2 text-sm" key={key}>
                    <span>{label}</span>
                    <select
                      className={inspectionControl}
                      value={filters[key] ?? ""}
                      onChange={(event) =>
                        setFilters((previous) => ({
                          ...previous,
                          [key]: event.target.value,
                        }))
                      }
                    >
                      <option value="">Todas as opções</option>
                      {(options[key] ?? []).map((value) => (
                        <option key={value}>{value}</option>
                      ))}
                    </select>
                    {key === "categoria" && !options[key]?.length ? (
                      <span className="text-xs text-muted">
                        Esta fonte não publica categorias.
                      </span>
                    ) : null}
                  </label>
                ))
              : null}
          </div>
          <p className="text-sm text-muted">
            Todas as UCs do recorte serão incluídas, até 50.000 por arquivo. A
            ordenação atual será preservada.
          </p>
          <div className="flex flex-col-reverse gap-2 border-t border-border pt-4 sm:flex-row sm:justify-end">
            <Button variant="ghost" onClick={() => setOpen(false)}>
              Cancelar
            </Button>
            <Button
              variant="primary"
              disabled={busy}
              leftIcon={<Download size={16} aria-hidden="true" />}
              onClick={() => void exportQueue()}
            >
              Baixar CSV
            </Button>
          </div>
          <p role="status">{busy ? "Processando…" : message}</p>
        </div>
      </Modal>
      {!open && (busy || message) ? (
        <p
          role="status"
          className="border-t border-border bg-canvas px-5 py-4 text-sm leading-6 break-words whitespace-pre-wrap sm:px-6"
        >
          {busy ? "Processando arquivo…" : message}
        </p>
      ) : null}
    </section>
  );
}
