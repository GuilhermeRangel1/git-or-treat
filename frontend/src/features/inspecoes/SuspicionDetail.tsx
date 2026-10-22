import type { DetailEnvelope } from "./contract";
import { energy, formatNumber } from "./format";
import { ShieldAlert, Zap, ListChecks } from "lucide-react";
import PriorityScore from "./PriorityScore";

export default function SuspicionDetail({
  data,
}: {
  data: DetailEnvelope["data"];
}) {
  const evidence = data.estimate_evidence;
  return (
    <article className="space-y-5" aria-labelledby="suspicion-title">
      <div className="rounded-xl border border-border bg-surface p-5 lg:p-6">
        <p className="font-mono text-xs text-muted">
          DETALHE DA SUSPEITA · {data.rule_version}
        </p>
        <h2
          id="suspicion-title"
          className="mt-2 font-heading text-2xl font-semibold"
        >
          {data.uc_id}
        </h2>
        <p className="mt-1 text-sm text-muted">
          {data.municipality} · {data.neighborhood} · {data.class_name} ·{" "}
          {data.feeder_id}
        </p>
        <div className="mt-5 grid gap-5 sm:grid-cols-[1fr_180px]">
          <div>
            <p className="text-xs text-muted">O que motivou a investigação</p>
            <p className="mt-2 font-heading text-lg font-semibold">
              {data.reason}
            </p>
            <p className="mt-2 text-sm text-muted">
              Confira os sinais, os insumos e as limitações antes de encaminhar
              a inspeção.
            </p>
          </div>
          <div className="rounded-lg bg-canvas p-4">
            <p className="mb-3 text-xs text-muted">Prioridade da UC</p>
            <PriorityScore value={data.priority} />
          </div>
        </div>
      </div>
      <aside
        className="flex gap-3 rounded-xl border border-border bg-selected/50 p-4"
        aria-label="Limite da evidência"
      >
        <ShieldAlert
          size={20}
          aria-hidden="true"
          className="shrink-0 text-brand"
        />
        <div>
          <p className="text-sm font-semibold">
            Não há irregularidade confirmada.
          </p>
          <p className="mt-1 text-xs leading-5 text-muted">
            Esta pontuação orienta a investigação. GD, alterações de cadastro e
            falhas de medição precisam ser verificadas antes de concluir.
          </p>
        </div>
      </aside>
      <div className="grid items-start gap-5 lg:grid-cols-2">
        <section
          className="rounded-xl border border-border bg-surface p-5 lg:p-6"
          aria-labelledby="priority-title"
        >
          <ListChecks
            size={20}
            aria-hidden="true"
            className="mb-3 text-brand"
          />
          <h3
            id="priority-title"
            className="font-heading text-lg font-semibold"
          >
            Como a prioridade foi calculada
          </h3>
          <p className="mt-2">
            Pontuação: <strong>{formatNumber(data.priority)} / 1</strong>. Soma
            dos pesos dos sinais presentes, limitada a 1 e arredondada a duas
            casas. Não é probabilidade de irregularidade.
          </p>
          <ul className="mt-3 space-y-2">
            {data.signals.map((signal) => (
              <li
                key={signal.id}
                className="flex flex-wrap justify-between gap-2 rounded-lg bg-canvas p-3"
              >
                <span>{signal.label}</span>
                <strong>+{formatNumber(signal.weight)}</strong>
              </li>
            ))}
          </ul>
          <p className="mt-2 text-sm text-muted">
            Desempate: maior estimativa disponível, depois número da UC em ordem
            crescente. Estimativas ausentes ficam por último.
          </p>
        </section>
        <section
          className="rounded-xl border border-border bg-surface p-5 lg:p-6"
          aria-labelledby="energy-title"
        >
          <Zap size={20} aria-hidden="true" className="mb-3 text-brand" />
          <h3 id="energy-title" className="font-heading text-lg font-semibold">
            Energia potencialmente recuperável
          </h3>
          <p className="mt-2 font-heading text-2xl font-semibold text-brand">
            {energy(data.potential_recoverable_energy_kwh)}
          </p>
          <dl className="mt-5 grid gap-3 rounded-lg bg-canvas p-4 text-sm sm:grid-cols-2">
            <div>
              <dt className="text-muted">Referência mensal hipotética</dt>
              <dd className="mt-1 font-mono font-medium">
                {evidence.baseline_kwh === null
                  ? "Referência indisponível"
                  : energy(evidence.baseline_kwh)}
              </dd>
            </div>
            <div>
              <dt className="text-muted">Observação mensal sintética</dt>
              <dd>{energy(evidence.observed_kwh)}</dd>
            </div>
            <div>
              <dt className="text-muted">Horizonte de projeção</dt>
              <dd>{evidence.horizon_months} mês(es)</dd>
            </div>
          </dl>
          <p className="mt-3 text-sm">
            Regra: máximo entre zero e (referência − observação), multiplicado
            pelo horizonte em meses; arredondamento a duas casas.
          </p>
          {data.potential_recoverable_energy_kwh !== null &&
            evidence.baseline_kwh !== null &&
            evidence.observed_kwh !== null && (
              <p className="mt-2 font-mono text-sm">
                max(0; {formatNumber(evidence.baseline_kwh)} −{" "}
                {formatNumber(evidence.observed_kwh)}) ×{" "}
                {evidence.horizon_months} ={" "}
                {energy(data.potential_recoverable_energy_kwh)}
              </p>
            )}
          <p className="mt-2 text-sm text-muted">{evidence.reference}</p>
          {evidence.unavailable_reason && (
            <p className="mt-2 rounded-lg border border-border p-3 text-sm">
              {evidence.unavailable_reason}
            </p>
          )}
        </section>
      </div>
      <section
        className="rounded-xl border border-border bg-surface p-5 lg:p-6"
        aria-labelledby="limits-title"
      >
        <h3 id="limits-title" className="font-heading text-lg font-semibold">
          Limitações e próximos cuidados
        </h3>
        <ul className="mt-2 list-disc space-y-2 pl-5 text-sm text-muted">
          {data.limitations.map((text) => (
            <li key={text}>{text}</li>
          ))}
        </ul>
        <p className="mt-4 border-t border-border pt-4 text-xs leading-5 text-muted">
          Antes da inspeção: conferir cadastro, histórico de medição, mudanças
          de medidor e eventual geração própria. O registro de ordens e
          resultados de campo pertence à jornada de Ordens.
        </p>
      </section>
    </article>
  );
}
