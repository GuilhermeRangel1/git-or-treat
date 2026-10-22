import { useState, type FormEvent } from "react";
import { Search } from "lucide-react";
import { ApiError } from "@/shared/api/client";
import { useSearchParams } from "react-router-dom";
import type { UCChange, UCMeasure, UCStatus } from "./contract";
import { ErrorMessage, EvidenceDialog, HistoryPanel } from "./UC360History";
import { humanizeLimitation, statusLabel } from "./uc360-format";
import {
  applyUCPeriod,
  applyUCSearch,
  parseUC360SearchParams,
  selectUC,
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
function hasComparablePair(initial: UCMeasure, final: UCMeasure) {
  return initial.value !== null && final.value !== null;
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
  return (
    <article className="grid min-h-40 content-center gap-2 rounded-xl bg-surface px-4 py-5 text-center">
      <h3 className="text-sm text-muted">{title}</h3>
      <p className="font-heading text-3xl font-semibold text-content">
        {amount(current.value, unit)}
      </p>
      <p className="text-xs text-muted">
        Anterior: {amount(before.value, unit)}
      </p>
      <p className="text-sm font-medium text-content">
        {delta} · {percent}
      </p>
      <p className="text-xs text-muted">
        {period} · {statusLabel(currentStatus)}
      </p>
      {current.limitations.length > 0 && (
        <p className="text-xs text-muted">
          {current.limitations.map(humanizeLimitation).join(" ")}
        </p>
      )}
    </article>
  );
}
export default function UC360Page() {
  const [params, setParams] = useSearchParams();
  const state = parseUC360SearchParams(params);
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
  const search = useUCSearch(
    state.q,
    state.searchPage,
    !state.invalid.length && Boolean(state.q) && !state.uc,
  );
  const overview = useUCOverview(
    state.uc,
    state.start,
    state.end,
    !state.invalid.length,
  );
  const history = useUCHistory(
    state.uc,
    state.section,
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
    setParams(applyUCSearch(params, q));
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
  const searchMessage =
    search.error instanceof ApiError && search.error.status === 422
      ? "Busca inválida. Use de 1 a 100 caracteres."
      : "Não foi possível buscar unidades.";
  return (
    <div className="mt-6 grid min-w-0 max-w-[980px] gap-4">
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
            Busque pelo número da UC informado durante o atendimento.
          </p>
        </div>
        <form className="flex flex-col gap-3 sm:flex-row" onSubmit={submit}>
          <label
            className="grid flex-1 gap-1 text-sm font-medium"
            htmlFor="uc-number"
          >
            Número da UC
            <input
              id="uc-number"
              className={inputClass}
              autoComplete="off"
              value={query}
              onChange={(event) => {
                setQueryDraft({ applied: state.q, value: event.target.value });
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
            className="inline-flex min-h-11 items-center justify-center gap-2 self-end rounded-lg bg-brand px-4 text-sm font-medium text-white hover:opacity-90 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand"
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
          <p id="uc-search-error" className="text-sm text-danger" role="alert">
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
                  onClick={() => setParams(selectUC(params, item.uc_id))}
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
          <div className="flex items-center gap-3 text-sm text-muted">
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
              disabled={state.searchPage >= search.data.pagination.total_pages}
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
              if (state.uc) clean.set("uc", state.uc);
              setParams(clean);
            }}
          >
            Limpar parâmetros inválidos
          </button>
        </div>
      )}
      {state.uc && !state.invalid.length && (
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
            <ErrorMessage
              error={overview.error}
              retry={() => void overview.refetch()}
            />
          )}
          {selected && (
            <>
              <header className="grid gap-1">
                <p className="font-mono text-xs uppercase tracking-wide text-muted">
                  V—ENERGY / ATENDIMENTO
                </p>
                <h2 className="font-heading text-2xl font-semibold text-content">
                  {selected.profile.uc_id}
                </h2>
                <p className="text-sm text-muted">
                  {selected.profile.customer_name ??
                    "Cliente sem nome registrado"}{" "}
                  · {selected.profile.municipio} / {selected.profile.bairro} ·{" "}
                  {selected.profile.classe}
                </p>
                <p className="text-xs text-muted">
                  {overview.data!.metadata.source.is_demo
                    ? "Demonstração · dados sintéticos"
                    : "Dados da fonte"}{" "}
                  · atualização {overview.data!.metadata.source.updated_at}
                </p>
              </header>
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
              {overview.isFetching && !overview.isPending && (
                <p role="status" className="text-sm text-muted">
                  Atualizando período…
                </p>
              )}
              <section
                className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4"
                aria-label="Comparação do período"
              >
                <Metric
                  title="Consumo medido"
                  current={selected.comparison.final.measured_energy_kwh}
                  before={selected.comparison.initial.measured_energy_kwh}
                  change={selected.comparison.measured_energy_kwh}
                  unit="kWh"
                  currentStatus={selected.comparison.measured_energy_kwh.status}
                  period={selected.comparison.final.competencia}
                />
                <Metric
                  title="Energia faturada"
                  current={selected.comparison.final.billed_energy_kwh}
                  before={selected.comparison.initial.billed_energy_kwh}
                  change={selected.comparison.billed_energy_kwh}
                  unit="kWh"
                  currentStatus={selected.comparison.billed_energy_kwh.status}
                  period={selected.comparison.final.competencia}
                />
                <Metric
                  title="Valor faturado"
                  current={selected.comparison.final.billed_amount}
                  before={selected.comparison.initial.billed_amount}
                  change={selected.comparison.billed_amount}
                  unit="BRL"
                  currentStatus={selected.comparison.billed_amount.status}
                  period={selected.comparison.final.competencia}
                />
                <Metric
                  title="Valor pago"
                  current={selected.comparison.final.paid_amount}
                  before={selected.comparison.initial.paid_amount}
                  change={selected.comparison.paid_amount}
                  unit="BRL"
                  currentStatus={selected.comparison.paid_amount.status}
                  period={selected.comparison.final.competencia}
                />
              </section>
              <p className="rounded-lg bg-surface p-3 text-sm text-content">
                Faturas em aberto na janela:{" "}
                {selected.open_invoices.count ?? "Sem dado"} ·{" "}
                {statusLabel(selected.open_invoices.status)}. Pagamentos
                vinculados às faturas não representam caixa por competência.
              </p>
              <HistoryPanel
                section={state.section || null}
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
              <section className="grid gap-3 rounded-xl bg-surface p-4 sm:p-5">
                <h3 className="font-heading text-lg font-semibold">
                  Contexto da unidade
                </h3>
                <p className="text-sm text-muted">
                  Fontes reunidas na mesma jornada, com ausências explícitas.
                  Medição menor e faturamento maior, quando observados, não
                  identificam por si só a causa da conta.
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
                  <li>
                    Interrupções:{" "}
                    {statusLabel(
                      selected.section_status.interruptions ?? "unavailable",
                    )}
                    .
                  </li>
                  <li>
                    Chamados:{" "}
                    {statusLabel(
                      selected.section_status.calls ?? "unavailable",
                    )}
                    .
                  </li>
                </ul>
                <div className="flex flex-wrap gap-2">
                  <EvidenceDialog
                    sectionStatus={selected.section_status}
                    meter={selected.current_meter.item}
                    limitations={[
                      ...new Set([
                        ...overview.data!.metadata.limitations,
                        ...selected.current_meter.limitations,
                        ...selected.distributed_generation.limitations,
                      ]),
                    ]}
                    onSelectHistory={(section) =>
                      setParams(selectUCHistory(params, section))
                    }
                  />
                  <button
                    type="button"
                    onClick={() => {
                      setQueryDraft({ applied: state.q, value: "" });
                      setParams(applyUCSearch(params, ""));
                    }}
                    className="min-h-11 rounded-lg border border-control px-4 text-sm text-content"
                  >
                    Nova busca
                  </button>
                </div>
              </section>
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
      {!state.uc && !state.q && (
        <p className="px-1 text-xs text-muted">
          Nenhuma UC selecionada. Os dados de atendimento serão exibidos após
          selecionar uma unidade nos resultados.
        </p>
      )}
    </div>
  );
}
