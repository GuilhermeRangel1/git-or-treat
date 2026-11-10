import { Search } from "lucide-react";
import IndicatorHelp from "@/shared/help/IndicatorHelp";
import type { RefObject } from "react";
import type { UCHistory, UCOverview } from "./contract";
import { ErrorMessage, HistoryPanel } from "./UC360History";
import UC360OverviewTable from "./UC360OverviewTable";
import UC360Series from "./UC360Series";
import UC360Interpretation from "./UC360Interpretation";
import { UC360SupportMetrics } from "./UC360Metrics";
import UC360PeriodForm from "./UC360PeriodForm";
import { currentMeterMessage } from "./uc360-format";
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
    series: {
      data:
        | {
            items: Array<{
              competencia: string;
              measured_energy_kwh: number | null;
            }>;
          }
        | undefined;
      pending: boolean;
      error: Error | null;
    };
    previousSeries?: {
      data?: {
        items: Array<{
          competencia: string;
          measured_energy_kwh: number | null;
        }>;
      };
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
  disclosureRef: RefObject<HTMLDivElement | null>;
  actions: {
    onOverviewRetry: () => void;
    onHistoryRetry: () => void;
    onSeriesRetry: () => void;
    onNewSearch: () => void;
    onHistoryOpen: (open: boolean) => void;
    onSelectHistory: (section: UCHistorySection) => void;
    onHistorySection: (section: UCHistorySection) => void;
    onHistoryPage: (page: number) => void;
    onHistoryPageSize?: (size: number) => void;
    onPeriodApply: (start: string, end: string) => void;
  };
};

function ConsumptionAnswer({
  series,
  previous,
}: {
  series: Props["unit"]["series"];
  previous: Props["unit"]["previousSeries"];
}) {
  const latest = [...(series.data?.items ?? [])].sort((a, b) =>
    b.competencia.localeCompare(a.competencia),
  )[0];
  const priorMonth = latest
    ? `${String(Number(latest.competencia.slice(0, 4)) - 1).padStart(4, "0")}${latest.competencia.slice(4)}`
    : "";
  const prior = previous?.data?.items.find(
    (item) => item.competencia === priorMonth,
  );
  const currentValue = latest?.measured_energy_kwh;
  const priorValue = prior?.measured_energy_kwh;
  const available =
    !series.pending &&
    !series.error &&
    !previous?.pending &&
    !previous?.error &&
    currentValue != null &&
    priorValue != null;
  const format = new Intl.NumberFormat("pt-BR", { maximumFractionDigits: 2 });
  const delta = available ? currentValue - priorValue : null;
  const tone =
    delta === null || delta === 0
      ? "text-content"
      : delta > 0
        ? "text-success"
        : "text-danger";
  return (
    <section
      aria-label="Comparação com o ano anterior"
      className="rounded-xl border border-control bg-surface p-4 sm:p-5"
    >
      <h2 className="font-heading text-lg font-semibold text-content">
        Consumo em comparação ao ano anterior
      </h2>
      {available && delta !== null ? (
        <div className="mt-3 flex flex-wrap items-start gap-x-8 gap-y-3">
          <div>
            <p className={`font-heading text-xl font-semibold ${tone}`}>
              {delta > 0
                ? "↑ Consumo aumentou"
                : delta < 0
                  ? "↓ Consumo diminuiu"
                  : "Consumo permaneceu igual"}
            </p>
            <p className="mt-1 text-sm text-muted">
              {delta === 0
                ? "Sem diferença"
                : `${format.format(Math.abs(delta))} kWh ${delta > 0 ? "a mais" : "a menos"}`}{" "}
              em relação ao mesmo mês do ano anterior
            </p>
          </div>
          <dl className="grid grid-cols-2 gap-x-6 gap-y-2 text-sm lg:mt-7">
            <div>
              <dt className="text-muted">
                {latest.competencia.slice(5)}/{latest.competencia.slice(0, 4)}
              </dt>
              <dd className="mt-1 font-semibold text-content">
                {format.format(currentValue)} kWh
              </dd>
            </div>
            <div>
              <dt className="text-muted">Mesmo mês do ano anterior</dt>
              <dd className="mt-1 font-semibold text-content">
                {format.format(priorValue)} kWh
              </dd>
            </div>
          </dl>
        </div>
      ) : (
        <p className="mt-2 text-sm text-muted">
          {series.pending || previous?.pending
            ? "Carregando comparação com o ano anterior…"
            : "Não há dados suficientes para comparar o consumo com o mesmo mês do ano anterior."}
        </p>
      )}
      <p className="mt-3 text-xs text-muted">
        O consumo medido, por si só, não explica a variação do valor da fatura.
      </p>
    </section>
  );
}

export default function UC360Detail({ unit, disclosureRef, actions }: Props) {
  const selected = unit.overview.data?.data;
  const metadata = unit.overview.data?.metadata;

  return (
    <>
      <header className="grid min-w-0 gap-2">
        <h1 className="font-heading text-[26px] leading-[34px] font-semibold [overflow-wrap:anywhere] text-content lg:text-[32px] lg:leading-10">
          {selected?.profile.uc_id ?? unit.id}
        </h1>
        {selected ? (
          <div>
            {selected.profile.customer_name?.trim() && (
              <p className="font-heading text-xl font-semibold text-content [overflow-wrap:anywhere]">
                {selected.profile.customer_name.trim()}
              </p>
            )}
            <p className="text-sm text-muted">
              {selected.profile.municipio} / {selected.profile.bairro} ·{" "}
              {selected.profile.classe}
            </p>
          </div>
        ) : (
          <p className="text-sm text-muted">UC {unit.id}</p>
        )}
        {metadata?.source.is_demo && (
          <p className="mt-4 text-xs text-muted">
            Demonstração · dados sintéticos
          </p>
        )}
        <div className="flex flex-wrap items-center justify-between gap-x-4">
          {selected &&
            metadata?.source.kind === "gold_csv" &&
            (selected.profile.customer_identification_status ??
              "unavailable") !== "available" && (
              <p className="text-sm text-muted">
                {selected.profile.customer_identification_status === "absent"
                  ? "Titular sem nome informado na origem."
                  : selected.profile.customer_identification_status ===
                      "conflict"
                    ? "A origem aponta conflito na identificação do titular."
                    : "Cadastro restrito indisponível para esta UC."}
              </p>
            )}
          <div className="ml-auto">
            <IndicatorHelp screen="uc360" />
          </div>
        </div>
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
              <ConsumptionAnswer
                series={unit.series}
                previous={unit.previousSeries}
              />
              <section className="rounded-xl bg-surface p-4 sm:p-5">
                <h2 className="font-heading text-lg font-semibold">
                  Resumo por competência
                </h2>
                <UC360OverviewTable comparison={selected.comparison} />
              </section>
              <div
                ref={disclosureRef}
                className="min-w-0 rounded-xl bg-surface"
              >
                <HistoryPanel
                  section={unit.filters.section || "consumption"}
                  history={unit.history.data}
                  pending={unit.history.pending}
                  error={unit.history.error}
                  onRetry={actions.onHistoryRetry}
                  onSelectSection={actions.onHistorySection}
                  onPageChange={actions.onHistoryPage}
                  onPageSizeChange={actions.onHistoryPageSize}
                />
                <div className="grid gap-3 px-4 pb-4 sm:px-5 sm:pb-5">
                  {unit.filters.section === "meters" && (
                    <p className="text-sm text-content">
                      {currentMeterMessage(
                        selected.current_meter.item,
                        selected.current_meter.status,
                      )}
                    </p>
                  )}
                  {unit.filters.section === "distributed_generation" && (
                    <UC360SupportMetrics data={selected} />
                  )}
                </div>
              </div>
              <UC360Series
                data={unit.series.data}
                previous={unit.previousSeries}
                pending={unit.series.pending}
                error={unit.series.error}
                onRetry={actions.onSeriesRetry}
              />
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
