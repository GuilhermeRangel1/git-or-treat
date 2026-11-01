import Button from "@/shared/ui/Button";
import { Link } from "react-router-dom";
import type { OperationMetric } from "./contract";
import type {
  GoldOperationDetailEnvelope,
  GoldOperationRankingEnvelope,
  GoldOperationSummaryEnvelope,
} from "./gold-contract";
import { formatNumber } from "./operation-format";
import OperationSeries from "./OperationSeries";
import GoldOperationFoundations from "./GoldOperationFoundations";
import GoldOccurrences from "./GoldOccurrences";

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
function base(value: number | null) {
  if (value === null) return "Indisponível";
  if (value <= 0) return `${formatNumber(value, 0)} UCs · inválido`;
  return `${formatNumber(value, 0)} UCs`;
}

export default function GoldOperationView({
  summary,
  ranking,
  detail,
  metric,
  search,
  rankingPage,
  onMetricChange,
  onRankingPage,
  onBack,
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
  rankingPage: number;
  onMetricChange: (next: URLSearchParams) => void;
  onRankingPage: (page: number) => void;
  onBack: () => void;
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
  const pageSize = 20;
  const rankingItems = ranking?.data.items ?? [];
  const pageCount = Math.max(1, Math.ceil(rankingItems.length / pageSize));
  const currentRankingPage = Math.min(rankingPage, pageCount);
  const visibleItems = rankingItems.slice(
    (currentRankingPage - 1) * pageSize,
    currentRankingPage * pageSize,
  );
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
          <div className="grid gap-3 sm:grid-cols-2">
            <article className="rounded-lg border border-border p-4">
              <h3>DEC · {stateLabel(selected.dec_status)}</h3>
              <p className="mt-2 text-xl font-semibold">
                {value(selected.dec_hours_per_uc, "h/UC")}
              </p>
              <p className="text-sm text-muted">
                Numerador {value(selected.duration_hours_sum, "h")} · base{" "}
                {base(selected.denominator_uc_count)}
              </p>
            </article>
            <article className="rounded-lg border border-border p-4">
              <h3>FEC · {stateLabel(selected.fec_status)}</h3>
              <p className="mt-2 text-xl font-semibold">
                {value(selected.fec_interruptions_per_uc, "interrupções/UC")}
              </p>
              <p className="text-sm text-muted">
                Numerador {value(selected.interruption_count, "registros")} ·
                base {base(selected.denominator_uc_count)}
              </p>
            </article>
          </div>
          <div>
            <h3 className="mb-3 font-semibold">Evolução mensal no período</h3>
            <OperationSeries
              period={selected.period}
              series={detail.data.series}
            />
          </div>
          <GoldOperationFoundations
            summary={selected}
            metadata={detail.metadata}
            definition={detail.data.definition}
          />
          <GoldOccurrences
            key={`${selected.feeder_id}-${selected.period.start}-${selected.period.end}`}
            feeder={selected.feeder_id}
            start={selected.period.start}
            end={selected.period.end}
          />
        </section>
      ) : !detailLoading && !detailError ? (
        <>
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
              {s.status === "empty" ? (
                <p
                  role="status"
                  className="rounded-xl bg-surface p-4 text-sm text-muted"
                >
                  Nenhum alimentador foi encontrado na publicação para este
                  recorte. Isso não representa indicadores iguais a zero.
                </p>
              ) : null}
              {s.status === "unavailable" ? (
                <p
                  role="status"
                  className="rounded-xl bg-surface p-4 text-sm text-muted"
                >
                  O consolidado não está disponível para este recorte. Consulte
                  os estados DEC e FEC e as limitações informadas pela fonte.
                </p>
              ) : null}
              <div className="grid gap-3 sm:grid-cols-2">
                <article className="rounded-xl bg-surface p-5">
                  <h2>DEC · {stateLabel(s.dec_status)}</h2>
                  <p className="my-2 text-2xl font-semibold">
                    {value(s.dec_hours_per_uc, "h/UC")}
                  </p>
                  <p className="text-sm text-muted">
                    Base DEC · {base(s.dec_denominator_uc_count)}
                  </p>
                  <p className="mt-1 text-xs text-muted">
                    {s.dec_included_feeder_ids.length} alimentadores incluídos ·{" "}
                    {s.dec_excluded_feeder_ids.length} excluídos
                  </p>
                  <div className="mt-2">
                    <GoldOperationFoundations
                      summary={s}
                      metadata={summary!.metadata}
                      definition={summary!.data.definition}
                      indicator="dec"
                    />
                  </div>
                </article>
                <article className="rounded-xl bg-surface p-5">
                  <h2>FEC · {stateLabel(s.fec_status)}</h2>
                  <p className="my-2 text-2xl font-semibold">
                    {value(s.fec_interruptions_per_uc, "interrupções/UC")}
                  </p>
                  <p className="text-sm text-muted">
                    Base FEC · {base(s.fec_denominator_uc_count)}
                  </p>
                  <p className="mt-1 text-xs text-muted">
                    {s.fec_included_feeder_ids.length} alimentadores incluídos ·{" "}
                    {s.fec_excluded_feeder_ids.length} excluídos
                  </p>
                  <div className="mt-2">
                    <GoldOperationFoundations
                      summary={s}
                      metadata={summary!.metadata}
                      definition={summary!.data.definition}
                      indicator="fec"
                    />
                  </div>
                </article>
              </div>
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
                    p.delete("ranking_page");
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
                    p.delete("ranking_page");
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
              ranking.data.items.length === 0 &&
              ranking.data.excluded.length === 0 ? (
                <p role="status" className="text-sm text-muted">
                  Nenhum alimentador foi retornado para este recorte.
                </p>
              ) : (
                <>
                  {ranking.data.items.length > 0 ? (
                    <>
                      <p className="text-sm text-muted">
                        {ranking.data.items.length} alimentadores com indicador
                        calculável · página {currentRankingPage} de {pageCount}
                      </p>
                      <div className="min-w-0 overflow-x-auto rounded-xl">
                        <table
                          aria-label="Ranking de alimentadores"
                          className="w-full min-w-[760px] table-fixed bg-surface text-left text-sm"
                        >
                          <colgroup>
                            <col className="w-[7%]" />
                            <col className="w-[18%]" />
                            <col className="w-[18%]" />
                            <col className="w-[16%]" />
                            <col className="w-[16%]" />
                            <col className="w-[13%]" />
                            <col className="w-[12%]" />
                          </colgroup>
                          <thead className="font-mono text-xs leading-[18px] text-muted">
                            <tr className="h-11 border-b border-border">
                              <th scope="col" className="pr-2 font-normal">
                                Pos.
                              </th>
                              <th scope="col" className="pr-2 font-normal">
                                Alimentador
                              </th>
                              <th scope="col" className="pr-2 font-normal">
                                Município
                              </th>
                              <th scope="col" className="pr-2 font-normal">
                                DEC
                              </th>
                              <th scope="col" className="pr-2 font-normal">
                                FEC
                              </th>
                              <th scope="col" className="pr-2 font-normal">
                                Base
                              </th>
                              <th scope="col" className="font-normal">
                                Detalhes
                              </th>
                            </tr>
                          </thead>
                          <tbody className="text-sm leading-[22px]">
                            {visibleItems.map((p) => (
                              <tr
                                key={p.feeder_id}
                                className="h-14 border-b border-border align-middle"
                              >
                                <td className="py-3 pr-2">{p.rank}</td>
                                <th
                                  scope="row"
                                  className="break-words py-3 pr-2 font-medium"
                                >
                                  {p.feeder_id}
                                </th>
                                <td className="break-words py-3 pr-2">
                                  {p.municipality || "não informado"}
                                </td>
                                <td className="py-3 pr-2">
                                  {value(p.dec_hours_per_uc, "h/UC")}
                                </td>
                                <td className="py-3 pr-2">
                                  {value(p.fec_interruptions_per_uc, "int./UC")}
                                </td>
                                <td className="py-3 pr-2">
                                  {base(p.denominator_uc_count)}
                                </td>
                                <td className="align-top py-1">
                                  <Link
                                    to={`?${(() => {
                                      const params = new URLSearchParams(
                                        search,
                                      );
                                      params.set("feeder_id", p.feeder_id);
                                      params.delete("page");
                                      return params.toString();
                                    })()}`}
                                    className="inline-flex min-h-11 items-center gap-1 rounded-md py-2 pl-0 pr-2 text-sm font-medium text-content underline decoration-border underline-offset-4 hover:decoration-content focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand"
                                  >
                                    Detalhes
                                  </Link>
                                </td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                      <nav
                        aria-label="Paginação do ranking"
                        className="flex flex-wrap items-center justify-between gap-3"
                      >
                        <p className="text-sm text-muted">
                          Mostrando {(currentRankingPage - 1) * pageSize + 1}–
                          {Math.min(
                            currentRankingPage * pageSize,
                            ranking.data.items.length,
                          )}{" "}
                          de {ranking.data.items.length}
                        </p>
                        <div className="flex gap-2">
                          <Button
                            variant="outline"
                            disabled={currentRankingPage <= 1}
                            onClick={() =>
                              onRankingPage(currentRankingPage - 1)
                            }
                          >
                            Anterior
                          </Button>
                          <Button
                            variant="outline"
                            disabled={currentRankingPage >= pageCount}
                            onClick={() =>
                              onRankingPage(currentRankingPage + 1)
                            }
                          >
                            Próxima
                          </Button>
                        </div>
                      </nav>
                    </>
                  ) : null}
                  {ranking.data.excluded.length > 0 ? (
                    <details className="rounded-lg border border-border p-3 text-sm">
                      <summary className="cursor-pointer font-medium">
                        Sem indicador calculável ·{" "}
                        {ranking.data.excluded.length}
                      </summary>
                      <ul className="mt-3 grid gap-2">
                        {ranking.data.excluded.map((p) => (
                          <li
                            key={p.feeder_id}
                            className="border-t border-border pt-2"
                          >
                            <strong>{p.feeder_id}</strong> ·{" "}
                            {p.municipality || "município não informado"}
                            <p className="text-xs text-muted">
                              {p.limitations.join(" ") ||
                                "A fonte não informou a causa."}
                            </p>
                          </li>
                        ))}
                      </ul>
                    </details>
                  ) : null}
                </>
              )
            ) : null}
          </section>
        </>
      ) : null}
    </div>
  );
}
