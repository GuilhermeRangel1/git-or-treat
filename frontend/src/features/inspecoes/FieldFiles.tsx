import { useRef, useState } from "react";
import { apiClient } from "@/shared/api/client";
import Modal from "@/shared/ui/Modal";
import { withGoldPublication } from "@/shared/analytics/goldPublication";
import { inspectionControl } from "./inspection-ui";
import Button from "@/shared/ui/Button";
import { Download, FileSpreadsheet, Upload, ArrowUpRight } from "lucide-react";
import { useQueryClient } from "@tanstack/react-query";

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
  const queryClient = useQueryClient();
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [open, setOpen] = useState(false);
  const [scope, setScope] = useState("all");
  const [options, setOptions] = useState<Record<string, string[]>>({});
  const [filters, setFilters] = useState<Record<string, string>>({});
  const trigger = useRef<HTMLButtonElement>(null);
  const uploadRef = useRef<HTMLInputElement>(null);
  async function template() {
    setBusy(true);
    setMessage("");
    try {
      const value = await apiClient<unknown>(
        "/api/v1/inspections/field-results/template",
      );
      if (
        !value ||
        typeof value !== "object" ||
        !("xlsx" in value) ||
        typeof value.xlsx !== "string" ||
        !("count" in value) ||
        !Number.isSafeInteger(value.count)
      )
        throw new Error("Modelo inválido.");
      const bytes = Uint8Array.from(atob(value.xlsx), (char) =>
        char.charCodeAt(0),
      );
      const url = URL.createObjectURL(
        new Blob([bytes], {
          type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        }),
      );
      const link = document.createElement("a");
      link.href = url;
      link.download = "resultados-campo.xlsx";
      link.click();
      URL.revokeObjectURL(url);
      setMessage(
        `${value.count} ordem(ns) em andamento no modelo. Preencha a coluna resultado e envie a planilha.`,
      );
    } catch (error) {
      setMessage(
        error instanceof Error ? error.message : "Falha ao baixar modelo.",
      );
    } finally {
      setBusy(false);
    }
  }
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
  async function upload(file: File | undefined) {
    if (!file) return;
    if (file.size > 1_000_000) {
      setMessage("O arquivo deve ter até 1 MB.");
      return;
    }
    setBusy(true);
    setMessage("");
    try {
      const isExcel = file.name.toLowerCase().endsWith(".xlsx");
      let payload: { csv: string } | { xlsx: string };
      if (isExcel) {
        const bytes = new Uint8Array(await file.arrayBuffer());
        let binary = "";
        for (const byte of bytes) binary += String.fromCharCode(byte);
        payload = { xlsx: btoa(binary) };
      } else if (file.name.toLowerCase().endsWith(".csv")) {
        payload = { csv: await file.text() };
      } else throw new Error("Selecione um arquivo XLSX ou CSV.");
      const result = await apiClient<unknown>(
        "/api/v1/inspections/field-results/import",
        { method: "POST", body: JSON.stringify(payload) },
      );
      if (
        !result ||
        typeof result !== "object" ||
        !("imported" in result) ||
        typeof result.imported !== "number" ||
        !("errors" in result) ||
        !Array.isArray(result.errors)
      )
        throw new Error("Resposta de importação inválida.");
      const errors = result.errors.map((error: unknown) => {
        if (
          !error ||
          typeof error !== "object" ||
          !("line" in error) ||
          typeof error.line !== "number" ||
          !("message" in error) ||
          typeof error.message !== "string"
        )
          throw new Error("Resposta de importação inválida.");
        return `Linha ${error.line}: ${error.message}`;
      });
      setMessage(
        `${result.imported} resultado(s) registrado(s). ${errors.join(" ")}`,
      );
      if (result.imported > 0)
        void queryClient.invalidateQueries({ queryKey: ["orders"] });
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Falha ao importar.");
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
          Prepare a equipe e registre o retorno das inspeções.
        </p>
      </header>
      <div className="grid divide-y divide-border lg:grid-cols-[0.85fr_1.15fr] lg:divide-x lg:divide-y-0">
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
        <div className="space-y-4 p-5 sm:p-6">
          <div className="flex items-start gap-3">
            <span className="flex size-10 shrink-0 items-center justify-center rounded-lg border border-border bg-canvas text-muted">
              <FileSpreadsheet size={20} aria-hidden="true" />
            </span>
            <div>
              <h3 className="text-sm font-semibold text-content">
                Registrar resultados de campo
              </h3>
              <p className="mt-1 text-sm leading-6 text-muted">
                Baixe o modelo, preencha a coluna resultado e envie a planilha
                de volta.
              </p>
            </div>
          </div>
          <div className="rounded-lg border border-dashed border-control bg-canvas p-4 sm:p-5">
            <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
              <div>
                <p className="text-sm font-medium text-content">
                  Planilha preenchida
                </p>
                <p
                  id="field-file-help"
                  className="mt-1 text-xs leading-5 text-muted"
                >
                  XLSX ou CSV · até 1 MB · 500 ordens
                </p>
              </div>
              <Button
                variant="primary"
                disabled={busy}
                leftIcon={<Upload size={16} aria-hidden="true" />}
                onClick={() => uploadRef.current?.click()}
              >
                Selecionar planilha
              </Button>
            </div>
            <input
              ref={uploadRef}
              className="sr-only"
              tabIndex={-1}
              aria-describedby="field-file-help"
              aria-label="Importar resultados de campo"
              type="file"
              accept=".xlsx,.csv,text/csv,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
              disabled={busy}
              onChange={(event) => {
                void upload(event.target.files?.[0]);
                event.target.value = "";
              }}
            />
          </div>
          <Button
            variant="ghost"
            className="w-full sm:w-auto sm:px-0"
            disabled={busy}
            leftIcon={<Download size={16} aria-hidden="true" />}
            onClick={() => void template()}
          >
            Baixar modelo de resultados
          </Button>
          <p className="text-xs leading-5 text-muted">
            Cada linha válida é registrada. Se houver erros, corrija as linhas
            indicadas e reenvie.
          </p>
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
