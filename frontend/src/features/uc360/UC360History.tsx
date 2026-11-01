import { useRef } from "react";
import { AlertCircle, ArrowUpRight, X } from "lucide-react";
import { ApiError } from "@/shared/api/client";
import type { UCHistory, UCHistoryItem, UCMeter, UCStatus } from "./contract";
import type { UCHistorySection } from "./uc360-state";
import {
  formatUCCompetence,
  formatUCDate,
  humanizeLimitation,
  statusLabel,
} from "./uc360-format";

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
  declared_status: "Situação declarada na fatura",
  declared_open_amount: "Valor nominal declarado em aberto",
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
  consumption: [
    "competencia",
    "measured_energy_kwh",
    "billed_amount",
    "status",
  ],
  invoices: [
    "invoice_id",
    "competencia",
    "billed_amount",
    "paid_amount",
    "billed_energy_kwh",
    "due_date",
    "payment_date",
    "payment_status",
    "declared_status",
    "declared_open_amount",
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
  if (value == null) return "Sem dado";
  if (key === "competencia") return formatUCCompetence(String(value));
  if (
    [
      "due_date",
      "payment_date",
      "installed_at",
      "removed_at",
      "opened_at",
    ].includes(key)
  )
    return formatUCDate(String(value));
  if (["billed_amount", "paid_amount", "declared_open_amount"].includes(key))
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

function coverageMessage(status: UCStatus) {
  switch (status) {
    case "available":
      return "Fonte disponível para a consulta.";
    case "empty":
      return "A fonte confirma cobertura e nenhum registro neste recorte.";
    case "partial":
      return "Cobertura parcial; esta resposta pode não incluir todo o recorte.";
    case "unavailable":
      return "Cobertura indisponível; não é possível concluir se há registros.";
  }
}

function currentMeterMessage(meter: UCMeter | null, status?: UCStatus) {
  if (meter) {
    if (status === "partial")
      return `Possível medidor na referência da Gold: ${meter.meter_id}, instalado em ${formatUCDate(meter.installed_at)}. A indicação depende das datas disponíveis; consulte as limitações e o histórico.`;
    return `Vigente no snapshot: ${meter.meter_id}, instalado em ${formatUCDate(meter.installed_at)}. Consulte o histórico para vínculos anteriores e retiradas.`;
  }
  switch (status) {
    case "empty":
      return "Nenhum medidor vigente registrado no snapshot.";
    case "partial":
      return "O vínculo vigente está ambíguo; não é possível escolher um medidor.";
    case "unavailable":
      return "A cobertura do medidor vigente está indisponível; não é possível determinar ausência.";
    case "available":
      return "A fonte do snapshot está disponível, mas não retornou medidor vigente.";
    default:
      return "O estado do medidor vigente não foi informado neste diálogo.";
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
  const columns = section
    ? historyColumns[section].filter((key) => {
        const goldV2 =
          history?.metadata.source.version.startsWith("gold-csv-v2:");
        if (
          section === "invoices" &&
          goldV2 &&
          [
            "paid_amount",
            "billed_energy_kwh",
            "payment_date",
            "payment_status",
          ].includes(key)
        )
          return false;
        return (
          !["declared_status", "declared_open_amount"].includes(key) ||
          history?.metadata.source.kind === "gold_csv"
        );
      })
    : [];
  return (
    <section className="grid min-w-0 gap-3 rounded-xl bg-surface p-4 sm:p-5">
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
          <p className="min-w-0 break-all text-sm text-muted">
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
                      {columns.map((key) => (
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
                        {columns.map((key) => (
                          <td
                            className="max-w-64 px-3 py-2 [overflow-wrap:anywhere] text-content"
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
                      {columns.map((key) => (
                        <div className="contents" key={key}>
                          <dt className="text-muted">
                            {historyLabels[key] ?? key}
                          </dt>
                          <dd className="[overflow-wrap:anywhere] text-content">
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
  currentMeterStatus,
  limitations,
  onSelectHistory,
}: {
  sectionStatus: Record<string, UCStatus>;
  meter: UCMeter | null;
  currentMeterStatus?: UCStatus;
  limitations: string[];
  onSelectHistory: (section: UCHistorySection) => void;
}) {
  const dialogRef = useRef<HTMLDialogElement>(null);
  const titleRef = useRef<HTMLHeadingElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const openDialog = () => {
    const dialog = dialogRef.current;
    if (!dialog || dialog.open) return;
    dialog.showModal();
    titleRef.current?.focus();
  };
  const closeDialog = () => dialogRef.current?.close();
  const selectHistory = (section: UCHistorySection) => {
    closeDialog();
    onSelectHistory(section);
  };

  const sourceGroups: {
    title: string;
    sections: UCHistorySection[];
    note?: string;
  }[] = [
    {
      title: "Consumo e leituras",
      sections: ["consumption"],
      note: "Mês sem leitura só é uma lacuna confirmada quando a cobertura daquela competência é conhecida; fonte indisponível não demonstra ausência.",
    },
    {
      title: "Medidor",
      sections: ["meters"],
      note: currentMeterMessage(meter, currentMeterStatus),
    },
    {
      title: "Faturas e pagamentos",
      sections: ["invoices"],
      note: "Valores faturados e pagos permanecem separados; pagamento é informação da fatura, não um fluxo de caixa separado.",
    },
    {
      title: "Geração própria",
      sections: ["distributed_generation"],
      note: "O cadastro informa potência em kW; não representa energia compensada.",
    },
    {
      title: "Interrupções e chamados",
      sections: ["interruptions", "calls"],
    },
  ];

  return (
    <>
      <button
        ref={triggerRef}
        type="button"
        onClick={openDialog}
        className="inline-flex min-h-11 items-center gap-2 rounded-lg bg-content px-4 text-sm text-surface"
      >
        <ArrowUpRight size={16} aria-hidden="true" />
        Ver detalhes
      </button>
      <dialog
        ref={dialogRef}
        id="uc-details-dialog"
        aria-labelledby="uc-details-title"
        onClose={() => triggerRef.current?.focus()}
        className="m-auto h-dvh w-screen max-h-dvh max-w-none open:grid grid-rows-[auto_minmax(0,1fr)_auto] overflow-hidden rounded-none bg-surface p-0 text-content shadow-xl backdrop:bg-black/50 sm:h-[min(678px,calc(100dvh-32px))] sm:max-h-[min(678px,calc(100dvh-32px))] sm:w-[calc(100%-2rem)] sm:max-w-[800px] sm:rounded-xl"
      >
        <header className="p-4 pb-2 sm:p-8 sm:pb-4">
          <h3
            ref={titleRef}
            id="uc-details-title"
            tabIndex={-1}
            className="font-heading text-[26px] leading-8 font-semibold focus-visible:outline-2 focus-visible:outline-brand sm:text-[32px] sm:leading-10"
          >
            Histórico e fontes da UC
          </h3>
          <p className="mt-2 text-sm text-muted">
            A cobertura é informada por fonte. Ausência confirmada, cobertura
            parcial e indisponibilidade têm significados diferentes.
          </p>
        </header>
        <div className="min-h-0 overflow-y-auto overscroll-contain px-4 pb-4 sm:px-8 sm:pb-4">
          <div className="grid gap-4 sm:gap-5">
            {sourceGroups.map((group) => (
              <section
                key={group.title}
                aria-labelledby={`uc-source-${group.sections[0]}`}
                className="grid gap-2"
              >
                <h4
                  id={`uc-source-${group.sections[0]}`}
                  className="text-sm font-semibold sm:text-base"
                >
                  {group.title}
                </h4>
                {group.note && (
                  <p className="text-sm text-muted">{group.note}</p>
                )}
                <ul className="grid gap-2">
                  {group.sections.map((section) => {
                    const status = sectionStatus[section] ?? "unavailable";
                    return (
                      <li
                        className="flex flex-wrap items-center justify-between gap-x-4 gap-y-1"
                        key={section}
                      >
                        <div className="grid min-w-0 gap-1 text-sm">
                          <span className="font-medium">
                            {sectionLabels[section]} · {statusLabel(status)}
                          </span>
                          <span className="text-muted">
                            {coverageMessage(status)}
                          </span>
                        </div>
                        <button
                          type="button"
                          className="min-h-10 shrink-0 text-sm text-brand underline underline-offset-2 focus-visible:outline-2 focus-visible:outline-brand"
                          onClick={() => selectHistory(section)}
                        >
                          Abrir histórico
                        </button>
                      </li>
                    );
                  })}
                </ul>
              </section>
            ))}
            <section
              aria-labelledby="uc-source-limitations"
              className="grid gap-2"
            >
              <h4 id="uc-source-limitations" className="text-sm font-semibold">
                Lacunas e limitações
              </h4>
              {limitations.length > 0 ? (
                <ul className="grid gap-2 text-sm text-muted">
                  {[...new Set(limitations)].map((item) => (
                    <li className="break-words" key={item}>
                      {humanizeLimitation(item)}
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="text-sm text-muted">
                  O overview não declarou limitações adicionais. Consulte o
                  estado de cobertura de cada fonte acima.
                </p>
              )}
              <p className="text-sm text-muted">
                Consulte a cobertura informada para os dados de atendimento.
                Nenhuma lacuna deve ser interpretada como valor zero ou causa da
                variação da conta.
              </p>
            </section>
          </div>
        </div>
        <form method="dialog" className="bg-surface px-4 pb-4 sm:px-8 sm:pb-8">
          <button
            autoFocus
            type="submit"
            aria-label="Fechar"
            className="inline-flex size-11 items-center justify-center rounded-full text-content hover:bg-surface-hover focus-visible:outline-2 focus-visible:outline-brand"
          >
            <X size={20} aria-hidden="true" />
          </button>
        </form>
      </dialog>
    </>
  );
}
