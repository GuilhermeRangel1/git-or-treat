import { useRef, useState } from "react";
import { apiClient, ApiError } from "@/shared/api/client";
import Modal from "@/shared/ui/Modal";
import { withGoldPublication } from "@/shared/analytics/goldPublication";
const inspectionControl =
  "min-h-11 w-full rounded-lg border border-control bg-canvas px-3 text-sm text-content focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand";
import Button from "@/shared/ui/Button";
import { Download, FileSpreadsheet, Upload, ArrowUpRight } from "lucide-react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useGoldPublicationKey } from "@/shared/analytics/goldPublication";

const exportHelp =
  "Exporte todas as UCs ou escolha um recorte por categoria, município, bairro e classe.";

function exportError(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.status === 422)
      return "Não existem UCs para essa combinação de filtros, ou uma das opções não é válida. Revise município, bairro, categoria e classe.";
    if (error.status === 401 || error.status === 403)
      return "Sua sessão não permite exportar esta fila. Entre novamente ou solicite acesso.";
    if (error.status === 409)
      return "A fila foi atualizada. Atualize a página e escolha os filtros novamente.";
    return "Não foi possível consultar a fila agora. Tente novamente em instantes.";
  }
  return "Não foi possível preparar a exportação. Tente novamente.";
}

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

export default function FieldFiles({
  request = "",
  mode = "all",
}: {
  request?: string;
  mode?: "all" | "export" | "results";
}) {
  const queryClient = useQueryClient();
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [hasLineErrors, setHasLineErrors] = useState(false);
  const [open, setOpen] = useState(false);
  const [scope, setScope] = useState("all");
  const [options, setOptions] = useState<Record<string, string[]>>({});
  const [filters, setFilters] = useState<Record<string, string>>({});
  const [neighborhoods, setNeighborhoods] = useState<
    { municipio: string; bairro: string }[]
  >([]);
  const trigger = useRef<HTMLButtonElement>(null);
  const templateTrigger = useRef<HTMLButtonElement>(null);
  const [templateOpen, setTemplateOpen] = useState(false);
  const [templateFormat, setTemplateFormat] = useState<"csv" | "xlsx">("xlsx");
  const uploadRef = useRef<HTMLInputElement>(null);
  const publication = useGoldPublicationKey();
  const countParams = new URLSearchParams({ count_only: "true" });
  if (scope === "filtered")
    for (const [key, value] of Object.entries(filters))
      if (value) countParams.set(key, value);
  const countRequest = countParams.toString();
  const count = useQuery({
    queryKey: ["inspection-export-count", publication, countRequest],
    enabled: open,
    retry: false,
    queryFn: async ({ signal }) => {
      const value = await apiClient<unknown>(
        `/api/v1/inspections/field-queue/export?${withGoldPublication(new URLSearchParams(countRequest))}`,
        { signal },
      );
      if (
        !value ||
        typeof value !== "object" ||
        !("count" in value) ||
        !Number.isSafeInteger(value.count) ||
        Number(value.count) < 0
      )
        throw new Error("Contagem inválida.");
      return Number(value.count);
    },
  });
  async function template(format: "xlsx" | "csv" = "xlsx") {
    setBusy(true);
    setMessage("");
    try {
      const value = await apiClient<unknown>(
        `/api/v1/inspections/field-results/template?format=${format}`,
      );
      if (format === "csv") {
        if (
          !value ||
          typeof value !== "object" ||
          !("csv" in value) ||
          typeof value.csv !== "string"
        )
          throw new Error("Modelo CSV inválido.");
        download("resultados-campo.csv", value.csv);
        setTemplateOpen(false);
        setMessage(
          "Modelo CSV baixado. Preencha resultado sem alterar ordem, versão e UC.",
        );
        return;
      }
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
      setTemplateOpen(false);
      setMessage(
        `${value.count} ordem(ns) em andamento no modelo. Preencha a coluna resultado e envie a planilha.`,
      );
    } catch (error) {
      setMessage(
        error instanceof ApiError &&
          (error.status === 500 || error.status === 503)
          ? "Não foi possível gerar o Excel agora. Tente baixar o modelo CSV ou solicite a atualização do serviço de planilhas."
          : error instanceof Error
            ? error.message
            : "Não foi possível baixar o modelo.",
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
      if ("neighborhoods" in value) {
        if (
          !Array.isArray(value.neighborhoods) ||
          !value.neighborhoods.every(
            (item) =>
              item &&
              typeof item === "object" &&
              typeof item.municipio === "string" &&
              typeof item.bairro === "string",
          )
        )
          throw new Error("Bairros inválidos.");
        setNeighborhoods(value.neighborhoods);
      } else setNeighborhoods([]);
    } catch (error) {
      setMessage(exportError(error));
    } finally {
      setBusy(false);
    }
  }
  async function exportQueue() {
    if (count.isFetching || count.isError || !count.data || count.data > 50000)
      return;
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
      setMessage(exportError(error));
    } finally {
      setBusy(false);
    }
  }
  async function upload(file: File | undefined) {
    if (!file) return;
    setHasLineErrors(false);
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
      setHasLineErrors(errors.length > 0);
      setMessage(
        `${result.imported} resultado(s) registrado(s). ${result.imported} ordem(ns) concluída(s). ${errors.join(" ")}`,
      );
      if (result.imported > 0)
        void queryClient.invalidateQueries({ queryKey: ["orders"] });
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Falha ao importar.");
    } finally {
      setBusy(false);
    }
  }
  const fileInput = (
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
  );
  const selectFileButton = (
    <Button
      variant="primary"
      disabled={busy}
      leftIcon={<Upload size={16} aria-hidden="true" />}
      onClick={() => uploadRef.current?.click()}
    >
      Selecionar planilha
    </Button>
  );
  function openTemplate() {
    setMessage("");
    setHasLineErrors(false);
    setTemplateOpen(true);
  }
  return (
    <section
      aria-label="Arquivos de campo"
      className={
        mode === "results"
          ? "contents"
          : mode === "export"
            ? "contents"
            : "overflow-hidden rounded-xl border border-border bg-surface"
      }
    >
      {mode === "results" ? (
        <div className="flex flex-col items-end gap-1.5 max-md:w-full max-md:items-start">
          <div className="flex flex-wrap gap-3 max-md:w-full">
            <Button
              variant="secondary"
              className="w-52 max-w-full whitespace-nowrap"
              disabled={busy}
              leftIcon={<Download size={16} aria-hidden="true" />}
              ref={templateTrigger}
              onClick={openTemplate}
            >
              Baixar modelo
            </Button>
            <Button
              variant="primary"
              className="w-52 max-w-full whitespace-nowrap"
              disabled={busy}
              aria-describedby="field-file-help"
              leftIcon={<Upload size={16} aria-hidden="true" />}
              onClick={() => uploadRef.current?.click()}
            >
              Importar resultados
            </Button>
          </div>
          <p id="field-file-help" className="text-xs text-muted md:text-right">
            Baixe o modelo, preencha a coluna resultado e importe de volta. XLSX
            ou CSV, até 1 MB, 500 ordens.
          </p>
          {fileInput}
        </div>
      ) : mode === "export" ? (
        <div className="flex justify-end max-md:w-full md:ml-auto">
          <Button
            variant="secondary"
            size="sm"
            className="min-h-11 whitespace-nowrap text-sm! max-md:w-full md:min-h-9"
            disabled={busy}
            ref={trigger}
            title={exportHelp}
            aria-describedby="field-export-help"
            leftIcon={<Download size={16} aria-hidden="true" />}
            onClick={() => void openExport()}
          >
            Exportar fila
          </Button>
          <span id="field-export-help" className="sr-only">
            {exportHelp}
          </span>
        </div>
      ) : (
        <>
          <header className="border-b border-border px-5 py-4 sm:px-6">
            <h2 className="font-heading text-lg font-semibold text-content">
              Arquivos de campo
            </h2>
            <p className="mt-1 text-sm leading-6 text-muted">
              Prepare a fila de inspeção para enviar à equipe de campo.
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
                  {exportHelp}
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
                    Baixe o modelo, preencha a coluna resultado e envie a
                    planilha de volta.
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
                  {selectFileButton}
                </div>
                {fileInput}
              </div>
              <Button
                variant="ghost"
                className="w-full sm:w-auto sm:px-0"
                disabled={busy}
                leftIcon={<Download size={16} aria-hidden="true" />}
                ref={templateTrigger}
                onClick={openTemplate}
              >
                Baixar modelo de resultados
              </Button>
              <p className="text-xs leading-5 text-muted">
                Cada linha válida é registrada. Se houver erros, corrija as
                linhas indicadas e reenvie.
              </p>
            </div>
          </div>
        </>
      )}
      <Modal
        open={templateOpen}
        onClose={() => setTemplateOpen(false)}
        triggerRef={templateTrigger}
        size="md"
        header="inline"
        title="Baixar modelo de resultados"
        closeLabel="Fechar modelo de resultados"
      >
        <div className="space-y-5">
          <fieldset className="grid gap-3 sm:grid-cols-2">
            <legend className="mb-3 text-sm font-medium">
              Em qual formato você quer baixar?
            </legend>
            {(["xlsx", "csv"] as const).map((format) => (
              <label
                key={format}
                className={`flex cursor-pointer items-start gap-3 rounded-lg border p-4 text-sm ${templateFormat === format ? "border-brand bg-canvas" : "border-border"}`}
              >
                <input
                  className="mt-1 size-4 accent-brand"
                  type="radio"
                  name="template-format"
                  value={format}
                  checked={templateFormat === format}
                  disabled={busy}
                  onChange={() => setTemplateFormat(format)}
                />
                <span>
                  <span className="block font-medium">
                    {format === "xlsx" ? "Excel (XLSX)" : "CSV"}
                  </span>
                  <span className="mt-1 block text-xs leading-5 text-muted">
                    {format === "xlsx"
                      ? "Planilha formatada para preencher no Excel."
                      : "Arquivo de texto separado por ponto e vírgula."}
                  </span>
                </span>
              </label>
            ))}
          </fieldset>
          <p className="text-sm leading-6 text-muted">
            O modelo inclui as ordens em andamento. Preencha a coluna resultado
            e envie o arquivo pelo portal.
          </p>
          <div className="flex flex-col-reverse gap-2 border-t border-border pt-4 sm:flex-row sm:justify-end">
            <Button
              variant="ghost"
              disabled={busy}
              onClick={() => setTemplateOpen(false)}
            >
              Cancelar
            </Button>
            <Button
              variant="primary"
              isLoading={busy}
              leftIcon={<Download size={16} aria-hidden="true" />}
              onClick={() => void template(templateFormat)}
            >
              Baixar {templateFormat.toUpperCase()}
            </Button>
          </div>
          {message ? (
            <p role="status" className="text-sm leading-6">
              {message}
            </p>
          ) : null}
        </div>
      </Modal>
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
                      disabled={key === "bairro" && !filters.municipio}
                      onChange={(event) =>
                        setFilters((previous) => ({
                          ...previous,
                          [key]: event.target.value,
                          ...(key === "municipio" ? { bairro: "" } : {}),
                        }))
                      }
                    >
                      <option value="">
                        {key === "bairro" && !filters.municipio
                          ? "Selecione um município primeiro"
                          : "Todas as opções"}
                      </option>
                      {(key === "bairro"
                        ? neighborhoods
                            .filter(
                              (item) => item.municipio === filters.municipio,
                            )
                            .map((item) => item.bairro)
                        : (options[key] ?? [])
                      ).map((value) => (
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
          <p
            role="status"
            className="rounded-lg border border-border bg-canvas p-4 text-sm font-medium"
            aria-live="polite"
          >
            {count.isFetching || count.isPending
              ? "Contando UCs…"
              : count.isError
                ? exportError(count.error)
                : count.data === 0
                  ? "Não existem UCs com esses filtros. Altere a seleção para exportar."
                  : count.data > 50000
                    ? `${count.data?.toLocaleString("pt-BR")} UCs encontradas. Refine os filtros para ficar dentro do limite de 50.000.`
                    : `${count.data?.toLocaleString("pt-BR")} UC(s) serão incluídas no arquivo.`}
          </p>
          <div className="flex flex-col-reverse gap-2 border-t border-border pt-4 sm:flex-row sm:justify-end">
            <Button variant="ghost" onClick={() => setOpen(false)}>
              Cancelar
            </Button>
            <Button
              variant="primary"
              disabled={
                busy ||
                count.isFetching ||
                count.isError ||
                !count.data ||
                count.data > 50000
              }
              leftIcon={<Download size={16} aria-hidden="true" />}
              onClick={() => void exportQueue()}
            >
              Baixar CSV
            </Button>
          </div>
          <p role="status">{busy ? "Processando…" : message}</p>
        </div>
      </Modal>
      {!open && !templateOpen && (busy || message) ? (
        <p
          role="status"
          className={
            mode === "results"
              ? "min-w-0 basis-full rounded-xl border border-border bg-surface px-5 py-4 text-sm leading-6 break-words whitespace-pre-wrap sm:px-6"
              : mode === "export"
                ? "min-w-0 basis-full rounded-xl border border-border bg-canvas px-5 py-4 text-sm leading-6 break-words whitespace-pre-wrap sm:px-6"
                : "border-t border-border bg-canvas px-5 py-4 text-sm leading-6 break-words whitespace-pre-wrap sm:px-6"
          }
        >
          {busy ? "Processando arquivo…" : message}
          {mode === "results" && !busy && hasLineErrors ? (
            <span className="mt-1 block text-xs leading-5 text-muted">
              Cada linha válida é registrada. Se houver erros, corrija as linhas
              indicadas e reenvie.
            </span>
          ) : null}
        </p>
      ) : null}
    </section>
  );
}
