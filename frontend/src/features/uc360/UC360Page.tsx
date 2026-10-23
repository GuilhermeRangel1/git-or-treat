import { useEffect, useRef, useState, type FormEvent } from "react";
import { Search } from "lucide-react";
import { ApiError } from "@/shared/api/client";
import { useNavigate, useParams, useSearchParams } from "react-router-dom";
import type { UCChange, UCMeasure, UCStatus } from "./contract";
import { ErrorMessage, EvidenceDialog, HistoryPanel } from "./UC360History";
import UC360OverviewTable from "./UC360OverviewTable";
import { humanizeLimitation, statusLabel } from "./uc360-format";
import {
  applyUCPeriod,
  applyUCSearch,
  parseUC360SearchParams,
  selectUCHistory,
} from "./uc360-state";
import { useUCOverview, useUCSearch, useUCHistory } from "./useUC360";

const inputClass =
  "min-h-11 rounded-lg border border-control bg-canvas px-3 text-content focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand";
const money = new Intl.NumberFormat("pt-BR", {
  style: "currency",
  currency: "BRL",
});
const decimal = new Intl.NumberFormat("pt-BR", { maximumFractionDigits: 2 });
function amount(value: number | null, unit: "BRL" | "kWh") {
  return value === null
    ? "Sem dado"
    : unit === "BRL"
      ? money.format(value)
      : `${decimal.format(value)} kWh`;
}
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
function hasComparablePair(initial: UCMeasure, final: UCMeasure) {
  return initial.value !== null && final.value !== null;
}
function changeTone(value: number | null) {
  if (value === null || value === 0) return "text-muted";
  return value > 0
    ? "text-[var(--status-success)]"
    : "text-[var(--accent-goiaba)]";
}
function Metric({
  title,
  current,
  before,
  change,
  unit,
  currentStatus,
  period,
}: {
  title: string;
  current: UCMeasure;
  before: UCMeasure;
  change: UCChange;
  unit: "BRL" | "kWh";
  currentStatus: UCStatus;
  period: string;
}) {
  const delta =
    change.delta === null
      ? "Variação indisponível"
      : `${change.delta > 0 ? "+" : ""}${unit === "BRL" ? money.format(change.delta) : `${decimal.format(change.delta)} kWh`}`;
  const percent =
    change.percent_change === null
      ? "Percentual indisponível"
      : `${change.percent_change > 0 ? "+" : ""}${decimal.format(change.percent_change)}%`;
  const limitations = [
    ...new Set([
      ...current.limitations,
      ...before.limitations,
      ...change.limitations,
    ]),
  ];
  return (
    <article className="grid min-w-0 min-h-40 content-center gap-2 rounded-xl bg-surface px-3 py-4 text-center sm:px-4 sm:py-5">
      <h3 className="text-sm text-muted">{title}</h3>
      <p className="break-words font-heading text-xl font-semibold text-content sm:text-2xl xl:text-3xl">
        {amount(current.value, unit)}
      </p>
      <p className="text-xs text-muted">
        Anterior: {amount(before.value, unit)}
      </p>
      <p className="break-words text-xs font-medium text-muted sm:text-sm">
        <span className={changeTone(change.delta)}>{delta}</span> ·{" "}
        <span className={changeTone(change.percent_change)}>{percent}</span>
      </p>
      <p className="text-xs text-muted">
        {period} · atual: {statusLabel(currentStatus)} · anterior:{" "}
        {statusLabel(before.status)}
      </p>
      <p className="text-xs text-muted">
        Comparação: {statusLabel(change.status)}
      </p>
      {limitations.length > 0 && (
        <p className="text-xs text-muted">
          {limitations.map(humanizeLimitation).join(" ")}
        </p>
      )}
    </article>
  );
}
function SummaryMetric({
  title,
  value,
  detail,
  status,
  limitations = [],
}: {
  title: string;
  value: string;
  detail: string;
  status: UCStatus;
  limitations?: string[];
}) {
  const valueSize = /\d/.test(value)
    ? value.length > 15
      ? "text-lg sm:text-2xl"
      : "text-[28px] leading-8 lg:text-4xl lg:leading-10"
    : "text-xl sm:text-2xl";
  return (
    <article className="grid min-w-0 min-h-36 content-center gap-2 rounded-xl bg-surface p-3 text-left md:text-center sm:min-h-48 sm:p-5">
      <h3 className="text-sm font-medium text-muted">{title}</h3>
      <p
        className={`break-words font-heading font-semibold text-content ${valueSize}`}
      >
        {value}
      </p>
      <p className="text-xs text-muted">{detail}</p>
      <p className="text-xs text-muted">{statusLabel(status)}</p>
      {limitations.length > 0 && (
        <details className="text-xs text-muted">
          <summary className="cursor-pointer">Limites da fonte</summary>
          <p className="mt-1">
            {limitations.map(humanizeLimitation).join(" ")}
          </p>
        </details>
      )}
    </article>
  );
}
export default function UC360Page() {
  const { ucId: routeUCId } = useParams<{ ucId: string }>();
  const navigate = useNavigate();
  const [params, setParams] = useSearchParams();
  const state = parseUC360SearchParams(params);
  const selectedUCId = routeUCId ?? state.uc;
  const [queryDraft, setQueryDraft] = useState({
    applied: state.q,
    value: state.q,
  });
  const periodKey = `${state.start}/${state.end}`;
  const [periodDraft, setPeriodDraft] = useState({
    applied: periodKey,
    start: state.start || "2025-01",
    end: state.end || "2025-02",
  });
  const query = queryDraft.applied === state.q ? queryDraft.value : state.q;
  const startDraft =
    periodDraft.applied === periodKey
      ? periodDraft.start
      : state.start || "2025-01";
  const endDraft =
    periodDraft.applied === periodKey
      ? periodDraft.end
      : state.end || "2025-02";
  const [searchValidation, setSearchValidation] = useState("");
  const [periodValidation, setPeriodValidation] = useState("");
  const [historyDraft, setHistoryDraft] = useState({
    applied: state.section,
    open: Boolean(state.section),
  });
  const historyOpen =
    historyDraft.applied === state.section
      ? historyDraft.open
      : Boolean(state.section);
  const historyDisclosureRef = useRef<HTMLDetailsElement>(null);
  const currentSearch = params.toString();
  const hasDuplicatedUC = state.invalid.some((message) =>
    message.includes("uc duplicado"),
  );
  function setHistoryOpen(open: boolean) {
    setHistoryDraft({ applied: state.section, open });
  }
  useEffect(() => {
    if (!routeUCId && state.uc) {
      const legacyParams = new URLSearchParams(currentSearch);
      if (!hasDuplicatedUC) legacyParams.delete("uc");
      const search = legacyParams.toString();
      navigate(
        `/uc-360/${encodeURIComponent(state.uc)}${search ? `?${search}` : ""}`,
        { replace: true },
      );
    }
  }, [currentSearch, hasDuplicatedUC, navigate, routeUCId, state.uc]);
  const search = useUCSearch(
    state.q,
    state.searchPage,
    !state.invalid.length && Boolean(state.q) && !selectedUCId,
  );
  const overview = useUCOverview(
    selectedUCId,
    state.start,
    state.end,
    !state.invalid.length,
  );
  const history = useUCHistory(
    selectedUCId,
    state.section || "consumption",
    state.start,
    state.end,
    state.historyPage,
    !state.invalid.length,
  );
  const selected = overview.data?.data;
  function submit(event: FormEvent) {
    event.preventDefault();
    const q = query.trim();
    if (!q || q.length > 100) {
      setSearchValidation("Informe um identificador de 1 a 100 caracteres.");
      return;
    }
    setSearchValidation("");
    const searchParams = applyUCSearch(params, q);
    navigate(`/uc-360?${searchParams.toString()}`);
  }
  function submitPeriod(event: FormEvent) {
    event.preventDefault();
    if (
      !/^\d{4}-(0[1-9]|1[0-2])$/.test(startDraft) ||
      !/^\d{4}-(0[1-9]|1[0-2])$/.test(endDraft) ||
      startDraft > endDraft
    ) {
      setPeriodValidation(
        "Informe competências válidas e mantenha o início antes do fim.",
      );
      return;
    }
    setPeriodValidation("");
    setParams(applyUCPeriod(params, startDraft, endDraft));
  }
  function openHistorySection(section: Parameters<typeof selectUCHistory>[1]) {
    setHistoryOpen(true);
    setParams(selectUCHistory(params, section));
    requestAnimationFrame(() => {
      const disclosure = historyDisclosureRef.current;
      if (disclosure && "scrollIntoView" in disclosure) {
        const reduceMotion =
          typeof window.matchMedia === "function" &&
          window.matchMedia("(prefers-reduced-motion: reduce)").matches;
        disclosure.scrollIntoView({
          behavior: reduceMotion ? "auto" : "smooth",
          block: "start",
        });
      }
    });
  }
  const searchMessage =
    search.error instanceof ApiError && search.error.status === 422
      ? "Busca inválida. Use de 1 a 100 caracteres."
      : "Não foi possível buscar unidades.";
  const periodControls = selected ? (
    <form
      onSubmit={submitPeriod}
      className="flex flex-wrap items-end gap-3 rounded-xl bg-surface p-4"
    >
      <label className="grid gap-1 text-xs text-muted">
        Início
        <input
          className={inputClass}
          aria-label="Competência inicial"
          type="month"
          value={startDraft}
          onChange={(event) =>
            setPeriodDraft({
              applied: periodKey,
              start: event.target.value,
              end: endDraft,
            })
          }
        />
      </label>
      <label className="grid gap-1 text-xs text-muted">
        Fim
        <input
          className={inputClass}
          aria-label="Competência final"
          type="month"
          value={endDraft}
          onChange={(event) =>
            setPeriodDraft({
              applied: periodKey,
              start: startDraft,
              end: event.target.value,
            })
          }
        />
      </label>
      <button
        className="min-h-11 rounded-lg border border-control px-4 text-sm text-content focus-visible:outline-2 focus-visible:outline-brand"
        type="submit"
      >
        Aplicar período
      </button>
      <span className="text-xs text-muted">
        Período: {selected.period.start} a {selected.period.end}
      </span>
      {periodValidation && (
        <span className="w-full text-sm text-danger" role="alert">
          {periodValidation}
        </span>
      )}
    </form>
  ) : null;
  const comparisonPanel = selected ? (
    <section
      className="grid grid-cols-2 gap-3 xl:grid-cols-4"
      aria-labelledby="uc-comparison-title"
    >
      <h2
        id="uc-comparison-title"
        className="col-span-full font-heading text-lg font-semibold text-content"
      >
        Comparação entre competências
      </h2>
      <Metric
        title="Consumo medido"
        current={selected.comparison.final.measured_energy_kwh}
        before={selected.comparison.initial.measured_energy_kwh}
        change={selected.comparison.measured_energy_kwh}
        unit="kWh"
        currentStatus={selected.comparison.final.measured_energy_kwh.status}
        period={`${selected.comparison.initial.competencia} → ${selected.comparison.final.competencia}`}
      />
      <Metric
        title="Energia faturada"
        current={selected.comparison.final.billed_energy_kwh}
        before={selected.comparison.initial.billed_energy_kwh}
        change={selected.comparison.billed_energy_kwh}
        unit="kWh"
        currentStatus={selected.comparison.final.billed_energy_kwh.status}
        period={`${selected.comparison.initial.competencia} → ${selected.comparison.final.competencia}`}
      />
      <Metric
        title="Valor faturado"
        current={selected.comparison.final.billed_amount}
        before={selected.comparison.initial.billed_amount}
        change={selected.comparison.billed_amount}
        unit="BRL"
        currentStatus={selected.comparison.final.billed_amount.status}
        period={`${selected.comparison.initial.competencia} → ${selected.comparison.final.competencia}`}
      />
      <Metric
        title="Valor pago"
        current={selected.comparison.final.paid_amount}
        before={selected.comparison.initial.paid_amount}
        change={selected.comparison.paid_amount}
        unit="BRL"
        currentStatus={selected.comparison.final.paid_amount.status}
        period={`${selected.comparison.initial.competencia} → ${selected.comparison.final.competencia}`}
      />
    </section>
  ) : null;
  return (
    <div
      className={`grid w-full min-w-0 ${selectedUCId ? "mt-0 gap-6" : "mt-6 gap-4"}`}
    >
      {!selectedUCId && (
        <section
          className="grid gap-3 rounded-xl bg-surface p-4 sm:p-5"
          aria-labelledby="uc-search-title"
        >
          <div>
            <h2
              id="uc-search-title"
              className="font-heading text-lg font-semibold"
            >
              Buscar unidade consumidora
            </h2>
            <p className="mt-1 text-sm text-muted">
              A UC identifica um ponto de consumo. Digite o número informado
              durante o atendimento.
            </p>
          </div>
          <form className="grid w-full gap-3" onSubmit={submit}>
            <label
              className="grid w-full max-w-80 gap-1 text-sm font-medium"
              htmlFor="uc-number"
            >
              Número da UC
              <input
                id="uc-number"
                className={`${inputClass} w-full`}
                autoComplete="off"
                value={query}
                onChange={(event) => {
                  setQueryDraft({
                    applied: state.q,
                    value: event.target.value,
                  });
                  setSearchValidation("");
                }}
                aria-describedby={
                  search.error
                    ? "uc-search-error"
                    : searchValidation
                      ? "uc-search-validation"
                      : undefined
                }
                aria-invalid={Boolean(search.error || searchValidation)}
              />
            </label>
            <button
              className="inline-flex min-h-11 w-full items-center justify-center gap-2 rounded-lg bg-content px-4 text-sm font-medium text-canvas hover:opacity-90 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-content sm:w-fit"
              type="submit"
            >
              <Search size={16} aria-hidden="true" />
              Buscar UC
            </button>
          </form>
          {searchValidation && (
            <p
              id="uc-search-validation"
              className="text-sm text-danger"
              role="alert"
            >
              {searchValidation}
            </p>
          )}
          {search.error && (
            <p
              id="uc-search-error"
              className="text-sm text-danger"
              role="alert"
            >
              {searchMessage}{" "}
              <button
                type="button"
                onClick={() => void search.refetch()}
                className="underline"
              >
                Tentar novamente
              </button>
            </p>
          )}
          {search.isFetching && (
            <p role="status" className="text-sm text-muted">
              Buscando unidades…
            </p>
          )}
          {search.data && !search.data.data.items.length && (
            <p className="text-sm text-muted" role="status">
              Nenhuma unidade corresponde a “{state.q}”.
            </p>
          )}
          {search.data && search.data.data.items.length > 0 && (
            <ul className="grid gap-2" aria-label="Resultados da busca">
              {search.data.data.items.map((item) => (
                <li key={item.uc_id}>
                  <button
                    type="button"
                    onClick={() => {
                      const detailParams = new URLSearchParams();
                      if (state.start && state.end) {
                        detailParams.set("start", state.start);
                        detailParams.set("end", state.end);
                      }
                      const search = detailParams.toString();
                      navigate(
                        `/uc-360/${encodeURIComponent(item.uc_id)}${search ? `?${search}` : ""}`,
                      );
                    }}
                    className="grid w-full gap-1 rounded-lg border border-control p-3 text-left hover:bg-canvas focus-visible:outline-2 focus-visible:outline-brand sm:grid-cols-[1fr_auto]"
                  >
                    <span className="font-medium text-content">
                      {item.uc_id} · {item.classe}
                    </span>
                    <span className="text-sm text-muted">
                      {item.municipio} · {item.bairro} · Alimentador{" "}
                      {item.alimentador}
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          )}
          {search.data && search.data.pagination.total_pages > 1 && (
            <div className="flex flex-wrap items-center gap-3 text-sm text-muted">
              <button
                type="button"
                disabled={state.searchPage <= 1}
                onClick={() => {
                  const next = new URLSearchParams(params);
                  next.set("search_page", String(state.searchPage - 1));
                  setParams(next);
                }}
                className="min-h-10 rounded border border-control px-3 disabled:opacity-50"
              >
                Anterior
              </button>
              <span>
                Página {search.data.pagination.page} de{" "}
                {search.data.pagination.total_pages}
              </span>
              <button
                type="button"
                disabled={
                  state.searchPage >= search.data.pagination.total_pages
                }
                onClick={() => {
                  const next = new URLSearchParams(params);
                  next.set("search_page", String(state.searchPage + 1));
                  setParams(next);
                }}
                className="min-h-10 rounded border border-control px-3 disabled:opacity-50"
              >
                Próxima
              </button>
            </div>
          )}
        </section>
      )}
      {state.invalid.length > 0 && (
        <div
          role="alert"
          className="grid gap-2 rounded-lg border border-danger p-3 text-sm text-danger"
        >
          {state.invalid.join(" ")} Os dados não foram consultados.
          <button
            type="button"
            className="w-fit underline"
            onClick={() => {
              const clean = new URLSearchParams();
              if (routeUCId)
                navigate(`/uc-360/${encodeURIComponent(routeUCId)}`);
              else if (state.uc)
                navigate(`/uc-360/${encodeURIComponent(state.uc)}`);
              else setParams(clean);
            }}
          >
            Limpar parâmetros inválidos
          </button>
        </div>
      )}
      {selectedUCId && (
        <header className="grid min-w-0 gap-2">
          <h1 className="font-heading text-[26px] leading-[34px] font-semibold text-content lg:text-[32px] lg:leading-10">
            {selected?.profile.uc_id ?? selectedUCId}
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
            <p className="text-sm text-muted">UC {selectedUCId}</p>
          )}
          {overview.data && (
            <p className="mt-4 text-xs text-muted">
              {overview.data.metadata.source.is_demo
                ? "Demonstração · dados sintéticos"
                : "Dados da fonte"}{" "}
              · atualização{" "}
              {sourceDate(overview.data.metadata.source.updated_at)}
            </p>
          )}
        </header>
      )}
      {selectedUCId && !state.invalid.length && (
        <>
          {overview.isPending && (
            <p
              role="status"
              className="rounded-lg bg-surface p-4 text-sm text-muted"
            >
              Carregando cadastro e comparação…
            </p>
          )}
          {overview.error && (
            <div className="grid justify-items-start gap-3">
              <ErrorMessage
                error={overview.error}
                retry={() => void overview.refetch()}
              />
              {!selected && (
                <button
                  type="button"
                  onClick={() => navigate("/uc-360")}
                  className="inline-flex min-h-11 items-center gap-2 rounded-lg border border-control px-4 text-sm text-content focus-visible:outline-2 focus-visible:outline-brand"
                >
                  <Search size={16} aria-hidden="true" />
                  Nova busca
                </button>
              )}
            </div>
          )}
          {selected && (
            <>
              <section
                className="grid grid-cols-2 gap-3 lg:gap-4 xl:grid-cols-4"
                aria-labelledby="uc-primary-indicators-title"
              >
                <h2 id="uc-primary-indicators-title" className="sr-only">
                  Indicadores principais da unidade
                </h2>
                <SummaryMetric
                  title="Consumo recente"
                  value={amount(
                    selected.comparison.final.measured_energy_kwh.value,
                    "kWh",
                  )}
                  detail={`${selected.comparison.final.competencia} · Anterior: ${amount(
                    selected.comparison.initial.measured_energy_kwh.value,
                    "kWh",
                  )} (${selected.comparison.initial.competencia})`}
                  status={selected.comparison.final.measured_energy_kwh.status}
                  limitations={
                    selected.comparison.final.measured_energy_kwh.limitations
                  }
                />
                <SummaryMetric
                  title="Valor faturado"
                  value={amount(
                    selected.comparison.final.billed_amount.value,
                    "BRL",
                  )}
                  detail={`${selected.comparison.final.competencia} · Anterior: ${amount(
                    selected.comparison.initial.billed_amount.value,
                    "BRL",
                  )} (${selected.comparison.initial.competencia})`}
                  status={selected.comparison.final.billed_amount.status}
                  limitations={
                    selected.comparison.final.billed_amount.limitations
                  }
                />
                <SummaryMetric
                  title="Faturas em aberto"
                  value={
                    selected.open_invoices.count?.toLocaleString("pt-BR") ??
                    "Sem dado"
                  }
                  detail={`${selected.period.start} a ${selected.period.end} · contagem, sem saldo ou atraso`}
                  status={selected.open_invoices.status}
                  limitations={selected.open_invoices.limitations}
                />
                <SummaryMetric
                  title="Geração própria"
                  value={
                    selected.distributed_generation.items.length > 0
                      ? selected.distributed_generation.items
                          .map(
                            (item) => `${decimal.format(item.capacity_kw)} kW`,
                          )
                          .join(" · ")
                      : selected.distributed_generation.status === "empty"
                        ? "Sem cadastro"
                        : "Sem dado"
                  }
                  detail="Potência cadastrada em kW; não é energia compensada."
                  status={selected.distributed_generation.status}
                  limitations={selected.distributed_generation.limitations}
                />
              </section>
              <UC360OverviewTable comparison={selected.comparison} />
              <section className="grid gap-3 rounded-xl bg-surface p-4 sm:p-5">
                <h3 className="font-heading text-lg font-semibold">
                  Contexto da unidade
                </h3>
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
                      ? ` · retirado em ${selected.current_meter.item.removed_at}`
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
                          .map(
                            (item) => `${decimal.format(item.capacity_kw)} kW`,
                          )
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
                        ...overview.data!.metadata.limitations,
                        ...selected.current_meter.limitations,
                        ...selected.distributed_generation.limitations,
                      ]),
                    ]}
                    onSelectHistory={openHistorySection}
                  />
                  <button
                    type="button"
                    onClick={() => navigate("/uc-360")}
                    className="inline-flex min-h-11 items-center gap-2 rounded-lg border border-control px-4 text-sm text-content"
                  >
                    <Search size={16} aria-hidden="true" />
                    Nova busca
                  </button>
                </div>
              </section>
              <details
                ref={historyDisclosureRef}
                open={historyOpen}
                onToggle={(event) => setHistoryOpen(event.currentTarget.open)}
                className="grid min-w-0 gap-3 rounded-xl bg-surface p-4 sm:p-5"
              >
                <summary className="cursor-pointer font-heading text-lg font-semibold">
                  Históricos por fonte
                </summary>
                <HistoryPanel
                  section={state.section || "consumption"}
                  history={history.data}
                  pending={history.isPending}
                  error={history.error}
                  historyPage={state.historyPage}
                  onRetry={() => void history.refetch()}
                  onSelectSection={(section) =>
                    setParams(selectUCHistory(params, section))
                  }
                  onPageChange={(page) => {
                    const next = new URLSearchParams(params);
                    next.set("history_page", String(page));
                    setParams(next);
                  }}
                />
              </details>
              {overview.isFetching && !overview.isPending && (
                <p role="status" className="text-sm text-muted">
                  Atualizando período…
                </p>
              )}
              {periodControls}
              {comparisonPanel}
              <section className="grid gap-3 sm:grid-cols-2">
                <article className="rounded-xl border border-control bg-surface p-4">
                  <h3 className="font-heading font-semibold">
                    Fatos observados
                  </h3>
                  <ul className="mt-2 grid gap-2 text-sm text-content">
                    <li>
                      Consumo medido:{" "}
                      {amount(
                        selected.comparison.initial.measured_energy_kwh.value,
                        "kWh",
                      )}{" "}
                      em {selected.comparison.initial.competencia} →{" "}
                      {amount(
                        selected.comparison.final.measured_energy_kwh.value,
                        "kWh",
                      )}{" "}
                      em {selected.comparison.final.competencia}.
                    </li>
                    <li>
                      {selected.comparison.initial.billed_amount.status ===
                        "empty" &&
                      selected.comparison.final.billed_amount.status === "empty"
                        ? "Sem faturas nos meses comparados."
                        : `Valor faturado: ${amount(
                            selected.comparison.initial.billed_amount.value,
                            "BRL",
                          )} → ${amount(
                            selected.comparison.final.billed_amount.value,
                            "BRL",
                          )}.`}
                    </li>
                    <li>
                      Estado da medição:{" "}
                      {statusLabel(
                        selected.comparison.measured_energy_kwh.status,
                      )}
                      . Estado do faturamento:{" "}
                      {statusLabel(selected.comparison.billed_amount.status)}.
                    </li>
                  </ul>
                </article>
                <article className="rounded-xl border border-control bg-surface p-4">
                  <h3 className="font-heading font-semibold">
                    Hipóteses e limites
                  </h3>
                  <p className="mt-2 text-sm text-muted">
                    {(() => {
                      const hasComparableValues =
                        hasComparablePair(
                          selected.comparison.initial.measured_energy_kwh,
                          selected.comparison.final.measured_energy_kwh,
                        ) ||
                        hasComparablePair(
                          selected.comparison.initial.billed_amount,
                          selected.comparison.final.billed_amount,
                        );
                      const billIncrease =
                        selected.comparison.billed_amount.status ===
                          "available" &&
                        selected.comparison.billed_amount.delta !== null &&
                        selected.comparison.billed_amount.delta > 0 &&
                        hasComparablePair(
                          selected.comparison.initial.billed_amount,
                          selected.comparison.final.billed_amount,
                        );
                      if (billIncrease)
                        return "Há valores comparáveis de consumo medido ou valor faturado, mas eles não demonstram por que a conta aumentou. A causa permanece sem evidência nesta resposta; consulte os históricos de faturas, medição, rede e chamados antes de atribuí-la.";
                      if (hasComparableValues)
                        return "Há valores comparáveis de consumo medido ou valor faturado, mas eles não permitem atribuir a causa de alterações no período. Consulte os históricos de faturas, medição, rede e chamados.";
                      return "Não há dois valores disponíveis para comparar consumo medido ou valor faturado neste período. Não é possível concluir o que mudou nem atribuir a causa da conta; consulte os históricos de faturas, medição, rede e chamados.";
                    })()}
                  </p>
                  {selected.comparison.measured_energy_kwh.limitations.length >
                    0 && (
                    <p className="mt-2 text-xs text-muted">
                      {selected.comparison.measured_energy_kwh.limitations
                        .map(humanizeLimitation)
                        .join(" ")}
                    </p>
                  )}
                </article>
              </section>
            </>
          )}
        </>
      )}
      {!selectedUCId && !state.q && (
        <p className="px-1 text-xs text-muted">
          Nenhuma UC selecionada. Os dados de atendimento serão exibidos após
          selecionar uma unidade nos resultados.
        </p>
      )}
    </div>
  );
}
