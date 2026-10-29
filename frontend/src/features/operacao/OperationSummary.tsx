import type { OperationSummaryEnvelope } from "./contract";
import { formatNumber, formatPeriod } from "./operation-format";
import Button from "@/shared/ui/Button";

type SummaryCard = {
  label: string;
  value: string;
  accessibleValue: string;
  description: string;
};

function statusLabel(status: string) {
  if (status === "partial") return "Parcial";
  if (status === "unavailable") return "Indisponível";
  if (status === "empty") return "Sem alimentadores";
  return "Completa";
}

export default function OperationSummary({
  data,
  isLoading,
  isFetching,
  isError,
  onRetry,
}: {
  data?: OperationSummaryEnvelope;
  isLoading: boolean;
  isFetching: boolean;
  isError: boolean;
  onRetry: () => void;
}) {
  const summary = data?.data.summary;
  const cards: SummaryCard[] = summary
    ? [
        {
          label: "DEC simplificado",
          value:
            summary.dec_hours_per_uc === null
              ? "Indisponível"
              : `${formatNumber(summary.dec_hours_per_uc)} h/UC`,
          accessibleValue:
            summary.dec_hours_per_uc === null
              ? "indisponível"
              : `${formatNumber(summary.dec_hours_per_uc)} horas por unidade consumidora`,
          description: "Duração equivalente interna",
        },
        {
          label: "FEC simplificado",
          value:
            summary.fec_interruptions_per_uc === null
              ? "Indisponível"
              : `${formatNumber(summary.fec_interruptions_per_uc)} int./UC`,
          accessibleValue:
            summary.fec_interruptions_per_uc === null
              ? "indisponível"
              : `${formatNumber(summary.fec_interruptions_per_uc)} interrupções por unidade consumidora`,
          description: "Frequência equivalente interna",
        },
        {
          label: "Base incluída",
          value:
            summary.denominator_uc_count === null
              ? "Indisponível"
              : `${formatNumber(summary.denominator_uc_count, 0)} UCs`,
          accessibleValue:
            summary.denominator_uc_count === null
              ? "indisponível"
              : `${formatNumber(summary.denominator_uc_count, 0)} unidades consumidoras de base incluída`,
          description: "Denominador dos alimentadores incluídos",
        },
        {
          label: "Cobertura",
          value: statusLabel(summary.status),
          accessibleValue: statusLabel(summary.status),
          description:
            summary.excluded_feeder_ids.length > 0
              ? `${summary.excluded_feeder_ids.length} alimentador(es) excluído(s)`
              : `${summary.included_feeder_ids.length} alimentador(es) incluído(s)`,
        },
      ]
    : [];

  return (
    <section aria-label="Resumo de continuidade" className="grid gap-4">
      {isFetching && data ? (
        <p role="status" className="text-xs text-muted">
          Atualizando consolidado; exibindo a última consulta válida.
        </p>
      ) : null}
      {isError && data ? (
        <p
          role="alert"
          className="rounded-lg border border-[var(--status-warning)]/30 bg-[var(--status-warning-bg)] p-3 text-sm text-content"
        >
          Não foi possível atualizar o consolidado. Exibindo a última consulta
          válida.
          <Button
            className="ml-2"
            size="sm"
            variant="outline"
            onClick={onRetry}
          >
            Tentar novamente o consolidado
          </Button>
        </p>
      ) : null}
      {isLoading ? (
        <div
          role="status"
          aria-label="Carregando consolidado"
          className="grid grid-cols-2 gap-3 xl:grid-cols-4"
        >
          {Array.from({ length: 4 }, (_, index) => (
            <div
              key={index}
              className="h-48 animate-pulse rounded-xl bg-surface"
            />
          ))}
        </div>
      ) : isError && !data ? (
        <div
          role="alert"
          className="grid gap-3 rounded-xl border border-danger/30 bg-surface p-5 text-sm"
        >
          <strong>Não foi possível carregar o consolidado.</strong>
          <span className="text-muted">
            A API de operação está indisponível. Os dados do ranking permanecem
            disponíveis quando válidos.
          </span>
          <Button className="w-fit" variant="outline" onClick={onRetry}>
            Tentar novamente o consolidado
          </Button>
        </div>
      ) : summary ? (
        <>
          <div className="grid grid-cols-2 gap-3 xl:grid-cols-4 xl:gap-4">
            {cards.map((card) => (
              <article
                key={card.label}
                className="flex min-h-48 min-w-0 flex-col items-center justify-center gap-3 rounded-xl bg-surface p-4 text-center xl:p-6"
              >
                <h2 className="text-sm font-medium text-muted">{card.label}</h2>
                <p
                  aria-label={`${card.label}: ${card.accessibleValue}`}
                  className="break-words font-heading text-2xl font-semibold tracking-tight text-content xl:text-4xl"
                >
                  {card.value}
                </p>
                <p className="text-xs text-muted">{card.description}</p>
                <p className="text-xs text-muted">
                  {formatPeriod(summary.period)}
                </p>
              </article>
            ))}
          </div>
          {summary.status === "partial" ? (
            <div
              role="status"
              className="rounded-xl border border-[var(--status-warning)]/30 bg-[var(--status-warning-bg)] p-4 text-sm text-content"
            >
              <strong className="block text-[var(--status-warning-text)]">
                Consolidado parcial
              </strong>
              <p>
                Base incluída:{" "}
                {formatNumber(summary.denominator_uc_count ?? 0, 0)} UCs.
              </p>
              <p>
                Alimentadores excluídos:{" "}
                {summary.excluded_feeder_ids.join(", ")}.
              </p>
              <p className="mt-1 text-xs text-[var(--status-warning-text)]">
                Indicadores internos simplificados, sem comparação com limites
                regulatórios oficiais.
              </p>
            </div>
          ) : null}
          {summary.status === "empty" ? (
            <p
              role="status"
              className="rounded-xl border border-border bg-surface p-4 text-sm text-muted"
            >
              Nenhum alimentador foi encontrado na fonte para este recorte.
            </p>
          ) : null}
          {summary.status === "unavailable" ? (
            <p
              role="status"
              className="rounded-xl border border-[var(--status-warning)]/30 bg-[var(--status-warning-bg)] p-4 text-sm text-content"
            >
              Indicadores indisponíveis: não há alimentadores elegíveis com
              denominador e cobertura conhecidos. Sem comparação com limites
              regulatórios oficiais.
            </p>
          ) : null}
          {summary.status !== "partial" && summary.status !== "unavailable" ? (
            <p className="rounded-xl bg-[var(--status-warning-bg)] px-4 py-3 text-xs leading-5 text-[var(--status-warning-text)]">
              Indicadores internos simplificados. Sem comparação com limites
              regulatórios oficiais.
            </p>
          ) : null}
        </>
      ) : null}
    </section>
  );
}
