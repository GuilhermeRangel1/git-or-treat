import type { ReactNode } from "react";
import { ChevronRight } from "lucide-react";
import type { DetailEnvelope, Metadata } from "./contract";
import { energy } from "./format";
import { signedValueTone } from "@/shared/ui/signedValue";

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

const GUIDANCE =
  "Verificar cadastro, medição, histórico e eventual geração própria antes de concluir.";

function CollapsibleSection({
  title,
  children,
}: {
  title: string;
  children: ReactNode;
}) {
  return (
    <details className="group rounded-lg border border-border">
      <summary className="flex min-h-11 cursor-pointer list-none items-center gap-2 rounded-lg px-3 text-sm font-medium hover:bg-surface-hover focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand [&::-webkit-details-marker]:hidden">
        <ChevronRight
          size={16}
          aria-hidden="true"
          className="shrink-0 transition-transform group-open:rotate-90 motion-reduce:transition-none"
        />
        {title}
      </summary>
      <section
        aria-label={title}
        className="border-t border-border p-4 text-sm leading-[22px]"
      >
        {children}
      </section>
    </details>
  );
}

function RecoveryHighlight({
  value,
  notice,
  children,
}: {
  value: number | null;
  notice: string;
  children?: ReactNode;
}) {
  return (
    <section
      className="rounded-xl border border-border bg-surface p-4 sm:p-6"
      aria-labelledby="recovery-title"
    >
      <h2
        id="recovery-title"
        className="text-xs leading-[18px] font-medium text-muted"
      >
        Energia a recuperar (estimativa)
      </h2>
      <p
        className={`mt-1 font-heading font-semibold [overflow-wrap:anywhere] ${value === null ? "text-2xl text-content" : "text-4xl text-brand"}`}
      >
        {energy(value)}
      </p>
      <p className="mt-2 text-sm leading-[22px]">{notice}</p>
      {children}
    </section>
  );
}

export default function SuspicionDetail({
  data,
  metadata,
  action,
}: {
  data: DetailEnvelope["data"];
  metadata: Metadata;
  action?: ReactNode;
}) {
  if ("category" in data) {
    const evidence = data.evidence;
    const metric = (label: string, value: number | null, unit = "") => (
      <div key={label}>
        <dt className="text-xs text-muted">{label}</dt>
        <dd className={`mt-1 font-medium ${signedValueTone(value, false)}`}>
          {value === null ? "Indisponível" : `${formatGold(value)}${unit}`}
        </dd>
      </div>
    );
    return (
      <article
        className="space-y-5 lg:space-y-6"
        aria-labelledby="suspicion-title"
      >
        {action}
        <RecoveryHighlight
          value={data.potential_recoverable_energy_kwh}
          notice={
            data.potential_recoverable_energy_kwh === null
              ? (data.recovery_unavailable_reason ??
                "A Gold não publicou uma estimativa válida para esta UC.")
              : "Estimativa se a irregularidade se confirmar; não garante recuperação nesta UC."
          }
        >
          {data.potential_recoverable_energy_kwh !== null &&
          evidence.recovery_interval_lower_kwh !== null &&
          evidence.recovery_interval_upper_kwh !== null &&
          evidence.recovery_estimate_confidence_level !== null ? (
            <p className="mt-2 text-xs text-muted">
              Faixa nominal de{" "}
              {Math.round(evidence.recovery_estimate_confidence_level * 100)}%:{" "}
              {energy(evidence.recovery_interval_lower_kwh)} a{" "}
              {energy(evidence.recovery_interval_upper_kwh)}. A faixa foi
              validada temporalmente.
            </p>
          ) : null}
          {data.potential_recoverable_energy_kwh !== null &&
          evidence.recovery_estimate_window_anchor &&
          evidence.recovery_estimate_window_months &&
          evidence.recovery_estimate_minimum_window_months ? (
            <p className="mt-1 text-xs text-muted">
              Janela de aplicação: {evidence.recovery_estimate_window_months}{" "}
              meses até {periodLabel(evidence.recovery_estimate_window_anchor)}{" "}
              (mínimo: {evidence.recovery_estimate_minimum_window_months}{" "}
              meses).
            </p>
          ) : null}
        </RecoveryHighlight>
        <section
          className="rounded-xl bg-surface p-4 sm:p-6"
          aria-labelledby="suspicion-title"
        >
          <h2
            id="suspicion-title"
            className="font-heading text-lg leading-[26px] font-semibold lg:text-xl lg:leading-7"
          >
            O que consta na triagem
          </h2>
          <p className="mt-4 text-xs leading-[18px] text-muted">
            Os dados da fila são uma fotografia cadastral, sem competência
            mensal.
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
          <p className="mt-4 text-sm leading-[22px] text-muted">{GUIDANCE}</p>
          <div className="mt-5 space-y-2">
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
                <CollapsibleSection title="Referência histórica de recuperação">
                  <p className="font-medium">
                    Média histórica de recuperação por inspeção
                  </p>
                  <p className="mt-1">
                    {energy(
                      evidence.historical_recovery_mean_kwh_per_inspection,
                    )}{" "}
                    por inspeção · intervalo{" "}
                    {energy(evidence.historical_recovery_interval_lower_kwh)} a{" "}
                    {energy(evidence.historical_recovery_interval_upper_kwh)}
                  </p>
                  <p className="mt-1 text-xs text-muted">
                    Referência{" "}
                    {evidence.historical_recovery_reference ?? "não informada"};
                    método candidato, não é estimativa para esta UC.
                  </p>
                </CollapsibleSection>
              )}
            {data.investigation_potential && (
              <CollapsibleSection title="Potencial estimado para investigação">
                <p className="text-xs text-muted">
                  {periodLabel(data.investigation_potential.baseline_start)} a{" "}
                  {periodLabel(data.investigation_potential.baseline_end)}{" "}
                  comparado com{" "}
                  {periodLabel(data.investigation_potential.recent_start)} a{" "}
                  {periodLabel(data.investigation_potential.recent_end)}.
                </p>
                {data.investigation_potential.potential_kwh !== null ? (
                  <>
                    <p className="mt-2 font-semibold">
                      {energy(data.investigation_potential.potential_kwh)} nos
                      três meses analisados
                    </p>
                    <p className="mt-1">
                      Consumo medido:{" "}
                      {energy(data.investigation_potential.baseline_kwh)} →{" "}
                      {energy(data.investigation_potential.recent_kwh)}.
                    </p>
                  </>
                ) : (
                  <p className="mt-1">
                    {data.investigation_potential.unavailable_reason}
                  </p>
                )}
                <p className="mt-2 text-xs text-muted">
                  Diferença de consumo, limitada a zero quando houve aumento.
                  Não é energia recuperada, previsão validada nem prova de
                  irregularidade; um resultado zero não descarta irregularidade.
                  A cobertura das leituras não é certificada e mudanças de
                  atividade, ocupação ou medidor podem influenciar a comparação.
                </p>
                {evidence.distributed_generation_present
                  ?.trim()
                  .toLowerCase() === "sim" && (
                  <p className="mt-2 text-xs text-muted">
                    Há geração distribuída cadastrada; ela pode influenciar a
                    queda de consumo.
                  </p>
                )}
              </CollapsibleSection>
            )}
            {data.consumption_comparison && (
              <CollapsibleSection title="Comparação proposta de consumo">
                <p className="text-xs text-muted">
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
                      {data.consumption_comparison.change_percent !== null && (
                        <span
                          className={signedValueTone(
                            data.consumption_comparison.change_percent,
                          )}
                        >{` (${data.consumption_comparison.change_percent.toLocaleString("pt-BR", { maximumFractionDigits: 1, signDisplay: "exceptZero" })}%)`}</span>
                      )}
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
              </CollapsibleSection>
            )}
            <CollapsibleSection title="Variação de consumo observada">
              {data.variation ? (
                <>
                  <p className="text-xs text-muted">
                    Comparação descritiva das janelas publicadas; não é
                    estimativa de recuperação.
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
                      <dt className="text-xs text-muted">
                        Queda superior a 30%
                      </dt>
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
                <p className="text-sm text-muted">
                  A variação não está disponível nesta publicação.
                </p>
              )}
            </CollapsibleSection>
          </div>
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
      {action}
      <RecoveryHighlight
        value={data.potential_recoverable_energy_kwh}
        notice={
          metadata.source.is_demo
            ? "Estimativa demonstrativa, sem confirmação de recuperação."
            : "Estimativa não fornecida nesta consulta."
        }
      >
        {metadata.source.is_demo &&
        data.potential_recoverable_energy_kwh === null ? (
          <p className="mt-1 text-xs text-muted">
            {data.estimate_evidence.unavailable_reason ??
              "Insumos indisponíveis"}
          </p>
        ) : null}
      </RecoveryHighlight>
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
        {metadata.source.kind === "gold_csv" && (
          <p className="mt-4 text-xs text-muted">
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
                ? "Regra provisória aguardando homologação."
                : "Não é probabilidade de irregularidade."}
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

          <p className="mt-4 text-muted">{GUIDANCE}</p>

          <div className="mt-5 space-y-2">
            <CollapsibleSection title="Como a prioridade é calculada">
              <p>
                {data.priority === null
                  ? "Categoria publicada na Gold. Não há score nem pesos fornecidos nesta versão."
                  : metadata.source.is_demo
                    ? "Pontuação de priorização da fila. Soma dos pesos dos sinais presentes, limitada a 1 e arredondada a duas casas."
                    : "Pontuação de priorização da fila."}
              </p>
            </CollapsibleSection>

            <CollapsibleSection
              title={
                metadata.source.kind === "gold_csv"
                  ? "Cobertura do consumo no lote"
                  : "Janela da evidência"
              }
            >
              <p>
                {metadata.period
                  ? `${periodLabel(metadata.period.start)} a ${periodLabel(metadata.period.end)}`
                  : "Não informado"}
              </p>
            </CollapsibleSection>

            {data.consumption_comparison && (
              <CollapsibleSection title="Comparação proposta de consumo">
                <p className="text-xs text-muted">
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
                      {data.consumption_comparison.change_percent !== null && (
                        <span
                          className={signedValueTone(
                            data.consumption_comparison.change_percent,
                          )}
                        >{` (${data.consumption_comparison.change_percent.toLocaleString("pt-BR", { maximumFractionDigits: 1, signDisplay: "exceptZero" })}%)`}</span>
                      )}
                    </p>
                  )}
                {data.consumption_comparison.unavailable_reason && (
                  <p className="mt-1 text-muted">
                    {data.consumption_comparison.unavailable_reason}
                  </p>
                )}
                <p className="mt-1 text-xs text-muted">
                  Regra proposta: três meses contra os três anteriores,
                  terminando na última competência da publicação. Dados
                  observados não certificam cobertura completa. Esta comparação
                  não define a prioridade nem comprova irregularidade.
                </p>
              </CollapsibleSection>
            )}

            {data.historical_recovery ? (
              <CollapsibleSection title="Média histórica de recuperação por inspeção">
                <p className="text-lg font-semibold">
                  {energy(data.historical_recovery.mean_kwh_per_inspection)} por
                  inspeção
                </p>
                <p className="mt-1 text-xs text-muted">
                  Intervalo histórico:{" "}
                  {energy(data.historical_recovery.lower_kwh_per_inspection)} a{" "}
                  {energy(data.historical_recovery.upper_kwh_per_inspection)}{" "}
                  por inspeção. Referência:{" "}
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
              </CollapsibleSection>
            ) : null}
          </div>
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
