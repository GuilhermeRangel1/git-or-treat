import { useEffect, useState } from "react";
import { AlertCircle } from "lucide-react";
import { ApiError } from "@/shared/api/client";
import type { UCHistory, UCHistoryItem, UCMeter, UCStatus } from "./contract";
import type { UCHistorySection } from "./uc360-state";
import { humanizeLimitation, statusLabel } from "./uc360-format";

const sectionLabels: Record<UCHistorySection, string> = {
  consumption: "Consumo",
  invoices: "Faturas e pagamentos",
  meters: "Medidores",
  distributed_generation: "Geração própria",
  interruptions: "Interrupções",
  calls: "Chamados",
};
const historyLabels: Record<string, string> = {
  invoice_id: "Fatura",
  event_id: "Evento",
  call_id: "Chamado",
  meter_id: "Medidor",
  competencia: "Competência",
  measured_energy_kwh: "Consumo medido",
  billed_energy_kwh: "Energia faturada",
  billed_amount: "Valor faturado",
  paid_amount: "Valor pago",
  due_date: "Vencimento",
  payment_date: "Data do pagamento",
  payment_status: "Situação do pagamento",
  currency_unit: "Moeda",
  installed_at: "Instalado em",
  removed_at: "Retirado em",
  capacity_kw: "Potência cadastrada",
  status: "Situação",
  feeder_id: "Alimentador",
  duration_hours: "Duração",
  opened_at: "Aberto em",
  category: "Categoria",
};
const historyColumns: Record<UCHistorySection, string[]> = {
  consumption: ["competencia", "measured_energy_kwh", "status"],
  invoices: [
    "invoice_id",
    "competencia",
    "billed_amount",
    "paid_amount",
    "billed_energy_kwh",
    "due_date",
    "payment_date",
    "payment_status",
  ],
  meters: ["meter_id", "installed_at", "removed_at"],
  distributed_generation: ["capacity_kw", "status"],
  interruptions: ["event_id", "competencia", "feeder_id", "duration_hours"],
  calls: ["call_id", "opened_at", "category"],
};
const money = new Intl.NumberFormat("pt-BR", {
  style: "currency",
  currency: "BRL",
});
const decimal = new Intl.NumberFormat("pt-BR", { maximumFractionDigits: 2 });

function historyValue(key: string, value: unknown) {
  if (value === null) return "Sem dado";
  if (key === "billed_amount" || key === "paid_amount")
    return money.format(Number(value));
  if (["measured_energy_kwh", "billed_energy_kwh"].includes(key))
    return `${decimal.format(Number(value))} kWh`;
  if (key === "capacity_kw") return `${decimal.format(Number(value))} kW`;
  if (key === "duration_hours") return `${decimal.format(Number(value))} h`;
  if (key === "payment_status")
    return (
      (
        {
          paid: "Paga",
          partial: "Parcial",
          unpaid: "Em aberto",
          unknown: "Situação desconhecida",
        } as Record<string, string>
      )[String(value)] ?? String(value)
    );
  if (["available", "empty", "partial", "unavailable"].includes(String(value)))
    return statusLabel(value as UCStatus);
  return String(value);
}

function historyRowKey(
  section: UCHistorySection,
  row: UCHistoryItem,
  index: number,
): string {
  switch (section) {
    case "consumption":
      return String(row.competencia);
    case "invoices":
      return String(row.invoice_id);
    case "meters":
      return `${row.meter_id}-${row.installed_at}`;
    case "distributed_generation":
      return `${row.capacity_kw}-${row.status}-${index}`;
    case "interruptions":
      return String(row.event_id);
    case "calls":
      return String(row.call_id);
  }
}

function emptyHistoryMessage(status: UCStatus) {
  switch (status) {
    case "empty":
      return "A fonte confirma cobertura neste período e nenhum registro para esta unidade.";
    case "partial":
      return "A fonte tem cobertura parcial; os registros conhecidos podem não representar todo o período.";
    case "unavailable":
      return "A cobertura desta fonte não está disponível; não é possível concluir se houve registros.";
    case "available":
      return "A fonte está disponível, mas não retornou registros para esta consulta.";
  }
}

export function ErrorMessage({
  error,
  retry,
}: {
  error: unknown;
  retry: () => void;
}) {
  const unavailable = error instanceof ApiError && error.status === 503;
  return (
    <div
      className="flex flex-wrap items-center gap-3 rounded-lg border border-danger p-3 text-sm text-danger"
      role="alert"
    >
      <AlertCircle size={18} aria-hidden="true" />
      {unavailable
        ? "Fonte de atendimento indisponível."
        : error instanceof ApiError && error.status === 404
          ? "A unidade informada não foi encontrada."
          : "Não foi possível carregar os dados da unidade."}
      <button
        className="underline underline-offset-2"
        type="button"
        onClick={retry}
      >
        Tentar novamente
      </button>
    </div>
  );
}

export function HistoryPanel({
  section,
  history,
  pending,
  error,
  historyPage,
  onRetry,
  onSelectSection,
  onPageChange,
}: {
  section: UCHistorySection | null;
  history?: UCHistory;
  pending: boolean;
  error: unknown;
  historyPage: number;
  onRetry: () => void;
  onSelectSection: (section: UCHistorySection) => void;
  onPageChange: (page: number) => void;
}) {
  return (
    <section className="grid gap-3 rounded-xl bg-surface p-4 sm:p-5">
      <h3 className="font-heading text-lg font-semibold">
        Histórico da unidade
      </h3>
      <div
        className="flex flex-wrap gap-2"
        role="group"
        aria-label="Fontes de histórico"
      >
        {(Object.keys(sectionLabels) as UCHistorySection[]).map((item) => (
          <button
            key={item}
            type="button"
            aria-pressed={section === item}
            onClick={() => onSelectSection(item)}
            className={`min-h-10 rounded-lg border px-3 text-sm focus-visible:outline-2 focus-visible:outline-brand ${section === item ? "border-brand bg-canvas text-content" : "border-control text-muted"}`}
          >
            {sectionLabels[item]}
          </button>
        ))}
      </div>
      {section && pending && (
        <p role="status" className="text-sm text-muted">
          Carregando {sectionLabels[section].toLowerCase()}…
        </p>
      )}
      {error != null && <ErrorMessage error={error} retry={onRetry} />}
      {history && (
        <>
          <p className="text-sm text-muted">
            {statusLabel(history.metadata.status)} · {history.pagination.total}{" "}
            {history.pagination.total === 1 ? "registro" : "registros"} · fonte{" "}
            {history.metadata.source.version}
          </p>
          {history.metadata.limitations.length > 0 && (
            <ul
              className="grid gap-1 text-sm text-muted"
              aria-label="Limitações da fonte"
            >
              {history.metadata.limitations.map((limitation) => (
                <li key={limitation}>{humanizeLimitation(limitation)}</li>
              ))}
            </ul>
          )}
          {history.data.items.length > 0 && section ? (
            <>
              <div className="hidden overflow-x-auto rounded-lg border border-control md:block">
                <table className="w-full border-collapse text-left text-sm">
                  <caption className="sr-only">
                    Histórico de {sectionLabels[section].toLowerCase()} da
                    unidade
                  </caption>
                  <thead className="bg-canvas text-muted">
                    <tr>
                      {historyColumns[section].map((key) => (
                        <th
                          className="whitespace-nowrap px-3 py-2 font-semibold"
                          key={key}
                          scope="col"
                        >
                          {historyLabels[key] ?? key}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {history.data.items.map((row, index) => (
                      <tr
                        className="border-t border-control"
                        key={historyRowKey(section, row, index)}
                      >
                        {historyColumns[section].map((key) => (
                          <td
                            className="max-w-64 break-words px-3 py-2 text-content"
                            key={key}
                          >
                            {historyValue(key, row[key])}
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <ul
                className="grid gap-2 md:hidden"
                aria-label={`Registros de ${sectionLabels[section]}`}
              >
                {history.data.items.map((row, index) => (
                  <li
                    key={historyRowKey(section, row, index)}
                    className="rounded-lg border border-control p-3"
                  >
                    <dl className="grid grid-cols-[minmax(7rem,0.8fr)_minmax(0,1.2fr)] gap-x-3 gap-y-2 text-sm">
                      {historyColumns[section].map((key) => (
                        <div className="contents" key={key}>
                          <dt className="text-muted">
                            {historyLabels[key] ?? key}
                          </dt>
                          <dd className="break-words text-content">
                            {historyValue(key, row[key])}
                          </dd>
                        </div>
                      ))}
                    </dl>
                  </li>
                ))}
              </ul>
            </>
          ) : (
            <p className="text-sm text-muted">
              {emptyHistoryMessage(history.metadata.status)}
            </p>
          )}
          {history.pagination.total_pages > 1 && (
            <div className="flex flex-wrap items-center gap-3">
              <button
                type="button"
                disabled={historyPage <= 1}
                onClick={() => onPageChange(historyPage - 1)}
                className="min-h-10 rounded border border-control px-3 disabled:opacity-50"
              >
                Anterior
              </button>
              <span className="text-sm text-muted">
                Página {history.pagination.page} de{" "}
                {history.pagination.total_pages}
              </span>
              <button
                type="button"
                disabled={historyPage >= history.pagination.total_pages}
                onClick={() => onPageChange(historyPage + 1)}
                className="min-h-10 rounded border border-control px-3 disabled:opacity-50"
              >
                Próxima
              </button>
            </div>
          )}
        </>
      )}
    </section>
  );
}

export function EvidenceDialog({
  sectionStatus,
  meter,
  limitations,
  onSelectHistory,
}: {
  sectionStatus: Record<string, UCStatus>;
  meter: UCMeter | null;
  limitations: string[];
  onSelectHistory: (section: UCHistorySection) => void;
}) {
  const [open, setOpen] = useState(false);
  useEffect(() => {
    const dialog =
      document.querySelector<HTMLDialogElement>("#uc-details-dialog");
    if (!dialog) return;
    if (open && !dialog.open) dialog.showModal();
    else if (!open && dialog.open) dialog.close();
  }, [open]);

  return (
    <>
      <button
        type="button"
        onClick={() => setOpen(true)}
        className="min-h-11 rounded-lg bg-content px-4 text-sm text-surface"
      >
        Ver detalhes
      </button>
      <dialog
        id="uc-details-dialog"
        aria-labelledby="uc-details-title"
        onCancel={() => setOpen(false)}
        onClose={() => setOpen(false)}
        className="m-auto w-[min(640px,calc(100%-2rem))] rounded-xl bg-surface p-5 text-content backdrop:bg-black/40"
      >
        <h3
          id="uc-details-title"
          className="font-heading text-lg font-semibold"
        >
          Evidências e limites
        </h3>
        <p className="mt-3 text-sm text-muted">
          Cadastro e métricas usam cobertura declarada por fonte. Uma ausência
          conhecida é diferente de zero ou de uma fonte indisponível. Chamados
          disponibilizam apenas identificador, abertura e categoria nesta
          demonstração.
        </p>
        <h4 className="mt-4 text-sm font-semibold">Fontes da unidade</h4>
        <ul className="mt-2 grid gap-2 text-sm">
          {(Object.keys(sectionLabels) as UCHistorySection[]).map((section) => (
            <li
              key={section}
              className="flex flex-wrap items-center justify-between gap-2 border-b border-control pb-2"
            >
              <span>
                {sectionLabels[section]} ·{" "}
                {statusLabel(sectionStatus[section] ?? "unavailable")}
              </span>
              <button
                type="button"
                className="underline underline-offset-2"
                onClick={() => {
                  onSelectHistory(section);
                  setOpen(false);
                }}
              >
                Abrir histórico
              </button>
            </li>
          ))}
        </ul>
        {meter && (
          <p className="mt-3 text-sm">
            Medidor vigente no snapshot: {meter.meter_id}, instalado em{" "}
            {meter.installed_at}
            {meter.removed_at ? `, retirado em ${meter.removed_at}` : ""}.
          </p>
        )}
        <ul className="mt-3 grid gap-2 text-sm">
          {[...new Set(limitations)].map((item, index) => (
            <li key={`${index}-${item}`}>{humanizeLimitation(item)}</li>
          ))}
        </ul>
        <form method="dialog" className="mt-4 text-right">
          <button
            className="min-h-10 rounded border border-control px-4"
            onClick={() => setOpen(false)}
          >
            Fechar
          </button>
        </form>
      </dialog>
    </>
  );
}
