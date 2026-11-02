import { useRef, useState } from "react";
import Button from "@/shared/ui/Button";
import Modal from "@/shared/ui/Modal";
import type { GoldMetadata } from "@/shared/analytics/goldContract";
import type {
  GoldOperationDefinition,
  GoldOperationPoint,
  GoldOperationSummary,
} from "./gold-contract";
import {
  formatNumber,
  formatPeriod,
  formatUpdatedAt,
} from "./operation-format";

type Indicator = "dec" | "fec";

export default function GoldOperationFoundations({
  summary,
  metadata,
  definition,
  indicator: visibleIndicator = "both",
}: {
  summary: GoldOperationSummary | GoldOperationPoint;
  metadata: GoldMetadata;
  definition: GoldOperationDefinition;
  indicator?: Indicator | "both";
}) {
  const [indicator, setIndicator] = useState<Indicator | null>(null);
  const decTriggerRef = useRef<HTMLButtonElement>(null);
  const fecTriggerRef = useRef<HTMLButtonElement>(null);
  const triggerRef = indicator === "fec" ? fecTriggerRef : decTriggerRef;
  const isDec = indicator === "dec";
  const isSummary = "dec_included_feeder_ids" in summary;
  const included = isSummary
    ? isDec
      ? summary.dec_included_feeder_ids
      : summary.fec_included_feeder_ids
    : [summary.feeder_id];
  const excluded = isSummary
    ? isDec
      ? summary.dec_excluded_feeder_ids
      : summary.fec_excluded_feeder_ids
    : [];
  const numerator = isDec
    ? summary.duration_hours_sum
    : summary.interruption_count;
  const denominator = isSummary
    ? isDec
      ? summary.dec_denominator_uc_count
      : summary.fec_denominator_uc_count
    : summary.denominator_uc_count;
  const formula = isDec ? definition.dec_formula : definition.fec_formula;
  const unit = isDec ? definition.dec_unit : definition.fec_unit;
  const title = isDec ? "Fundamentos do DEC" : "Fundamentos do FEC";

  return (
    <>
      <div className="flex flex-wrap gap-2">
        {visibleIndicator !== "fec" ? (
          <Button
            ref={decTriggerRef}
            variant="ghost"
            className="w-fit"
            onClick={() => setIndicator("dec")}
          >
            Ver base do DEC
          </Button>
        ) : null}
        {visibleIndicator !== "dec" ? (
          <Button
            ref={fecTriggerRef}
            variant="ghost"
            className="w-fit"
            onClick={() => setIndicator("fec")}
          >
            Ver base do FEC
          </Button>
        ) : null}
      </div>
      <Modal
        open={indicator !== null}
        onClose={() => setIndicator(null)}
        triggerRef={triggerRef}
        title={title}
        description="Veja como o indicador foi calculado, qual base foi considerada e quais são os limites deste resultado."
        closeLabel="Fechar fundamentos"
        size="md"
        header="inline"
        className="grid gap-4 p-5 sm:p-6 [overflow-wrap:anywhere]"
      >
        <section className="grid gap-3 text-sm" aria-label={title}>
          <p>
            <strong>Período solicitado:</strong> {formatPeriod(summary.period)}.
          </p>
          <p>
            <strong>Período observado:</strong>{" "}
            {summary.observed_period
              ? formatPeriod(summary.observed_period)
              : "sem cobertura conhecida"}
            .
          </p>
          <p>
            <strong>Fórmula:</strong> {formula}
          </p>
          <p>
            <strong>Numerador:</strong>{" "}
            {numerator === null
              ? "indisponível"
              : `${formatNumber(numerator)} ${isDec ? "h" : "registros"}`}
            .
          </p>
          <p>
            <strong>Denominador:</strong>{" "}
            {denominator === null
              ? "indisponível"
              : denominator <= 0
                ? `${denominator} UCs · inválido`
                : `${denominator} UCs`}
            .
          </p>
          <p>
            <strong>Unidade:</strong> {unit}.
          </p>
          <p>
            <strong>Alimentadores considerados:</strong> {included.length}.
          </p>
          {isSummary ? (
            <p>
              <strong>Fora do cálculo:</strong> {excluded.length}{" "}
              alimentador(es).
            </p>
          ) : null}
          {summary.limitations.length ? (
            <div>
              <strong>Limitações:</strong>
              <ul className="mt-1 list-inside list-disc">
                {summary.limitations.map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
            </div>
          ) : null}
          <div className="grid gap-1 border-t border-border pt-3 text-xs text-muted">
            <p>
              <strong>Referência:</strong> {definition.reference}
            </p>
            <p>
              <strong>População:</strong> {definition.population}
            </p>
            <p>
              <strong>Cobertura:</strong> {definition.completeness}
            </p>
            <p>
              <strong>Atualizado em:</strong>{" "}
              {formatUpdatedAt(metadata.source.updated_at)}.
            </p>
          </div>
        </section>
      </Modal>
    </>
  );
}
