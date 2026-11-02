import { ListChecks, Zap } from "lucide-react";
import type { DetailEnvelope, Metadata } from "./contract";
import { energy, formatNumber } from "./format";
import { signedValueTone } from "@/shared/ui/signedValue";
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

function observedMonthsLabel(count: number | null, start: string, end: string) {
  if (count === null) return "Meses observados indisponíveis";
  const [startYear, startMonth] = start.split("-").map(Number);
  const [endYear, endMonth] = end.split("-").map(Number);
  const expected = (endYear - startYear) * 12 + endMonth - startMonth + 1;
  return expected > 0
    ? `${count} de ${expected} meses observados`
    : `${count} meses observados`;
}

export default function InspectionFoundations({
  metadata,
  detail,
}: {
  metadata: Metadata;
  detail?: DetailEnvelope["data"];
}) {
  if (metadata.contract_version === "2.0.0") {
    const goldDetail = detail && "category" in detail ? detail : null;
    const goldMonthRange = (start: string, end: string) =>
      `${monthLabel(start)} a ${monthLabel(end)}`;
    return (
      <div className="space-y-5 p-5 sm:p-6">
        <section className="space-y-3" aria-labelledby="source-title">
          <h3 id="source-title" className="font-heading text-lg font-semibold">
            Dados da fila
          </h3>
          <p className="text-sm text-muted">
            Atualizados em{" "}
            {new Date(metadata.source.updated_at).toLocaleString("pt-BR", {
              dateStyle: "short",
              timeStyle: "short",
            })}
            . A fila é uma fotografia cadastral, sem mês de referência.
          </p>
        </section>
        {goldDetail ? (
          <>
            <section
              className="border-t border-border pt-5"
              aria-labelledby="triage-title"
            >
              <h3
                id="triage-title"
                className="font-heading text-lg font-semibold"
              >
                Classificação e evidências
              </h3>
              <p className="mt-2 text-sm">
                Categoria:{" "}
                <strong>{goldDetail.category ?? "não classificada"}</strong>.
                Ela orienta a triagem; não confirma irregularidade nem define
                despacho.
              </p>
              <p className="mt-2 text-sm">
                Motivo: {goldDetail.reason ?? "não informado"}
              </p>
              <dl className="mt-3 grid gap-3 rounded-lg bg-canvas p-4 text-sm sm:grid-cols-2">
                <div>
                  <dt className="text-muted">Inspeções realizadas</dt>
                  <dd>
                    {goldDetail.evidence.inspections_performed ??
                      "Indisponível"}
                  </dd>
                </div>
                <div>
                  <dt className="text-muted">Irregularidades confirmadas</dt>
                  <dd>
                    {goldDetail.evidence.confirmed_irregular_inspections ??
                      "Indisponível"}
                  </dd>
                </div>
                <div>
                  <dt className="text-muted">Média histórica por leitura</dt>
                  <dd>
                    {goldDetail.evidence.historical_average_kwh_per_reading ===
                    null
                      ? "Indisponível"
                      : `${formatNumber(goldDetail.evidence.historical_average_kwh_per_reading)} kWh/leitura`}
                  </dd>
                </div>
                <div>
                  <dt className="text-muted">Geração distribuída</dt>
                  <dd>
                    {goldDetail.evidence.distributed_generation_present ??
                      "Indisponível"}
                  </dd>
                </div>
                <div>
                  <dt className="text-muted">Situação cadastral</dt>
                  <dd>
                    {goldDetail.evidence.cadastral_status ?? "Indisponível"}
                  </dd>
                </div>
                <div>
                  <dt className="text-muted">Contatos ao atendimento</dt>
                  <dd>
                    {goldDetail.evidence.call_center_contacts ?? "Indisponível"}
                  </dd>
                </div>
                <div>
                  <dt className="text-muted">Interrupções</dt>
                  <dd>{goldDetail.evidence.interruptions ?? "Indisponível"}</dd>
                </div>
              </dl>
            </section>
            <section
              className="border-t border-border pt-5"
              aria-labelledby="variation-title"
            >
              <h3
                id="variation-title"
                className="font-heading text-lg font-semibold"
              >
                Comparação do consumo
              </h3>
              {goldDetail.variation ? (
                <dl className="mt-3 grid gap-3 rounded-lg bg-canvas p-4 text-sm sm:grid-cols-2">
                  <div>
                    <dt className="text-muted">Janela de referência</dt>
                    <dd>
                      {goldMonthRange(
                        goldDetail.variation.p1_start,
                        goldDetail.variation.p1_end,
                      )}
                    </dd>
                    <dd>
                      {observedMonthsLabel(
                        goldDetail.variation.p1_months_observed,
                        goldDetail.variation.p1_start,
                        goldDetail.variation.p1_end,
                      )}
                      {" · "}
                      {goldDetail.variation.p1_average_kwh_per_month === null
                        ? "média indisponível"
                        : `${formatNumber(goldDetail.variation.p1_average_kwh_per_month)} kWh/mês`}
                    </dd>
                  </div>
                  <div>
                    <dt className="text-muted">Janela recente</dt>
                    <dd>
                      {goldMonthRange(
                        goldDetail.variation.p2_start,
                        goldDetail.variation.p2_end,
                      )}
                    </dd>
                    <dd>
                      {observedMonthsLabel(
                        goldDetail.variation.p2_months_observed,
                        goldDetail.variation.p2_start,
                        goldDetail.variation.p2_end,
                      )}
                      {" · "}
                      {goldDetail.variation.p2_average_kwh_per_month === null
                        ? "média indisponível"
                        : `${formatNumber(goldDetail.variation.p2_average_kwh_per_month)} kWh/mês`}
                    </dd>
                  </div>
                  <div>
                    <dt className="text-muted">Diferença observada</dt>
                    <dd
                      className={signedValueTone(
                        goldDetail.variation.variation_kwh,
                        false,
                      )}
                    >
                      {goldDetail.variation.variation_kwh === null
                        ? "Indisponível"
                        : `${formatNumber(goldDetail.variation.variation_kwh)} kWh/mês`}
                    </dd>
                  </div>
                  <div>
                    <dt className="text-muted">Variação percentual</dt>
                    <dd
                      className={signedValueTone(
                        goldDetail.variation.variation_pct,
                        false,
                      )}
                    >
                      {goldDetail.variation.variation_pct === null
                        ? "Indisponível"
                        : `${formatNumber(goldDetail.variation.variation_pct)}%`}
                    </dd>
                  </div>
                  <div>
                    <dt className="text-muted">Queda acima de 30%</dt>
                    <dd>
                      {goldDetail.variation.drop_over_30_pct === null
                        ? "Indisponível"
                        : goldDetail.variation.drop_over_30_pct
                          ? "Sim"
                          : "Não"}
                    </dd>
                  </div>
                </dl>
              ) : (
                <p className="mt-2 text-sm text-muted">
                  Variação não disponível para esta UC.
                </p>
              )}
              <p className="mt-3 text-sm text-muted">
                A variação descreve o consumo observado; não estima energia
                recuperável nem confirma irregularidade.
              </p>
            </section>
          </>
        ) : (
          <p className="border-t border-border pt-5 text-sm text-muted">
            Abra uma UC da fila para consultar a classificação, as evidências e
            a comparação do consumo.
          </p>
        )}
      </div>
    );
  }
  detail = detail && "priority" in detail ? detail : undefined;
  return (
    <div className="space-y-5 p-5 sm:p-6">
      <section className="space-y-3" aria-labelledby="source-title">
        <h3 id="source-title" className="font-heading text-lg font-semibold">
          Fonte e limites
        </h3>
        <p className="text-sm [overflow-wrap:anywhere]">
          {metadata.source.is_demo
            ? "Demonstração com dados sintéticos"
            : "Fonte analítica"}{" "}
          · {metadata.source.kind} · {metadata.source.version}
        </p>
        <p className="text-sm">
          {metadata.source.kind === "gold_csv"
            ? "Cobertura do consumo no lote"
            : "Janela"}
          : {monthLabel(metadata.period.start)} a{" "}
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
                  <strong className={signedValueTone(signal.weight)}>
                    {signal.weight > 0 ? "+" : ""}
                    {formatNumber(signal.weight)}
                  </strong>
                </li>
              ))}
            </ul>
            {metadata.source.is_demo ? (
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
            ) : null}
            <h4 className="mt-5 font-semibold">
              O que define a posição na fila
            </h4>
            <p className="mt-2 text-sm text-muted">
              {metadata.source.is_demo
                ? "Na ordenação padrão, as maiores pontuações aparecem primeiro no recorte filtrado. Alterar filtros ou ordenação pode mudar a posição."
                : metadata.source.version.startsWith("gold-csv-v2:")
                  ? "A ordem segue a posição publicada: categoria, histórico de irregularidades, média de consumo e UC; casos para revisão ficam ao final."
                  : "Ordenação categórica publicada, sem score de risco."}
            </p>
            <p className="mt-2 text-sm text-muted">
              {metadata.source.is_demo
                ? "Desempate: maior estimativa disponível, depois número da UC em ordem crescente. Estimativas ausentes ficam por último."
                : metadata.source.version.startsWith("gold-csv-v2:")
                  ? "Desempate: mais irregularidades, maior média de consumo e número da UC. A média é por leitura e não indica período próprio."
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
            {metadata.source.is_demo ? (
              <ConsumptionComparison evidence={detail.estimate_evidence} />
            ) : null}
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
                <dd>
                  {detail.estimate_evidence.horizon_months === null
                    ? "Não informado"
                    : `${detail.estimate_evidence.horizon_months} mês(es)`}
                </dd>
              </div>
            </dl>
            {metadata.source.is_demo ? (
              <p className="mt-3 text-sm">
                Regra: máximo entre zero e (referência − observação),
                multiplicado pelo horizonte em meses; arredondamento a duas
                casas.
              </p>
            ) : null}
            {metadata.source.is_demo &&
            detail.potential_recoverable_energy_kwh !== null &&
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
