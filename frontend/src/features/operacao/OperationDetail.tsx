import type { OperationDetailEnvelope, OperationPeriod } from "./contract";
import {
  formatMonth,
  formatMonthReferences,
  formatNumber,
  formatPeriod,
  formatUpdatedAt,
} from "./operation-format";
import Button from "@/shared/ui/Button";
import OperationSeries from "./OperationSeries";

export default function OperationDetail({
  feederId,
  period,
  data,
  isLoading,
  isFetching,
  isError,
  onRetry,
  onBack,
  onPaginate,
}: {
  feederId: string;
  period: OperationPeriod;
  data?: OperationDetailEnvelope;
  isLoading: boolean;
  isFetching: boolean;
  isError: boolean;
  onRetry: () => void;
  onBack: () => void;
  onPaginate: (page: number) => void;
}) {
  const point = data?.data.summary;
  const pagination = data?.pagination;
  const territory =
    point?.municipalities.join(", ") || "Território não informado";
  const baseLabel =
    point &&
    point.denominator_uc_count !== null &&
    point.denominator_uc_count > 0 &&
    point.status !== "unavailable"
      ? "Base incluída"
      : "Denominador informado";

  return (
    <section
      aria-label={`Detalhe do alimentador ${feederId}`}
      className="grid min-w-0 gap-4 [overflow-wrap:anywhere]"
    >
      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="text-sm text-muted">
          {feederId} · {territory} · {formatPeriod(period)}
        </p>
        <Button variant="ghost" onClick={onBack}>
          ← Voltar ao ranking
        </Button>
      </div>
      {isFetching && data ? (
        <p role="status" className="text-xs text-muted">
          Atualizando detalhe; exibindo a última consulta válida.
        </p>
      ) : null}
      {isError && data ? (
        <p
          role="alert"
          className="rounded-lg border border-[var(--status-warning)]/30 bg-[var(--status-warning-bg)] p-3 text-sm"
        >
          Não foi possível atualizar o detalhe; exibindo a última consulta
          válida.
          <Button
            className="ml-2"
            size="sm"
            variant="outline"
            onClick={onRetry}
          >
            Tentar novamente o detalhe
          </Button>
        </p>
      ) : null}
      {isLoading && !data ? (
        <div
          role="status"
          className="rounded-xl bg-surface p-6 text-sm text-muted"
        >
          Carregando detalhe do alimentador…
        </div>
      ) : isError && !data ? (
        <div
          role="alert"
          className="grid gap-3 rounded-xl border border-danger/30 bg-surface p-5 text-sm"
        >
          <strong>Não foi possível carregar os dados de {feederId}.</strong>
          <span className="text-muted">
            A consulta ao detalhe falhou. O resumo consolidado do período
            continua visível no ranking.
          </span>
          <Button className="w-fit" variant="outline" onClick={onRetry}>
            Tentar novamente o detalhe
          </Button>
        </div>
      ) : data && point ? (
        <>
          {point.status === "unavailable" ? (
            <div
              role="alert"
              className="grid gap-2 rounded-xl border border-[var(--status-warning)]/30 bg-[var(--status-warning-bg)] p-4 text-sm"
            >
              <strong>DEC e FEC indisponíveis neste alimentador</strong>
              <p>{formatMonthReferences(point.text_alternative)}</p>
              {point.limitations.map((limitation) => (
                <p key={limitation}>{formatMonthReferences(limitation)}</p>
              ))}
              <p>
                Registros e ocorrências observados continuam disponíveis abaixo.
                Sem base adequada, os indicadores não são calculados.
              </p>
            </div>
          ) : null}
          {point.status === "partial" ? (
            <div
              role="status"
              className="rounded-xl border border-[var(--status-warning)]/30 bg-[var(--status-warning-bg)] p-4 text-sm"
            >
              <strong>Dados parciais neste período.</strong>{" "}
              {point.limitations.map(formatMonthReferences).join(" ")}
            </div>
          ) : null}
          {point.status === "empty" ? (
            <p
              role="status"
              className="rounded-xl border border-border bg-surface p-4 text-sm text-muted"
            >
              Nenhum registro de continuidade para {feederId} neste período.
              Isso é diferente de um indicador conhecido igual a zero.
            </p>
          ) : null}
          <div className="grid min-w-0 grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <article className="rounded-xl bg-surface p-4">
              <h2 className="text-xs text-muted">DEC simplificado</h2>
              <p className="mt-2 font-heading text-xl font-semibold">
                {point.dec_hours_per_uc === null
                  ? "Indisponível"
                  : `${formatNumber(point.dec_hours_per_uc)} h/UC`}
              </p>
            </article>
            <article className="rounded-xl bg-surface p-4">
              <h2 className="text-xs text-muted">FEC simplificado</h2>
              <p className="mt-2 font-heading text-xl font-semibold">
                {point.fec_interruptions_per_uc === null
                  ? "Indisponível"
                  : `${formatNumber(point.fec_interruptions_per_uc)} int./UC`}
              </p>
            </article>
            <article className="rounded-xl bg-surface p-4">
              <h2 className="text-xs text-muted">{baseLabel}</h2>
              <p className="mt-2 font-heading text-xl font-semibold">
                {point.denominator_uc_count === null
                  ? "Indisponível"
                  : point.denominator_uc_count <= 0
                    ? `${formatNumber(point.denominator_uc_count, 0)} UCs · inválido`
                    : point.status === "unavailable"
                      ? `${formatNumber(point.denominator_uc_count, 0)} UCs · não elegível`
                      : `${formatNumber(point.denominator_uc_count, 0)} UCs`}
              </p>
            </article>
            <article className="rounded-xl bg-surface p-4">
              <h2 className="text-xs text-muted">Ocorrências no período</h2>
              <p className="mt-2 font-heading text-xl font-semibold">
                {formatNumber(point.interruption_count, 0)}
              </p>
            </article>
          </div>
          <p className="text-xs text-muted">
            {data.metadata.source.is_demo
              ? "Demonstração · dados sintéticos"
              : `Fonte ${data.metadata.source.kind}`}{" "}
            · atualizado em {formatUpdatedAt(data.metadata.source.updated_at)}{" "}
            UTC
          </p>
          <OperationSeries period={period} series={data.data.series} />
          <section className="grid gap-3 rounded-xl bg-surface p-4">
            <div>
              <h2 className="font-heading text-lg font-semibold">
                Ocorrências registradas
              </h2>
              <p className="mt-1 text-xs text-muted">
                Registros UC–interrupção · página consultada no servidor
              </p>
            </div>
            {data.data.occurrences.length > 0 ? (
              <div className="max-w-full min-w-0 overflow-x-auto">
                <table
                  aria-label="Ocorrências de interrupção"
                  className="w-full min-w-[560px] border-collapse text-left font-sans text-sm leading-[22px]"
                >
                  <thead className="font-mono text-xs leading-[18px] text-muted [&_th]:font-normal">
                    <tr>
                      <th scope="col" className="px-3 py-2">
                        Registro
                      </th>
                      <th scope="col" className="px-3 py-2">
                        UC
                      </th>
                      <th scope="col" className="px-3 py-2">
                        Mês
                      </th>
                      <th scope="col" className="px-3 py-2">
                        Duração
                      </th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border">
                    {data.data.occurrences.map((occurrence) => (
                      <tr key={occurrence.event_id}>
                        <th scope="row" className="px-3 py-3 font-medium">
                          {occurrence.event_id}
                        </th>
                        <td className="px-3 py-3">{occurrence.uc_id}</td>
                        <td className="px-3 py-3">
                          {formatMonth(occurrence.competencia)}
                        </td>
                        <td className="px-3 py-3">
                          {formatNumber(occurrence.duration_hours)} h
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <p role="status" className="text-sm text-muted">
                Nenhuma ocorrência nesta página do recorte.
              </p>
            )}
            {pagination ? (
              <div className="flex flex-wrap items-center justify-between gap-3 text-sm">
                <p className="text-muted">
                  {pagination.total === 0
                    ? "0 registros"
                    : `Página ${pagination.page} de ${pagination.total_pages} · ${pagination.total} registros`}
                </p>
                <div className="flex max-w-full flex-wrap gap-2">
                  <Button
                    variant="outline"
                    className="max-w-full whitespace-normal"
                    disabled={pagination.page <= 1}
                    onClick={() => onPaginate(pagination.page - 1)}
                  >
                    Página anterior
                  </Button>
                  <Button
                    variant="outline"
                    className="max-w-full whitespace-normal"
                    disabled={pagination.page >= pagination.total_pages}
                    onClick={() => onPaginate(pagination.page + 1)}
                  >
                    Próxima página de ocorrências
                  </Button>
                </div>
              </div>
            ) : null}
          </section>
          <p className="rounded-xl bg-[var(--status-warning-bg)] p-4 text-sm text-[var(--status-warning-text)]">
            Indicadores internos simplificados; sem comparação com limites
            regulatórios oficiais.
          </p>
        </>
      ) : null}
    </section>
  );
}
