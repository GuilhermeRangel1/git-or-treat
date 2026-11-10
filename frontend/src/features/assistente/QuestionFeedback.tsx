import { useState } from "react";
import {
  Ban,
  CalendarX,
  CircleHelp,
  Info,
  ShieldAlert,
  Wrench,
  type LucideIcon,
} from "lucide-react";
import Button from "@/shared/ui/Button";
import type { AIQuestionResponse, FeedbackReason } from "./contract";

type Presentation = {
  title: string;
  icon: LucideIcon;
  appearance: string;
};

const BY_REASON: Record<FeedbackReason, Presentation> = {
  out_of_domain: {
    title: "Posso ajudar com dados de energia",
    icon: Info,
    appearance: "text-content",
  },
  unsupported_capability: {
    title: "Essa análise ainda não está disponível",
    icon: Wrench,
    appearance: "text-muted",
  },
  insufficient_coverage: {
    title: "Os dados não cobrem todo o período",
    icon: CalendarX,
    appearance: "text-muted",
  },
  security_restriction: {
    title: "Não posso atender a essa solicitação",
    icon: ShieldAlert,
    appearance: "text-[var(--action-danger-text)]",
  },
  ambiguous_subject: {
    title: "Preciso de um esclarecimento",
    icon: CircleHelp,
    appearance: "text-brand",
  },
  missing_context: {
    title: "Preciso de um esclarecimento",
    icon: CircleHelp,
    appearance: "text-brand",
  },
};

const CLARIFICATION: Presentation = BY_REASON.missing_context;
const NEUTRAL_REFUSAL: Presentation = {
  title: "Não consegui atender a esta solicitação",
  icon: Ban,
  appearance: "text-muted",
};

/** O motivo vem do contrato tipado; sem motivo, a apresentação é neutra. */
function presentationFor(response: AIQuestionResponse): Presentation {
  const feedback = response.feedback;
  if (feedback?.reason) return BY_REASON[feedback.reason];
  if (feedback?.kind === "clarification") return CLARIFICATION;
  if (!feedback && response.status === "needs_clarification") {
    return CLARIFICATION;
  }
  // Rota legada: o código de erro tipado, não o texto, identifica assunto externo.
  if (response.error?.code === "out_of_scope") return BY_REASON.out_of_domain;
  return NEUTRAL_REFUSAL;
}

export default function QuestionFeedback({
  response,
  onChoose,
  choicesDisabled = false,
}: {
  response: AIQuestionResponse;
  onChoose: (question: string) => void;
  choicesDisabled?: boolean;
}) {
  const [chosen, setChosen] = useState(false);
  const { title, icon: Icon, appearance } = presentationFor(response);
  const options =
    response.status === "needs_clarification"
      ? (response.feedback?.options ?? [])
      : [];
  const disabled = choicesDisabled || chosen;

  return (
    <div className="mt-3 space-y-3">
      <h3
        className={`flex items-center gap-2 text-sm font-semibold ${appearance}`}
      >
        <Icon aria-hidden="true" className="size-4 shrink-0" />
        {title}
      </h3>
      <p className="whitespace-pre-wrap text-base leading-7 text-content [overflow-wrap:anywhere] sm:text-[17px]">
        {response.message}
      </p>
      {options.length > 0 && (
        <div role="group" aria-label="Opções de resposta" className="space-y-2">
          <ul className="flex flex-wrap gap-2">
            {options.map((option) => (
              <li key={option.question}>
                <Button
                  variant="outline"
                  size="sm"
                  disabled={disabled}
                  onClick={() => {
                    if (disabled) return;
                    setChosen(true);
                    onChoose(option.question);
                  }}
                >
                  {option.label}
                </Button>
              </li>
            ))}
          </ul>
          <p className="text-sm text-muted">
            Ou escreva outra resposta na caixa de texto.
          </p>
        </div>
      )}
    </div>
  );
}
