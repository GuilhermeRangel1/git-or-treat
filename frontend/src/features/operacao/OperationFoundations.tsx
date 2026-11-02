import { useRef, useState } from "react";
import type {
  OperationDetailEnvelope,
  OperationSummaryEnvelope,
} from "./contract";
import Button from "@/shared/ui/Button";
import Modal from "@/shared/ui/Modal";
import {
  formatMonthReferences,
  formatPeriod,
  formatUpdatedAt,
} from "./operation-format";

export default function OperationFoundations({
  summary,
  detail,
}: {
  summary?: OperationSummaryEnvelope;
  detail?: OperationDetailEnvelope;
}) {
  const [open, setOpen] = useState(false);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const definition = detail?.data.definition ?? summary?.data.definition;
  const summaryData = summary?.data.summary;
  const point = detail?.data.summary;
  const source = detail?.metadata.source ?? summary?.metadata.source;
  const period = point?.period ?? summaryData?.period;
  const observedPeriod = point?.observed_period ?? summaryData?.observed_period;
  const denominatorLabel = point
    ? point.denominator_uc_count === null
      ? "indisponível"
      : point.denominator_uc_count <= 0
        ? `${point.denominator_uc_count} UCs · inválido`
        : point.status === "unavailable"
          ? `${point.denominator_uc_count} UCs · não elegível nesta janela`
          : `${point.denominator_uc_count} UCs`
    : summaryData?.denominator_uc_count === null ||
        summaryData?.denominator_uc_count === undefined
      ? "indisponível"
      : `${summaryData.denominator_uc_count} UCs`;

  return (
    <>
      <Button
        ref={triggerRef}
        variant="ghost"
        className="w-fit"
        onClick={() => setOpen(true)}
      >
        {detail ? "Ver fórmula e base do alimentador" : "Ver fundamentos"}
      </Button>
      <Modal
        open={open}
        onClose={() => setOpen(false)}
        triggerRef={triggerRef}
        title={
          detail
            ? "Fórmula e base do alimentador"
            : "Fundamentos do consolidado"
        }
        description="Definição recebida com a resposta da API. Indicadores demonstrativos não são apuração regulatória oficial."
        closeLabel="Fechar fundamentos"
        size="md"
        header="inline"
        className="grid gap-4 p-5 sm:p-6 [overflow-wrap:anywhere]"
      >
        <section
          role="region"
          aria-label={
            detail ? "Fundamentos do alimentador" : "Fundamentos do consolidado"
          }
          className="grid gap-4 text-sm"
        >
          {summaryData ? (
            <>
              <p>
                <strong>Período solicitado:</strong>{" "}
                {formatPeriod(summaryData.period)}.
              </p>
              <p>
                <strong>Período observado:</strong>{" "}
                {summaryData.observed_period
                  ? formatPeriod(summaryData.observed_period)
                  : "sem cobertura conhecida"}
                .
              </p>
              <p>
                <strong>Numerador DEC:</strong>{" "}
                {summaryData.duration_hours_sum === null
                  ? "indisponível"
                  : `${summaryData.duration_hours_sum} h`}
                .
              </p>
              <p>
                <strong>Numerador FEC:</strong>{" "}
                {summaryData.interruption_count === null
                  ? "indisponível"
                  : summaryData.interruption_count}{" "}
                registros UC–interrupção.
              </p>
              <p>
                <strong>Base incluída:</strong> {denominatorLabel}.
              </p>
              <p>
                <strong>População do recorte:</strong>{" "}
                {summaryData.served_uc_count} UCs.
              </p>
              <p>
                <strong>População incluída:</strong>{" "}
                {summaryData.included_uc_count} UCs.
              </p>
              <p>
                <strong>Alimentadores incluídos:</strong>{" "}
                {summaryData.included_feeder_ids.length} alimentador(es).
              </p>
              <p>
                <strong>Alimentadores excluídos:</strong>{" "}
                {summaryData.excluded_feeder_ids.length} alimentador(es).
              </p>
              {summaryData.limitations.map((item) => (
                <p key={item}>{formatMonthReferences(item)}</p>
              ))}
            </>
          ) : point ? (
            <>
              <p>
                <strong>Período solicitado:</strong> {formatPeriod(period!)}.
              </p>
              <p>
                <strong>Período observado:</strong>{" "}
                {observedPeriod
                  ? formatPeriod(observedPeriod)
                  : "sem cobertura conhecida"}
                .
              </p>
              <p>
                <strong>Numerador DEC:</strong> {point.duration_hours_sum} h.
              </p>
              <p>
                <strong>Numerador FEC:</strong> {point.interruption_count}{" "}
                registros UC–interrupção.
              </p>
              <p>
                <strong>Alimentador:</strong> {point.feeder_id}.
              </p>
              <p>
                <strong>
                  {point.status === "available" || point.status === "partial"
                    ? "Base incluída"
                    : "Denominador informado"}
                  :
                </strong>{" "}
                {denominatorLabel}.
              </p>
              <p>
                <strong>População atendida:</strong> {point.served_uc_count} UCs
                · <strong>UCs cobertas:</strong> {point.covered_uc_count}.
              </p>
              <p>{formatMonthReferences(point.text_alternative)}</p>
              {point.limitations.map((item) => (
                <p key={item}>{formatMonthReferences(item)}</p>
              ))}
            </>
          ) : null}
          {definition ? (
            <>
              <p className="font-medium">{definition.label}</p>
              <div>
                <h3 className="font-semibold">
                  DEC simplificado ({definition.dec_unit})
                </h3>
                <p>{definition.dec_formula}</p>
              </div>
              <div>
                <h3 className="font-semibold">
                  FEC simplificado ({definition.fec_unit})
                </h3>
                <p>{definition.fec_formula}</p>
              </div>
              <p>
                <strong>População:</strong> {definition.population}
              </p>
              <p>
                <strong>Unidade de eventos:</strong> {definition.event_grain}
              </p>
              <p>
                <strong>Arredondamento:</strong> {definition.rounding}
              </p>
              {summaryData ? (
                <p>
                  <strong>Regra de inclusão:</strong>{" "}
                  {summary?.data.definition.inclusion_rule}
                </p>
              ) : null}
              <p>
                <strong>Referência:</strong> {definition.reference}
              </p>
            </>
          ) : (
            <p role="status">Definição indisponível nesta resposta.</p>
          )}
          {source?.updated_at ? (
            <p className="border-t border-border pt-3 text-xs text-muted">
              Atualizado em {formatUpdatedAt(source.updated_at)}.
            </p>
          ) : null}
        </section>
      </Modal>
    </>
  );
}
