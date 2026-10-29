import type { DetailEnvelope, Metadata } from "./contract";
import { energy } from "./format";

const months = [
  "janeiro",
  "fevereiro",
  "março",
  "abril",
  "maio",
  "junho",
  "julho",
  "agosto",
  "setembro",
  "outubro",
  "novembro",
  "dezembro",
];

function periodLabel(value: string) {
  const [year, month] = value.split("-");
  return `${months[Number(month) - 1] ?? month} de ${year}`;
}

export default function SuspicionDetail({
  data,
  metadata,
}: {
  data: DetailEnvelope["data"];
  metadata: Metadata;
}) {
  const priority =
    data.priority_label ??
    data.priority?.toLocaleString("pt-BR", {
      maximumFractionDigits: 2,
    });

  return (
    <article
      className="space-y-5 lg:space-y-6"
      aria-labelledby="suspicion-title"
    >
      <section
        className="rounded-xl bg-surface p-4 sm:p-6"
        aria-labelledby="suspicion-title"
      >
        <h2
          id="suspicion-title"
          className="font-heading text-lg leading-[26px] font-semibold lg:text-xl lg:leading-7"
        >
          O que motivou a investigação
        </h2>
        <p className="mt-4 text-xs leading-[18px] text-muted">
          {metadata.source.kind === "gold_csv"
            ? "Cobertura do consumo no lote"
            : "Janela da evidência"}
          : {periodLabel(metadata.period.start)} a{" "}
          {periodLabel(metadata.period.end)}
        </p>
        {metadata.source.kind === "gold_csv" && (
          <p className="mt-1 text-xs text-muted">
            A fila não informa uma janela temporal própria para esta suspeita.
          </p>
        )}
        <div className="mt-4 text-sm leading-[22px]">
          <p className="font-medium">Motivo da suspeita</p>
          <p className="mt-1">{data.reason}</p>

          <div className="mt-4">
            <span
              role="status"
              aria-label={
                data.priority === null
                  ? `Prioridade categórica: ${priority}`
                  : `Prioridade analítica: ${priority} de 1`
              }
              className="inline-flex min-h-9 items-center rounded-full border border-[var(--status-info-text)] bg-[var(--status-info-bg)] px-3 text-sm font-semibold text-[var(--status-info-text)]"
            >
              Prioridade {priority}
              {data.priority !== null ? " / 1" : ""}
            </span>
            <p className="mt-1 text-xs leading-[18px] text-muted">
              {data.priority === null
                ? "Categoria publicada pela Gold; regra provisória aguardando homologação."
                : "Pontuação de priorização da fila; não é probabilidade de irregularidade."}
            </p>
          </div>

          <div className="mt-4">
            <p className="font-medium">Energia potencialmente recuperável</p>
            <p className="mt-1 text-lg font-semibold text-brand">
              {energy(data.potential_recoverable_energy_kwh)}
            </p>
            <p className="text-xs leading-[18px] text-muted">
              {metadata.source.is_demo
                ? "Estimativa demonstrativa, sem confirmação de recuperação."
                : "Estimativa não fornecida na Gold desta versão."}
            </p>
          </div>

          <div className="mt-4">
            <p className="font-medium">Sinais observados</p>
            {data.signals.length > 0 ? (
              <ul className="mt-1 list-disc space-y-1 pl-5">
                {data.signals.map((signal) => (
                  <li key={signal.id}>{signal.label}</li>
                ))}
              </ul>
            ) : (
              <p className="mt-1 text-muted">
                {data.indicators.join(" · ") || "Sem sinais disponíveis."}
              </p>
            )}
          </div>

          <p className="mt-4 text-muted">
            Verificar cadastro, medição, histórico e eventual geração própria
            antes de concluir.
          </p>
        </div>
      </section>
      <aside
        className="flex flex-col items-start justify-center gap-1 rounded-lg bg-[var(--status-warning-bg)] p-4 text-sm text-[var(--status-warning-text)]"
        aria-label="Limite da evidência"
      >
        <div>
          <p className="text-sm leading-5 font-medium">Limite da evidência</p>
          <p className="text-sm leading-[22px]">
            {metadata.source.is_demo
              ? "Não há irregularidade confirmada. A priorização orienta uma inspeção; não constitui diagnóstico de fraude."
              : "O histórico e a prioridade não confirmam uma nova irregularidade. A fila orienta investigação; não constitui diagnóstico de fraude."}
          </p>
        </div>
      </aside>
    </article>
  );
}
