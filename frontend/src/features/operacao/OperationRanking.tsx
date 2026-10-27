import { Link } from "react-router-dom";
import type { OperationPoint, OperationRankingEnvelope } from "./contract";
import type { OperationMetric } from "./operations-state";
import { changeOperationMetric, openOperationDetail } from "./operations-state";
import { formatNumber } from "./operation-format";
import Button from "@/shared/ui/Button";

function displayMetric(value: number | null, unit: string) {
  return value === null ? "Indisponível" : `${formatNumber(value)} ${unit}`;
}

function coverage(point: OperationPoint) {
  if (point.denominator_uc_count === null) return "Sem denominador";
  if (point.status === "unavailable") return "Cobertura indisponível";
  if (point.status === "partial") return "Cobertura parcial";
  if (point.status === "empty") return "Sem dados";
  return point.coverage_ratio === null
    ? "Cobertura indisponível"
    : `${formatNumber(point.coverage_ratio * 100, 1)}%`;
}

function detailHref(search: string, feederId: string) {
  const next = openOperationDetail(new URLSearchParams(search), feederId);
  return `?${next.toString()}`;
}

export default function OperationRanking({
  data,
  metric,
  search,
  isLoading,
  isFetching,
  isError,
  onRetry,
  onMetricChange,
}: {
  data?: OperationRankingEnvelope;
  metric: OperationMetric;
  search: string;
  isLoading: boolean;
  isFetching: boolean;
  isError: boolean;
  onRetry: () => void;
  onMetricChange: (next: URLSearchParams) => void;
}) {
  const items = data?.data.items ?? [];
  const excluded = data?.data.excluded ?? [];
  const mobileItems: Array<OperationPoint & { rank: number | null }> = [
    ...items.map((item) => ({ ...item, rank: item.rank })),
    ...excluded.map((item) => ({ ...item, rank: null })),
  ];
  return (
    <section aria-labelledby="ranking-title" className="grid min-w-0 gap-4">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h2 id="ranking-title" className="font-heading text-xl font-semibold">
            Alimentadores
          </h2>
          <p className="mt-1 text-xs text-muted">
            Indicadores no período filtrado · valores da API
          </p>
        </div>
        <div
          className="flex max-w-full flex-wrap gap-2"
          role="group"
          aria-label="Ordenar ranking"
        >
          <Button
            className="max-w-full whitespace-normal"
            variant={metric === "dec" ? "accent" : "outline"}
            aria-pressed={metric === "dec"}
            onClick={() =>
              onMetricChange(
                changeOperationMetric(new URLSearchParams(search), "dec"),
              )
            }
          >
            Ordenar por DEC
          </Button>
          <Button
            className="max-w-full whitespace-normal"
            variant={metric === "fec" ? "accent" : "outline"}
            aria-pressed={metric === "fec"}
            onClick={() =>
              onMetricChange(
                changeOperationMetric(new URLSearchParams(search), "fec"),
              )
            }
          >
            Ordenar por FEC
          </Button>
        </div>
      </div>
      {isFetching && data ? (
        <p role="status" className="text-xs text-muted">
          Atualizando ranking; exibindo a última consulta válida.
        </p>
      ) : null}
      {isLoading ? (
        <div
          role="status"
          className="rounded-xl bg-surface p-6 text-sm text-muted"
        >
          Carregando ranking de alimentadores…
        </div>
      ) : isError && !data ? (
        <div
          role="alert"
          className="grid gap-3 rounded-xl border border-danger/30 bg-surface p-5 text-sm"
        >
          <strong>Não foi possível carregar o ranking.</strong>
          <span className="text-muted">
            A consulta falhou. O consolidado pode continuar disponível.
          </span>
          <Button className="w-fit" variant="outline" onClick={onRetry}>
            Tentar novamente o ranking
          </Button>
        </div>
      ) : data && items.length === 0 && excluded.length === 0 ? (
        <div
          role="status"
          className="rounded-xl border border-dashed border-border bg-surface p-6 text-center text-sm text-muted"
        >
          {data.metadata.status === "unavailable"
            ? "Ranking indisponível: não há alimentadores com base e cobertura completas neste recorte."
            : "Nenhum alimentador encontrado no ranking para este recorte."}
        </div>
      ) : data ? (
        <>
          <div className="hidden max-w-full min-w-0 overflow-x-auto rounded-xl bg-surface lg:block">
            <table
              aria-label="Ranking de alimentadores"
              className="w-full min-w-[780px] border-collapse text-left text-sm"
            >
              <thead className="text-xs text-muted">
                <tr>
                  <th scope="col" className="px-4 py-3">
                    Posição
                  </th>
                  <th scope="col" className="px-4 py-3">
                    Alimentador
                  </th>
                  <th scope="col" className="px-4 py-3">
                    Território
                  </th>
                  <th scope="col" className="px-4 py-3">
                    DEC / h por UC
                  </th>
                  <th scope="col" className="px-4 py-3">
                    FEC / interrupções por UC
                  </th>
                  <th scope="col" className="px-4 py-3">
                    Base / cobertura
                  </th>
                  <th scope="col" className="px-4 py-3">
                    Ação
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {items.map((item) => (
                  <tr key={item.feeder_id}>
                    <td className="px-4 py-4 font-mono text-xs">{item.rank}</td>
                    <th scope="row" className="px-4 py-4 font-medium">
                      {item.feeder_id}
                    </th>
                    <td className="px-4 py-4 text-muted">
                      {item.municipalities.join(", ") ||
                        "Território não informado"}
                    </td>
                    <td className="px-4 py-4">
                      {displayMetric(item.dec_hours_per_uc, "h/UC")}
                    </td>
                    <td className="max-w-[220px] break-words px-4 py-4">
                      {displayMetric(
                        item.fec_interruptions_per_uc,
                        "interrupções/UC",
                      )}
                    </td>
                    <td className="px-4 py-4">
                      <span>
                        {item.denominator_uc_count === null
                          ? "Sem denominador"
                          : `${formatNumber(item.denominator_uc_count, 0)} UCs · ${coverage(item)}`}
                      </span>
                      {item.limitations.length > 0 ? (
                        <small className="block text-xs text-muted">
                          {item.limitations.join(" ")}
                        </small>
                      ) : null}
                    </td>
                    <td className="px-4 py-4">
                      <Link
                        className="whitespace-nowrap font-medium text-content underline underline-offset-2 focus-visible:outline-2 focus-visible:outline-offset-2"
                        to={detailHref(search, item.feeder_id)}
                        aria-label={`Investigar ${item.feeder_id}`}
                      >
                        Investigar →
                      </Link>
                    </td>
                  </tr>
                ))}
                {excluded.map((item) => (
                  <tr
                    key={item.feeder_id}
                    className="bg-[var(--status-warning-bg)]/20"
                  >
                    <td className="px-4 py-4 text-muted">—</td>
                    <th scope="row" className="px-4 py-4 font-medium">
                      {item.feeder_id}
                    </th>
                    <td className="px-4 py-4 text-muted">
                      {item.municipalities.join(", ") ||
                        "Território não informado"}
                    </td>
                    <td className="px-4 py-4">
                      {displayMetric(item.dec_hours_per_uc, "h/UC")}
                    </td>
                    <td className="max-w-[220px] break-words px-4 py-4">
                      {displayMetric(
                        item.fec_interruptions_per_uc,
                        "interrupções/UC",
                      )}
                    </td>
                    <td className="px-4 py-4">
                      <span>
                        {item.denominator_uc_count === null
                          ? "Sem denominador"
                          : coverage(item)}
                      </span>
                      {item.limitations.length > 0 ? (
                        <small className="block text-xs text-muted">
                          {item.limitations.join(" ")}
                        </small>
                      ) : null}
                    </td>
                    <td className="px-4 py-4">
                      <Link
                        className="whitespace-nowrap font-medium text-content underline underline-offset-2 focus-visible:outline-2 focus-visible:outline-offset-2"
                        to={detailHref(search, item.feeder_id)}
                        aria-label={`Investigar ${item.feeder_id}`}
                      >
                        Investigar →
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="grid min-w-0 gap-3 lg:hidden">
            {mobileItems.map((item) => (
              <article
                key={item.feeder_id}
                aria-label={`Alimentador ${item.feeder_id}`}
                className="grid min-w-0 gap-3 rounded-xl bg-surface p-4"
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <p className="text-xs text-muted">
                      {item.rank ? `Posição ${item.rank}` : "Fora do ranking"}
                    </p>
                    <h3 className="break-words font-semibold">
                      {item.feeder_id}
                    </h3>
                  </div>
                  <span className="rounded-md bg-[var(--status-warning-bg)] px-2 py-1 text-xs text-[var(--status-warning-text)]">
                    {coverage(item)}
                  </span>
                </div>
                <dl className="grid grid-cols-2 gap-x-3 gap-y-2 text-sm">
                  <div>
                    <dt className="text-xs text-muted">Território</dt>
                    <dd>{item.municipalities.join(", ") || "Não informado"}</dd>
                  </div>
                  <div>
                    <dt className="text-xs text-muted">Base incluída</dt>
                    <dd>
                      {item.denominator_uc_count === null
                        ? "Indisponível"
                        : `${formatNumber(item.denominator_uc_count, 0)} UCs`}
                    </dd>
                  </div>
                  <div>
                    <dt className="text-xs text-muted">DEC</dt>
                    <dd>{displayMetric(item.dec_hours_per_uc, "h/UC")}</dd>
                  </div>
                  <div>
                    <dt className="text-xs text-muted">FEC</dt>
                    <dd>
                      {displayMetric(
                        item.fec_interruptions_per_uc,
                        "interrupções/UC",
                      )}
                    </dd>
                  </div>
                </dl>
                {item.limitations.length > 0 ? (
                  <p className="text-xs text-muted">
                    {item.limitations.join(" ")}
                  </p>
                ) : null}
                <Link
                  className="w-fit font-medium text-content underline underline-offset-2 focus-visible:outline-2 focus-visible:outline-offset-2"
                  to={detailHref(search, item.feeder_id)}
                  aria-label={`Investigar ${item.feeder_id}`}
                >
                  Investigar alimentador →
                </Link>
              </article>
            ))}
          </div>
          <p className="text-xs text-muted">{data.data.order}</p>
        </>
      ) : null}
      {isError && data ? (
        <p
          role="alert"
          className="rounded-lg border border-[var(--status-warning)]/30 bg-[var(--status-warning-bg)] p-3 text-sm"
        >
          Não foi possível atualizar o ranking. Exibindo a última consulta
          válida.
          <Button
            className="ml-2"
            size="sm"
            variant="outline"
            onClick={onRetry}
          >
            Tentar novamente o ranking
          </Button>
        </p>
      ) : null}
    </section>
  );
}
