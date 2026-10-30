import Button from "@/shared/ui/Button";
import { Link } from "react-router-dom";
import { Fragment } from "react";
import type { OperationMetric } from "./contract";
import type {
  GoldOperationDetailEnvelope,
  GoldOperationRankingEnvelope,
  GoldOperationSummaryEnvelope,
} from "./gold-contract";
import { formatMonth, formatNumber, formatPeriod } from "./operation-format";

function stateLabel(state: string) {
  return (
    (
      {
        available: "Disponível",
        partial: "Parcial",
        empty: "Sem dados",
        unavailable: "Indisponível",
      } as Record<string, string>
    )[state] ?? state
  );
}
function value(value: number | null, unit: string) {
  return value === null ? "Indisponível" : `${formatNumber(value)} ${unit}`;
}

export default function GoldOperationView({
  summary,
  ranking,
  detail,
  metric,
  search,
  onMetricChange,
  onBack,
  summaryLoading,
  summaryError,
  rankingLoading,
  rankingError,
  detailLoading,
  detailError,
  onRetrySummary,
  onRetryRanking,
  onRetryDetail,
}: {
  summary?: GoldOperationSummaryEnvelope;
  ranking?: GoldOperationRankingEnvelope;
  detail?: GoldOperationDetailEnvelope;
  metric: OperationMetric;
  search: string;
  onMetricChange: (next: URLSearchParams) => void;
  onBack: () => void;
  summaryLoading?: boolean;
  summaryError?: boolean;
  rankingLoading?: boolean;
  rankingError?: boolean;
  detailLoading?: boolean;
  detailError?: boolean;
  onRetrySummary?: () => void;
  onRetryRanking?: () => void;
  onRetryDetail?: () => void;
}) {
  const s = summary?.data.summary;
  const selected = detail?.data.summary;
  const metadata = detail?.metadata ?? summary?.metadata ?? ranking?.metadata;
  const definition =
    detail?.data.definition ??
    summary?.data.definition ??
    ranking?.data.definition;
  return (
    <div className="grid gap-5">
      {detailLoading && !detail ? (
        <p role="status">Carregando detalhe agregado do alimentador…</p>
      ) : null}
      {detailError && !detail ? (
        <div role="alert" className="grid gap-2 rounded-xl bg-surface p-4">
          <p>Não foi possível carregar o detalhe agregado.</p>
          <Button variant="outline" className="w-fit" onClick={onRetryDetail}>
            Tentar novamente
          </Button>
        </div>
      ) : null}
      {detailError && detail ? (
        <p
          role="alert"
          className="rounded-lg bg-[var(--status-warning-bg)] p-3 text-sm"
        >
          Falha ao atualizar o detalhe; a publicação já carregada continua
          visível.{" "}
          <Button variant="outline" size="sm" onClick={onRetryDetail}>
            Tentar novamente
          </Button>
        </p>
      ) : null}
      {selected && detail ? (
        <section
          className="grid gap-4 rounded-xl bg-surface p-5"
          aria-label={`Detalhe do alimentador ${selected.feeder_id}`}
        >
          <div className="flex flex-wrap items-center justify-between gap-3">
            <h2 className="font-heading text-xl font-semibold">
              {selected.feeder_id} ·{" "}
              {selected.municipality || "Município não informado"}
            </h2>
            <Button variant="ghost" onClick={onBack}>
              ← Voltar ao ranking
            </Button>
          </div>
          <p className="text-sm text-muted">
            Janela solicitada: {formatPeriod(selected.period)} · cadastro atual
            sem vigência histórica comprovada.
          </p>
          <p className="text-xs text-muted">
            Competências observadas:{" "}
            {selected.observed_competencies.join(", ") || "nenhuma"}.
            Competências sem linha:{" "}
            {selected.missing_competencies.join(", ") ||
              "nenhuma na janela solicitada"}
            .
          </p>
          <div className="grid gap-3 sm:grid-cols-2">
            <article className="rounded-lg border border-border p-4">
              <h3>DEC · {stateLabel(selected.dec_status)}</h3>
              <p className="mt-2 text-xl font-semibold">
                {value(selected.dec_hours_per_uc, "h/UC")}
              </p>
              <p className="text-sm text-muted">
                Numerador {value(selected.duration_hours_sum, "h")} · base{" "}
                {value(selected.denominator_uc_count, "UCs")}
              </p>
            </article>
            <article className="rounded-lg border border-border p-4">
              <h3>FEC · {stateLabel(selected.fec_status)}</h3>
              <p className="mt-2 text-xl font-semibold">
                {value(selected.fec_interruptions_per_uc, "interrupções/UC")}
              </p>
              <p className="text-sm text-muted">
                Numerador {value(selected.interruption_count, "registros")} ·
                base {value(selected.denominator_uc_count, "UCs")}
              </p>
            </article>
          </div>
          <p className="rounded-lg bg-[var(--status-warning-bg)] p-3 text-sm">
            Ocorrências individuais indisponíveis: a Gold publica apenas
            agregados por alimentador e competência.
          </p>
          <h3 className="font-semibold">Série mensal</h3>
          <div className="overflow-x-auto">
            <table className="w-full min-w-[440px] text-left text-sm">
              <thead>
                <tr>
                  <th>Mês</th>
                  <th>DEC (h/UC)</th>
                  <th>FEC (interrupções/UC)</th>
                  <th>Base</th>
                </tr>
              </thead>
              <tbody>
                {detail.data.series.map((p) => (
                  <tr key={p.period.start} className="border-t border-border">
                    <th>{formatMonth(p.period.start)}</th>
                    <td>{value(p.dec_hours_per_uc, "")}</td>
                    <td>{value(p.fec_interruptions_per_uc, "")}</td>
                    <td>{value(p.denominator_uc_count, "UCs")}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {[
            ...selected.limitations,
            ...(detail.data.definition.completeness
              ? [detail.data.definition.completeness]
              : []),
          ].map((item) => (
            <p key={item} className="text-xs text-muted">
              {item}
            </p>
          ))}
        </section>
      ) : !detailLoading && !detailError ? (
        <>
          {summaryLoading && !s ? (
            <p role="status">Carregando consolidado Gold…</p>
          ) : null}
          {summaryError && !s ? (
            <div role="alert" className="grid gap-2 rounded-xl bg-surface p-4">
              <p>Não foi possível carregar o consolidado Gold.</p>
              <Button
                variant="outline"
                className="w-fit"
                onClick={onRetrySummary}
              >
                Tentar novamente
              </Button>
            </div>
          ) : null}
          {summaryError && s ? (
            <p
              role="alert"
              className="rounded-lg bg-[var(--status-warning-bg)] p-3 text-sm"
            >
              Falha ao atualizar o consolidado; mostrando a última resposta
              válida.{" "}
              <Button variant="outline" size="sm" onClick={onRetrySummary}>
                Tentar novamente
              </Button>
            </p>
          ) : null}
          {s ? (
            <section aria-label="Resumo de continuidade" className="grid gap-4">
              <div className="grid gap-3 sm:grid-cols-2">
                <article className="rounded-xl bg-surface p-5">
                  <h2>DEC · {stateLabel(s.dec_status)}</h2>
                  <p className="my-2 text-2xl font-semibold">
                    {value(s.dec_hours_per_uc, "h/UC")}
                  </p>
                  <p className="text-sm text-muted">
                    Numerador {value(s.duration_hours_sum, "h")} · base{" "}
                    {value(s.dec_denominator_uc_count, "UCs")}
                  </p>
                  <p className="text-xs text-muted">
                    Incluídos:{" "}
                    {s.dec_included_feeder_ids.join(", ") || "nenhum"} ·
                    excluídos:{" "}
                    {s.dec_excluded_feeder_ids.join(", ") || "nenhum"}
                  </p>
                </article>
                <article className="rounded-xl bg-surface p-5">
                  <h2>FEC · {stateLabel(s.fec_status)}</h2>
                  <p className="my-2 text-2xl font-semibold">
                    {value(s.fec_interruptions_per_uc, "interrupções/UC")}
                  </p>
                  <p className="text-sm text-muted">
                    Numerador {value(s.interruption_count, "registros")} · base{" "}
                    {value(s.fec_denominator_uc_count, "UCs")}
                  </p>
                  <p className="text-xs text-muted">
                    Incluídos:{" "}
                    {s.fec_included_feeder_ids.join(", ") || "nenhum"} ·
                    excluídos:{" "}
                    {s.fec_excluded_feeder_ids.join(", ") || "nenhum"}
                  </p>
                </article>
              </div>
              <p className="text-sm text-muted">
                Janela solicitada: {formatPeriod(s.period)}.{" "}
                {s.limitations.join(" ")}
              </p>
              <p className="rounded-lg bg-[var(--status-warning-bg)] p-3 text-sm">
                Cadastro atual sem vigência histórica comprovada. Resultados
                observados não demonstram homologação regulatória.
              </p>
            </section>
          ) : null}
          <section className="grid gap-4 rounded-xl bg-surface p-5">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <h2 className="font-heading text-xl font-semibold">
                Alimentadores ·{" "}
                {ranking?.data.metric.toUpperCase() ?? metric.toUpperCase()}
              </h2>
              <div className="flex gap-2">
                <Button
                  variant={metric === "dec" ? "accent" : "outline"}
                  onClick={() => {
                    const p = new URLSearchParams(search);
                    p.set("metric", "dec");
                    p.delete("feeder_id");
                    onMetricChange(p);
                  }}
                >
                  Ordenar por DEC
                </Button>
                <Button
                  variant={metric === "fec" ? "accent" : "outline"}
                  onClick={() => {
                    const p = new URLSearchParams(search);
                    p.set("metric", "fec");
                    p.delete("feeder_id");
                    onMetricChange(p);
                  }}
                >
                  Ordenar por FEC
                </Button>
              </div>
            </div>
            {rankingLoading && !ranking ? (
              <p role="status">Carregando ranking Gold…</p>
            ) : null}
            {rankingError && !ranking ? (
              <div role="alert" className="grid gap-2">
                <p>Não foi possível carregar o ranking Gold.</p>
                <Button
                  variant="outline"
                  className="w-fit"
                  onClick={onRetryRanking}
                >
                  Tentar novamente
                </Button>
              </div>
            ) : null}
            {rankingError && ranking ? (
              <p
                role="alert"
                className="rounded-lg bg-[var(--status-warning-bg)] p-3 text-sm"
              >
                Falha ao atualizar o ranking; mostrando a última resposta
                válida.{" "}
                <Button variant="outline" size="sm" onClick={onRetryRanking}>
                  Tentar novamente
                </Button>
              </p>
            ) : null}
            {ranking ? (
              <div className="overflow-x-auto">
                <table
                  aria-label="Ranking de alimentadores"
                  className="w-full min-w-[600px] text-left text-sm"
                >
                  <thead>
                    <tr>
                      <th>Pos.</th>
                      <th>Alimentador</th>
                      <th>Município</th>
                      <th>DEC</th>
                      <th>FEC</th>
                      <th>Base</th>
                      <th />
                    </tr>
                  </thead>
                  <tbody>
                    {[
                      ...ranking.data.items.map((p) => ({
                        ...p,
                        ranked: true,
                      })),
                      ...ranking.data.excluded.map((p) => ({
                        ...p,
                        rank: null,
                        ranked: false,
                      })),
                    ].map((p) => (
                      <Fragment key={p.feeder_id}>
                        <tr
                          key={p.feeder_id}
                          className="border-t border-border"
                        >
                          <td>{p.rank ?? "—"}</td>
                          <th>{p.feeder_id}</th>
                          <td>{p.municipality || "não informado"}</td>
                          <td>
                            {value(p.dec_hours_per_uc, "h/UC")}
                            <small className="block text-xs text-muted">
                              {stateLabel(p.dec_status)}
                            </small>
                          </td>
                          <td>
                            {value(p.fec_interruptions_per_uc, "int./UC")}
                            <small className="block text-xs text-muted">
                              {stateLabel(p.fec_status)}
                            </small>
                          </td>
                          <td>{value(p.denominator_uc_count, "UCs")}</td>
                          <td>
                            <Link
                              to={`?${(() => {
                                const params = new URLSearchParams(search);
                                params.set("feeder_id", p.feeder_id);
                                params.delete("page");
                                return params.toString();
                              })()}`}
                              className="underline"
                            >
                              Investigar
                            </Link>
                          </td>
                        </tr>
                        <tr
                          key={`${p.feeder_id}-limitations`}
                          className="border-b border-border"
                        >
                          <td
                            colSpan={7}
                            className="px-2 pb-2 text-xs text-muted"
                          >
                            {p.limitations.join(" ") ||
                              "Sem limitações adicionais informadas."}
                          </td>
                        </tr>
                      </Fragment>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : null}
          </section>
        </>
      ) : null}
      {metadata && definition ? (
        <section
          className="grid gap-2 rounded-xl border border-border bg-surface p-4 text-sm"
          aria-label="Fundamentos Gold de operação"
        >
          <h2 className="font-semibold">Fundamentos Gold</h2>
          <p>
            <strong>Publicação:</strong> lote {metadata.source.version} · schema{" "}
            {metadata.schema_version} · contrato {metadata.contract_version} ·
            fingerprint {metadata.fingerprint}
          </p>
          <p>
            <strong>Temporalidade:</strong> mensal · janela solicitada{" "}
            {metadata.period ? formatPeriod(metadata.period) : "indisponível"}.
          </p>
          <p>
            <strong>DEC ({definition.dec_unit}):</strong>{" "}
            {definition.dec_formula}
          </p>
          <p>
            <strong>FEC ({definition.fec_unit}):</strong>{" "}
            {definition.fec_formula}
          </p>
          <p>
            <strong>População:</strong> {definition.population} ·{" "}
            {definition.completeness}
          </p>
          <p>
            <strong>Eventos:</strong> {definition.event_grain}
          </p>
          <p>
            <strong>Limitações:</strong>{" "}
            {metadata.limitations.join(" ") ||
              "Nenhuma limitação adicional informada."}
          </p>
        </section>
      ) : null}
    </div>
  );
}
