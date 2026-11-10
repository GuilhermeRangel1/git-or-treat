import { useId } from "react";
import { Lightbulb } from "lucide-react";
import type { DiagnosisSummary } from "./revenue-diagnosis-summary";

/**
 * Resposta ao Diretor, montada por regras a partir do diagnóstico.
 * Não é texto da IA: por isso o selo "Calculado" e nenhum ícone de IA.
 */
export default function PanoramaDiagnosisInsight({
  summary,
}: {
  summary: DiagnosisSummary;
}) {
  const titleId = useId();
  return (
    <section
      aria-labelledby={titleId}
      data-diagnosis-insight=""
      className="flex h-full min-w-0 flex-col gap-3 rounded-lg border border-border bg-[var(--accent-pistache-subtle)] p-4"
    >
      <div className="flex items-center justify-between gap-3">
        <div className="flex min-w-0 items-center gap-2.5">
          <span className="grid size-9 shrink-0 place-items-center rounded-lg bg-surface text-[var(--accent-pistache)]">
            <Lightbulb aria-hidden="true" className="size-4" />
          </span>
          <div className="min-w-0">
            {/* Título sempre em uma linha: em telas estreitas, trunca em vez de quebrar. */}
            <h3
              id={titleId}
              className="truncate font-heading text-sm font-semibold text-content"
            >
              Resposta ao Diretor
            </h3>
            <p className="text-xs text-muted">
              Leitura do diagnóstico · calculada dos dados
            </p>
          </div>
        </div>
        <span className="shrink-0 rounded-full border border-[var(--line)] bg-surface px-2.5 py-1 text-[11px] font-semibold tracking-wide text-content">
          Calculado
        </span>
      </div>

      <p className="font-heading text-base font-semibold leading-6 text-content">
        {summary.question}
      </p>

      <div className="space-y-2 text-sm leading-5 text-content">
        {summary.paragraphs.map((paragraph) => (
          <p key={paragraph.lead}>
            <strong className="font-semibold">{paragraph.lead}</strong>
            {paragraph.body ? ` ${paragraph.body}` : ""}
          </p>
        ))}
      </div>

      {summary.nextStep ? (
        <p className="border-l-2 border-[var(--accent-pistache)] pl-3 text-xs leading-5 text-muted">
          <span className="font-semibold text-content">Próximo passo:</span>{" "}
          {summary.nextStep}
        </p>
      ) : null}

      <p className="mt-auto text-[11px] leading-4 text-muted">
        {summary.footer}
      </p>
    </section>
  );
}
