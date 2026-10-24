import type { DetailEnvelope, Metadata } from "./contract";
import { energy } from "./format";

export default function SuspicionDetail({
  data,
  metadata,
}: {
  data: DetailEnvelope["data"];
  metadata: Metadata;
}) {
  const periodLabel = (value: string) => {
    const [year, month] = value.split("-");
    const months = [
      "jan",
      "fev",
      "mar",
      "abr",
      "mai",
      "jun",
      "jul",
      "ago",
      "set",
      "out",
      "nov",
      "dez",
    ];
    return `${months[Number(month) - 1] ?? month}/${year}`;
  };
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
          Janela da evidência: {periodLabel(metadata.period.start)} a{" "}
          {periodLabel(metadata.period.end)}
        </p>
        <div className="mt-4 text-sm leading-[22px]">
          <p>{data.reason}</p>
          <p>
            Energia potencialmente recuperável:{" "}
            {energy(data.potential_recoverable_energy_kwh)}. Estimativa
            demonstrativa.
          </p>
          <p>
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
            Não há irregularidade confirmada. A priorização orienta uma
            inspeção; não constitui diagnóstico de fraude.
          </p>
        </div>
      </aside>
    </article>
  );
}
