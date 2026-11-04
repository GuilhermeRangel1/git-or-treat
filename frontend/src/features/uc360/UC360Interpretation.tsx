import type { UCOverview } from "./contract";
import { signedValueTone } from "@/shared/ui/signedValue";
import {
  formatUCAmount,
  formatUCCompetence,
  humanizeLimitation,
  statusLabel,
} from "./uc360-format";

function hasComparablePair(
  initial: { value: number | null },
  final: { value: number | null },
) {
  return initial.value !== null && final.value !== null;
}

export default function UC360Interpretation({
  data,
}: {
  data: UCOverview["data"];
}) {
  const { comparison } = data;
  const hasComparableValues =
    hasComparablePair(
      comparison.initial.measured_energy_kwh,
      comparison.final.measured_energy_kwh,
    ) ||
    hasComparablePair(
      comparison.initial.billed_amount,
      comparison.final.billed_amount,
    );
  const billIncrease =
    comparison.billed_amount.status === "available" &&
    comparison.billed_amount.delta !== null &&
    comparison.billed_amount.delta > 0 &&
    hasComparablePair(
      comparison.initial.billed_amount,
      comparison.final.billed_amount,
    );

  return (
    <section className="grid gap-3 sm:grid-cols-2">
      <article className="rounded-xl border border-control bg-surface p-4">
        <h3 className="font-heading font-semibold">O que os dados mostram</h3>
        <ul className="mt-2 grid gap-2 text-sm text-content">
          <li>
            Consumo medido:{" "}
            <span
              className={signedValueTone(
                comparison.initial.measured_energy_kwh.value,
                false,
              )}
            >
              {formatUCAmount(
                comparison.initial.measured_energy_kwh.value,
                "kWh",
              )}
            </span>{" "}
            em {formatUCCompetence(comparison.initial.competencia)} →{" "}
            <span
              className={signedValueTone(
                comparison.final.measured_energy_kwh.value,
                false,
              )}
            >
              {formatUCAmount(
                comparison.final.measured_energy_kwh.value,
                "kWh",
              )}
            </span>{" "}
            em {formatUCCompetence(comparison.final.competencia)}.
          </li>
          <li>
            {comparison.initial.billed_amount.status === "empty" &&
            comparison.final.billed_amount.status === "empty" ? (
              "Sem faturas nos meses comparados."
            ) : (
              <>
                Valor faturado:{" "}
                <span
                  className={signedValueTone(
                    comparison.initial.billed_amount.value,
                    false,
                  )}
                >
                  {formatUCAmount(
                    comparison.initial.billed_amount.value,
                    "BRL",
                  )}
                </span>{" "}
                →{" "}
                <span
                  className={signedValueTone(
                    comparison.final.billed_amount.value,
                    false,
                  )}
                >
                  {formatUCAmount(comparison.final.billed_amount.value, "BRL")}
                </span>{" "}
                ({formatUCCompetence(comparison.initial.competencia)} a{" "}
                {formatUCCompetence(comparison.final.competencia)}).
              </>
            )}
          </li>
          <li>
            Situação do consumo:{" "}
            {statusLabel(comparison.measured_energy_kwh.status)}. Situação do
            valor faturado: {statusLabel(comparison.billed_amount.status)}.
          </li>
        </ul>
      </article>
      <article className="rounded-xl border border-control bg-surface p-4">
        <h3 className="font-heading font-semibold">
          O que ainda não dá para concluir
        </h3>
        <p className="mt-2 text-sm text-muted">
          {billIncrease
            ? "Os valores mostram o que mudou, mas não explicam a causa do aumento. Consulte as faturas e o histórico de consumo antes de informar uma causa ao cliente."
            : hasComparableValues
              ? "Os valores comparados não explicam, por si só, uma mudança na conta. Consulte as faturas e o histórico de consumo para investigar o período."
              : "Não há dados disponíveis para comparar os dois meses selecionados. Consulte o histórico de faturas e leituras para conferir o período."}
        </p>
        {comparison.measured_energy_kwh.limitations.length > 0 && (
          <p className="mt-2 text-xs text-muted">
            {comparison.measured_energy_kwh.limitations
              .map(humanizeLimitation)
              .join(" ")}
          </p>
        )}
      </article>
    </section>
  );
}
