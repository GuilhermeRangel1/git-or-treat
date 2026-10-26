import { Search } from "lucide-react";
import type { RefObject } from "react";
import type { UCHistory, UCOverview } from "./contract";
import { ErrorMessage, EvidenceDialog, HistoryPanel } from "./UC360History";
import UC360OverviewTable from "./UC360OverviewTable";
import UC360Interpretation from "./UC360Interpretation";
import { UC360Comparison, UC360SupportMetrics } from "./UC360Metrics";
import UC360PeriodForm from "./UC360PeriodForm";
import { formatUCDate, formatUCPower, statusLabel } from "./uc360-format";
import type { UCHistorySection } from "./uc360-state";

type Props = {
  unit: {
    id: string;
    overview: {
      data: UCOverview | undefined;
      pending: boolean;
      fetching: boolean;
      error: Error | null;
    };
    history: {
      data: UCHistory | undefined;
      pending: boolean;
      error: Error | null;
    };
    filters: {
      start: string;
      end: string;
      section: UCHistorySection | "";
      historyPage: number;
      invalid: boolean;
      historyOpen: boolean;
    };
  };
  disclosureRef: RefObject<HTMLDetailsElement | null>;
  actions: {
    onOverviewRetry: () => void;
    onHistoryRetry: () => void;
    onNewSearch: () => void;
    onHistoryOpen: (open: boolean) => void;
    onSelectHistory: (section: UCHistorySection) => void;
    onHistorySection: (section: UCHistorySection) => void;
    onHistoryPage: (page: number) => void;
    onPeriodApply: (start: string, end: string) => void;
  };
};

function sourceDate(value: string) {
  const timestamp = Date.parse(value);
  return Number.isFinite(timestamp)
    ? new Intl.DateTimeFormat("pt-BR", {
        day: "2-digit",
        month: "2-digit",
        year: "numeric",
        timeZone: "UTC",
      }).format(timestamp)
    : value;
}

export default function UC360Detail({ unit, disclosureRef, actions }: Props) {
  const selected = unit.overview.data?.data;
  const metadata = unit.overview.data?.metadata;

  return (
    <>
      <header className="grid min-w-0 gap-2">
        <h1 className="font-heading text-[26px] leading-[34px] font-semibold text-content lg:text-[32px] lg:leading-10">
          {selected?.profile.uc_id ?? unit.id}
        </h1>
        {selected ? (
          <p className="text-sm text-muted">
            {selected.profile.customer_name?.trim() && (
              <>{selected.profile.customer_name.trim()} · </>
            )}
            {selected.profile.municipio} / {selected.profile.bairro} ·{" "}
            {selected.profile.classe}
          </p>
        ) : (
          <p className="text-sm text-muted">UC {unit.id}</p>
        )}
        {metadata && (
          <p className="mt-4 text-xs text-muted">
            {metadata.source.is_demo
              ? "Demonstração · dados sintéticos"
              : "Dados da fonte"}{" "}
            · atualização {sourceDate(metadata.source.updated_at)}
          </p>
        )}
      </header>
      {!unit.filters.invalid && (
        <>
          {unit.overview.pending && (
            <p
              role="status"
              className="rounded-lg bg-surface p-4 text-sm text-muted"
            >
              Carregando cadastro e comparação…
            </p>
          )}
          {unit.overview.error && (
            <div className="grid justify-items-start gap-3">
              <ErrorMessage
                error={unit.overview.error}
                retry={actions.onOverviewRetry}
              />
              {!selected && (
                <button
                  type="button"
                  onClick={actions.onNewSearch}
                  className="inline-flex min-h-11 items-center gap-2 rounded-lg border border-control px-4 text-sm text-content focus-visible:outline-2 focus-visible:outline-brand"
                >
                  <Search size={16} aria-hidden="true" />
                  Nova busca
                </button>
              )}
            </div>
          )}
          {selected && metadata && (
            <>
              <UC360PeriodForm
                appliedStart={unit.filters.start}
                appliedEnd={unit.filters.end}
                period={selected.period}
                onApply={actions.onPeriodApply}
              />
              <UC360Comparison comparison={selected.comparison} />
              <UC360SupportMetrics data={selected} />
              <UC360OverviewTable comparison={selected.comparison} />
              <section className="grid gap-3 rounded-xl bg-surface p-4 sm:p-5">
                <h2 className="font-heading text-lg font-semibold">
                  Contexto da unidade
                </h2>
                <p className="text-sm text-muted">
                  Fontes reunidas na mesma jornada, com ausências explícitas.
                </p>
                <ul className="grid gap-1 text-sm text-content">
                  <li>
                    {selected.current_meter.item ? (
                      <>Medidor: {selected.current_meter.item.meter_id}</>
                    ) : selected.current_meter.status === "empty" ? (
                      "Nenhum medidor vigente no snapshot; consulte o histórico de medidores"
                    ) : (
                      <>Medidor: {statusLabel(selected.current_meter.status)}</>
                    )}
                    {selected.current_meter.item?.removed_at
                      ? ` · retirado em ${formatUCDate(selected.current_meter.item.removed_at)}`
                      : ""}
                    .
                  </li>
                  <li>
                    Interrupções e rede:{" "}
                    {statusLabel(
                      selected.section_status.interruptions ?? "unavailable",
                    )}
                    .
                  </li>
                  <li>
                    Chamados e atendimento:{" "}
                    {statusLabel(
                      selected.section_status.calls ?? "unavailable",
                    )}
                    .
                  </li>
                  <li>
                    Geração própria:{" "}
                    {selected.distributed_generation.items.length
                      ? selected.distributed_generation.items
                          .map((item) => formatUCPower(item.capacity_kw))
                          .join(", ")
                      : statusLabel(selected.distributed_generation.status)}
                    . Potência não representa energia compensada.
                  </li>
                </ul>
                <div className="flex flex-wrap gap-2">
                  <EvidenceDialog
                    sectionStatus={selected.section_status}
                    meter={selected.current_meter.item}
                    currentMeterStatus={selected.current_meter.status}
                    limitations={[
                      ...new Set([
                        ...metadata.limitations,
                        ...selected.current_meter.limitations,
                        ...selected.distributed_generation.limitations,
                      ]),
                    ]}
                    onSelectHistory={actions.onSelectHistory}
                  />
                  <button
                    type="button"
                    onClick={actions.onNewSearch}
                    className="inline-flex min-h-11 items-center gap-2 rounded-lg border border-control px-4 text-sm text-content"
                  >
                    <Search size={16} aria-hidden="true" />
                    Nova busca
                  </button>
                </div>
              </section>
              <details
                ref={disclosureRef}
                open={unit.filters.historyOpen}
                onToggle={(event) =>
                  actions.onHistoryOpen(event.currentTarget.open)
                }
                className="grid min-w-0 gap-3 rounded-xl bg-surface p-4 sm:p-5"
              >
                <summary className="cursor-pointer font-heading text-lg font-semibold">
                  Históricos por fonte
                </summary>
                <HistoryPanel
                  section={unit.filters.section || "consumption"}
                  history={unit.history.data}
                  pending={unit.history.pending}
                  error={unit.history.error}
                  historyPage={unit.filters.historyPage}
                  onRetry={actions.onHistoryRetry}
                  onSelectSection={actions.onHistorySection}
                  onPageChange={actions.onHistoryPage}
                />
              </details>
              {unit.overview.fetching && !unit.overview.pending && (
                <p role="status" className="text-sm text-muted">
                  Atualizando período…
                </p>
              )}
              <UC360Interpretation data={selected} />
            </>
          )}
        </>
      )}
    </>
  );
}
