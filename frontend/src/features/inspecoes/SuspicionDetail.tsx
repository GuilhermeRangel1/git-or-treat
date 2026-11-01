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
  if ("category" in data) {
    const evidence = data.evidence;
    const metric = (label: string, value: number | null, unit = "") => (
      <div key={label}>
        <dt className="text-xs text-muted">{label}</dt>
        <dd className="mt-1 font-medium">
          {value === null ? "Indisponível" : `${formatGold(value)}${unit}`}
        </dd>
      </div>
    );
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
            O que consta na triagem Gold
          </h2>
          <p className="mt-4 text-xs leading-[18px] text-muted">
            Publicação {metadata.source.version} · snapshot sem competência
            mensal
          </p>
          <dl className="mt-4 grid gap-4 text-sm sm:grid-cols-2">
            <div>
              <dt className="font-medium">Categoria de triagem</dt>
              <dd className="mt-1">{data.category ?? "Não classificada"}</dd>
            </div>
            <div>
              <dt className="font-medium">Motivo registrado</dt>
              <dd className="mt-1">{data.reason ?? "Não informado"}</dd>
            </div>
            <div>
              <dt className="font-medium">Município</dt>
              <dd className="mt-1">{data.municipality ?? "Indisponível"}</dd>
            </div>
            <div>
              <dt className="font-medium">Alimentador</dt>
              <dd className="mt-1">{data.feeder_id ?? "Indisponível"}</dd>
            </div>
          </dl>
          {evidence.historical_recovery_status ===
            "DISPONIVEL_REFERENCIA_HISTORICA" &&
            evidence.historical_recovery_reference !== null &&
            ["global", "0", "1"].includes(
              evidence.historical_recovery_reference,
            ) &&
            evidence.historical_recovery_mean_kwh_per_inspection !== null &&
            evidence.historical_recovery_interval_lower_kwh !== null &&
            evidence.historical_recovery_interval_upper_kwh !== null &&
            evidence.historical_recovery_interval_lower_kwh <=
              evidence.historical_recovery_interval_upper_kwh && (
              <section
                className="mt-5 rounded-lg bg-canvas p-4 text-sm"
                aria-label="Referência histórica de recuperação"
              >
                <h3 className="font-medium">
                  Média histórica de recuperação por inspeção
                </h3>
                <p className="mt-1">
                  {energy(evidence.historical_recovery_mean_kwh_per_inspection)}{" "}
                  por inspeção · intervalo{" "}
                  {energy(evidence.historical_recovery_interval_lower_kwh)} a{" "}
                  {energy(evidence.historical_recovery_interval_upper_kwh)}
                </p>
                <p className="mt-1 text-xs text-muted">
                  Referência{" "}
                  {evidence.historical_recovery_reference ?? "não informada"};
                  método candidato, não é estimativa para esta UC.
                </p>
              </section>
            )}
          <p className="mt-5 font-medium">Evidências publicadas</p>
          <dl className="mt-2 grid gap-4 rounded-lg bg-canvas p-4 text-sm sm:grid-cols-2">
            {metric("Inspeções realizadas", evidence.inspections_performed)}
            {metric(
              "Irregularidades confirmadas",
              evidence.confirmed_irregular_inspections,
            )}
            {metric(
              "Média histórica por leitura",
              evidence.historical_average_kwh_per_reading,
              " kWh/leitura",
            )}
            {metric("Contatos ao atendimento", evidence.call_center_contacts)}
            {metric("Interrupções", evidence.interruptions)}
            <div>
              <dt className="text-xs text-muted">Geração distribuída</dt>
              <dd className="mt-1 font-medium">
                {evidence.distributed_generation_present ?? "Indisponível"}
              </dd>
            </div>
            <div>
              <dt className="text-xs text-muted">Situação cadastral</dt>
              <dd className="mt-1 font-medium">
                {evidence.cadastral_status ?? "Indisponível"}
              </dd>
            </div>
          </dl>
          {data.consumption_comparison && (
            <section
              className="mt-5 rounded-lg bg-canvas p-4 text-sm"
              aria-label="Comparação proposta de consumo"
            >
              <h3 className="font-medium">Comparação proposta de consumo</h3>
              <p className="mt-1 text-xs text-muted">
                {periodLabel(data.consumption_comparison.baseline_start)} a{" "}
                {periodLabel(data.consumption_comparison.baseline_end)}{" "}
                comparado com{" "}
                {periodLabel(data.consumption_comparison.recent_start)} a{" "}
                {periodLabel(data.consumption_comparison.recent_end)}.
              </p>
              {data.consumption_comparison.baseline_kwh !== null &&
                data.consumption_comparison.recent_kwh !== null && (
                  <p className="mt-1">
                    {energy(data.consumption_comparison.baseline_kwh)} →{" "}
                    {energy(data.consumption_comparison.recent_kwh)}
                    {data.consumption_comparison.change_percent !== null
                      ? ` (${data.consumption_comparison.change_percent.toLocaleString("pt-BR", { maximumFractionDigits: 1, signDisplay: "exceptZero" })}%)`
                      : ""}
                  </p>
                )}
              {data.consumption_comparison.unavailable_reason && (
                <p className="mt-1 text-muted">
                  {data.consumption_comparison.unavailable_reason}
                </p>
              )}
              <p className="mt-1 text-xs text-muted">
                Regra proposta: três meses contra os três anteriores. Leituras
                observadas não certificam cobertura completa; a comparação não
                define prioridade nem comprova irregularidade.
              </p>
            </section>
          )}
          <section
            className="mt-5 rounded-lg border border-border p-4"
            aria-label="Variação de consumo observada"
          >
            <h3 className="font-medium">Variação de consumo observada</h3>
            {data.variation ? (
              <>
                <p className="mt-1 text-xs text-muted">
                  Comparação descritiva das janelas publicadas; não é estimativa
                  de recuperação.
                </p>
                <dl className="mt-3 grid gap-4 text-sm sm:grid-cols-2">
                  {metric(
                    `Média P1 · ${data.variation.p1_start} a ${data.variation.p1_end}`,
                    data.variation.p1_average_kwh_per_month,
                    " kWh/mês",
                  )}
                  {metric(
                    `Média P2 · ${data.variation.p2_start} a ${data.variation.p2_end}`,
                    data.variation.p2_average_kwh_per_month,
                    " kWh/mês",
                  )}
                  {metric(
                    "Meses observados em P1",
                    data.variation.p1_months_observed,
                  )}
                  {metric(
                    "Meses observados em P2",
                    data.variation.p2_months_observed,
                  )}
                  {metric(
                    "Diferença observada",
                    data.variation.variation_kwh,
                    " kWh/mês",
                  )}
                  {metric(
                    "Variação percentual observada",
                    data.variation.variation_pct,
                    "%",
                  )}
                  <div>
                    <dt className="text-xs text-muted">Queda superior a 30%</dt>
                    <dd className="mt-1 font-medium">
                      {data.variation.drop_over_30_pct === null
                        ? "Indisponível"
                        : data.variation.drop_over_30_pct
                          ? "Sim"
                          : "Não"}
                    </dd>
                  </div>
                </dl>
              </>
            ) : (
              <p className="mt-2 text-sm text-muted">
                A variação não está disponível nesta publicação.
              </p>
            )}
          </section>
          <section
            className="mt-5 rounded-lg bg-[var(--status-warning-bg)] p-4 text-sm text-[var(--status-warning-text)]"
            aria-label="Estimativa de recuperação indisponível"
          >
            <h3 className="font-medium">Energia recuperável indisponível</h3>
            <p className="mt-1">{data.recovery_unavailable_reason}</p>
            <p className="mt-1">
              Variação de consumo não é estimativa de energia recuperável.
            </p>
          </section>
        </section>
        <aside
          className="rounded-lg bg-[var(--status-info-bg)] p-4 text-sm text-[var(--status-info-text)]"
          aria-label="Limite da evidência"
        >
          A categoria de triagem não é probabilidade nem prioridade operacional
          de despacho. Uma suspeita não confirma irregularidade.
        </aside>
      </article>
    );
  }
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
          :{" "}
          {metadata.period
            ? `${periodLabel(metadata.period.start)} a ${periodLabel(metadata.period.end)}`
            : "Não informado"}
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
              className="inline-flex min-h-9 max-w-full items-center rounded-full border border-[var(--status-info-text)] bg-[var(--status-info-bg)] px-3 text-sm font-semibold [overflow-wrap:anywhere] text-[var(--status-info-text)]"
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

          {data.consumption_comparison && (
            <div className="mt-4 rounded-lg bg-canvas p-3">
              <p className="font-medium">Comparação proposta de consumo</p>
              <p className="mt-1 text-xs text-muted">
                {periodLabel(data.consumption_comparison.baseline_start)} a{" "}
                {periodLabel(data.consumption_comparison.baseline_end)}{" "}
                comparado com{" "}
                {periodLabel(data.consumption_comparison.recent_start)} a{" "}
                {periodLabel(data.consumption_comparison.recent_end)}.
              </p>
              {data.consumption_comparison.baseline_kwh !== null &&
                data.consumption_comparison.recent_kwh !== null && (
                  <p className="mt-1">
                    {energy(data.consumption_comparison.baseline_kwh)} →{" "}
                    {energy(data.consumption_comparison.recent_kwh)}
                    {data.consumption_comparison.change_percent !== null
                      ? ` (${data.consumption_comparison.change_percent.toLocaleString("pt-BR", { maximumFractionDigits: 1, signDisplay: "exceptZero" })}%)`
                      : ""}
                  </p>
                )}
              {data.consumption_comparison.unavailable_reason && (
                <p className="mt-1 text-muted">
                  {data.consumption_comparison.unavailable_reason}
                </p>
              )}
              <p className="mt-1 text-xs text-muted">
                Regra proposta: três meses contra os três anteriores, terminando
                na última competência da publicação. Dados observados não
                certificam cobertura completa. Esta comparação não define a
                prioridade nem comprova irregularidade.
              </p>
            </div>
          )}

          {data.historical_recovery ? (
            <div className="mt-4 rounded-lg bg-canvas p-3">
              <p className="font-medium">
                Média histórica de recuperação por inspeção
              </p>
              <p className="mt-1 text-lg font-semibold">
                {energy(data.historical_recovery.mean_kwh_per_inspection)} por
                inspeção
              </p>
              <p className="mt-1 text-xs text-muted">
                Intervalo histórico:{" "}
                {energy(data.historical_recovery.lower_kwh_per_inspection)} a{" "}
                {energy(data.historical_recovery.upper_kwh_per_inspection)} por
                inspeção. Referência:{" "}
                {data.historical_recovery.reference === "global"
                  ? "geral"
                  : data.historical_recovery.reference === "1"
                    ? "com histórico anterior de irregularidade"
                    : "sem histórico anterior de irregularidade"}
                .
              </p>
              <p className="mt-1 text-xs text-muted">
                Referência candidata baseada em inspeções anteriores; não é
                estimativa para esta UC nem garantia de recuperação. Método
                sujeito a homologação.
              </p>
            </div>
          ) : null}

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

function formatGold(value: number) {
  return value.toLocaleString("pt-BR", { maximumFractionDigits: 2 });
}
