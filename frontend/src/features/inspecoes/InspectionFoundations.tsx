import { ListChecks, Zap } from "lucide-react";
import type { DetailEnvelope, Metadata } from "./contract";
import { energy, formatNumber } from "./format";
import ConsumptionComparison from "./ConsumptionComparison";

function monthLabel(value: string) {
  const [year, month] = value.split("-");
  const monthNames = [
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
  return `${monthNames[Number(month) - 1] ?? month} de ${year}`;
}

export default function InspectionFoundations({
  metadata,
  detail,
}: {
  metadata: Metadata;
  detail?: DetailEnvelope["data"];
}) {
  return (
    <div className="space-y-5 p-5 sm:p-6">
      <section className="space-y-3" aria-labelledby="source-title">
        <h3 id="source-title" className="font-heading text-lg font-semibold">
          Fonte e limites
        </h3>
        <p className="text-sm">
          {metadata.source.is_demo
            ? "Demonstração com dados sintéticos"
            : "Fonte analítica"}{" "}
          · {metadata.source.kind} · {metadata.source.version}
        </p>
        <p className="text-sm">
          Janela: {monthLabel(metadata.period.start)} a{" "}
          {monthLabel(metadata.period.end)} · Energia em kWh · Atualizado em{" "}
          {new Date(metadata.source.updated_at).toLocaleString("pt-BR", {
            timeZone: "UTC",
          })}{" "}
          UTC
        </p>
        <ul className="list-disc space-y-1 pl-5 text-sm text-muted">
          {metadata.limitations.map((text) => (
            <li key={text}>{text}</li>
          ))}
        </ul>
      </section>

      {detail ? (
        <>
          <section
            className="border-t border-border pt-5"
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
            <p className="mt-2 text-sm leading-5">
              Prioridade:{" "}
              <strong>
                {detail.priority_label ??
                  `${formatNumber(detail.priority ?? 0)} / 1`}
              </strong>
              .{" "}
              {metadata.source.is_demo
                ? "Soma dos pesos dos sinais presentes, limitada a 1 e arredondada a duas casas. Não é probabilidade de irregularidade."
                : "Categoria publicada na Gold. Não há score nem pesos fornecidos nesta versão."}
            </p>
            <ul className="mt-3 space-y-2">
              {detail.signals.map((signal) => (
                <li
                  key={signal.id}
                  className="flex flex-wrap justify-between gap-2 rounded-lg bg-canvas p-3 text-sm"
                >
                  <span>{signal.label}</span>
                  <strong>+{formatNumber(signal.weight)}</strong>
                </li>
              ))}
            </ul>
            <p
              className="mt-4 rounded-lg bg-canvas p-3 font-mono text-sm"
              aria-label="Composição da prioridade"
            >
              min(1;{" "}
              {detail.signals
                .map((signal) => formatNumber(signal.weight))
                .join(" + ") || "0"}
              ) ={" "}
              {detail.priority === null
                ? "score não fornecido"
                : formatNumber(detail.priority)}
            </p>
            <h4 className="mt-5 font-semibold">
              O que define a posição na fila
            </h4>
            <p className="mt-2 text-sm text-muted">
              {metadata.source.is_demo
                ? "Na ordenação padrão, as maiores pontuações aparecem primeiro no recorte filtrado. Alterar filtros ou ordenação pode mudar a posição."
                : "Ordenação categórica: Alta, Média, Revisar e Baixa. A ordem não corresponde a um score de risco."}
            </p>
            <p className="mt-2 text-sm text-muted">
              {metadata.source.is_demo
                ? "Desempate: maior estimativa disponível, depois número da UC em ordem crescente. Estimativas ausentes ficam por último."
                : "Desempate por número da UC crescente. Estimativas de recuperação não foram fornecidas."}
            </p>
          </section>

          <section
            className="border-t border-border pt-5"
            aria-labelledby="energy-title"
          >
            <Zap size={20} aria-hidden="true" className="mb-3 text-brand" />
            <h3
              id="energy-title"
              className="font-heading text-lg font-semibold"
            >
              Energia potencialmente recuperável
            </h3>
            <p className="mt-2 font-heading text-2xl font-semibold text-brand">
              {energy(detail.potential_recoverable_energy_kwh)}
            </p>
            <ConsumptionComparison evidence={detail.estimate_evidence} />
            <dl className="mt-4 grid gap-3 rounded-lg bg-canvas p-4 text-sm sm:grid-cols-2">
              <div>
                <dt className="text-muted">
                  {metadata.source.is_demo
                    ? "Referência mensal hipotética"
                    : "Referência mensal não fornecida"}
                </dt>
                <dd className="mt-1 font-mono font-medium">
                  {detail.estimate_evidence.baseline_kwh === null
                    ? "Referência indisponível"
                    : energy(detail.estimate_evidence.baseline_kwh)}
                </dd>
              </div>
              <div>
                <dt className="text-muted">
                  {metadata.source.is_demo
                    ? "Observação mensal sintética"
                    : "Observação mensal não fornecida"}
                </dt>
                <dd>{energy(detail.estimate_evidence.observed_kwh)}</dd>
              </div>
              <div>
                <dt className="text-muted">Horizonte de projeção</dt>
                <dd>{detail.estimate_evidence.horizon_months} mês(es)</dd>
              </div>
            </dl>
            <p className="mt-3 text-sm">
              Regra: máximo entre zero e (referência − observação), multiplicado
              pelo horizonte em meses; arredondamento a duas casas.
            </p>
            {detail.potential_recoverable_energy_kwh !== null &&
            detail.estimate_evidence.baseline_kwh !== null &&
            detail.estimate_evidence.observed_kwh !== null ? (
              <p className="mt-2 font-mono text-sm">
                max(0; {formatNumber(detail.estimate_evidence.baseline_kwh)} −{" "}
                {formatNumber(detail.estimate_evidence.observed_kwh)}) ×{" "}
                {detail.estimate_evidence.horizon_months} ={" "}
                {energy(detail.potential_recoverable_energy_kwh)}
              </p>
            ) : null}
            <p className="mt-2 text-sm text-muted">
              {detail.estimate_evidence.reference}
            </p>
            {detail.estimate_evidence.unavailable_reason ? (
              <p className="mt-2 rounded-lg border border-border p-3 text-sm">
                {detail.estimate_evidence.unavailable_reason}
              </p>
            ) : null}
          </section>

          <section
            className="border-t border-border pt-5"
            aria-labelledby="limitations-title"
          >
            <h3
              id="limitations-title"
              className="font-heading text-lg font-semibold"
            >
              Limitações e próximos cuidados
            </h3>
            <ul className="mt-2 list-disc space-y-2 pl-5 text-sm text-muted">
              {detail.limitations.map((text) => (
                <li key={text}>{text}</li>
              ))}
            </ul>
          </section>
        </>
      ) : (
        <section
          className="border-t border-border pt-5"
          aria-labelledby="queue-rules-title"
        >
          <h3
            id="queue-rules-title"
            className="font-heading text-lg font-semibold"
          >
            Como interpretar a fila
          </h3>
          <p className="mt-2 text-sm text-muted">
            A fila ordena suspeitas; prioridade não é probabilidade e estimativa
            indisponível não representa zero. Consulte o detalhe da UC para ver
            sinais, pesos, cálculo e insumos.
          </p>
        </section>
      )}
    </div>
  );
}
