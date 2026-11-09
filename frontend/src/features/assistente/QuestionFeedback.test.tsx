import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import type {
  AIQuestionResponse,
  FeedbackReason,
  QuestionFeedback as Feedback,
} from "./contract";
import QuestionFeedback from "./QuestionFeedback";

function response(
  status: "needs_clarification" | "refused",
  message: string,
  feedback?: Partial<Feedback>,
  errorCode?: string,
): AIQuestionResponse {
  return {
    contract_version: "v1",
    status,
    message,
    evidence: [],
    limitations: [],
    sql_analysis_mode: true,
    ...(errorCode ? { error: { code: errorCode, retryable: false } } : {}),
    ...(feedback
      ? {
          feedback: {
            kind: status === "refused" ? "refusal" : "clarification",
            reason: null,
            missingFields: status === "refused" ? [] : ["period"],
            options: [],
            ...feedback,
          },
        }
      : {}),
  };
}

describe("QuestionFeedback", () => {
  it.each<[FeedbackReason, string]>([
    ["out_of_domain", "Posso ajudar com dados de energia"],
    ["unsupported_capability", "Essa análise ainda não está disponível"],
    ["insufficient_coverage", "Os dados não cobrem todo o período"],
    ["security_restriction", "Não posso atender a essa solicitação"],
  ])("usa o título de %s sem depender da prosa", (reason, title) => {
    render(
      <QuestionFeedback
        response={response("refused", "Mensagem qualquer do serviço.", {
          reason,
        })}
        onChoose={vi.fn()}
      />,
    );
    expect(screen.getByRole("heading", { name: title })).toBeVisible();
    expect(screen.getByText("Mensagem qualquer do serviço.")).toBeVisible();
    expect(screen.queryByText("Solicitação recusada")).not.toBeInTheDocument();
  });

  it("mantém o título de esclarecimento e a pergunta original", () => {
    for (const reason of [
      "ambiguous_subject",
      "missing_context",
      null,
    ] as const) {
      const { unmount } = render(
        <QuestionFeedback
          response={response("needs_clarification", "Junho de qual ano?", {
            reason,
          })}
          onChoose={vi.fn()}
        />,
      );
      expect(
        screen.getByRole("heading", { name: "Preciso de um esclarecimento" }),
      ).toBeVisible();
      expect(screen.getByText("Junho de qual ano?")).toBeVisible();
      unmount();
    }
  });

  it("usa cobertura insuficiente também quando é um esclarecimento", () => {
    render(
      <QuestionFeedback
        response={response("needs_clarification", "Faltam julho a dezembro.", {
          reason: "insufficient_coverage",
        })}
        onChoose={vi.fn()}
      />,
    );
    expect(
      screen.getByRole("heading", {
        name: "Os dados não cobrem todo o período",
      }),
    ).toBeVisible();
  });

  it("trata o código legado out_of_scope como assunto externo", () => {
    render(
      <QuestionFeedback
        response={response(
          "refused",
          "Fora do domínio.",
          undefined,
          "out_of_scope",
        )}
        onChoose={vi.fn()}
      />,
    );
    expect(
      screen.getByRole("heading", {
        name: "Posso ajudar com dados de energia",
      }),
    ).toBeVisible();
  });

  it("usa apresentação neutra para recusa antiga sem motivo e preserva a mensagem", () => {
    render(
      <QuestionFeedback
        response={response(
          "refused",
          "Texto salvo antes do motivo existir.",
          { reason: null },
          "unsupported_operation",
        )}
        onChoose={vi.fn()}
      />,
    );
    expect(
      screen.getByRole("heading", {
        name: "Não consegui atender a esta solicitação",
      }),
    ).toBeVisible();
    expect(
      screen.getByText("Texto salvo antes do motivo existir."),
    ).toBeVisible();
    expect(screen.queryByText(/recusada/i)).not.toBeInTheDocument();
  });

  it("não apresenta nenhum termo interno nem dado quantitativo", () => {
    const { container } = render(
      <QuestionFeedback
        response={response(
          "refused",
          "Não tenho dados de eventos esportivos.",
          {
            reason: "out_of_domain",
          },
        )}
        onChoose={vi.fn()}
      />,
    );
    expect(container.textContent).not.toMatch(/\bF1\b|Gold|SQL|reason_code/i);
    expect(screen.queryByRole("table")).not.toBeInTheDocument();
    expect(screen.queryByRole("img")).not.toBeInTheDocument();
  });

  describe("opções", () => {
    const options = [
      { label: "2025", question: "Qual a receita em junho de 2025?" },
      { label: "2026", question: "Qual a receita em junho de 2026?" },
    ];
    const clarification = () =>
      response("needs_clarification", "Junho de qual ano?", {
        reason: "missing_context",
        options,
      });

    it("envia a pergunta da opção uma única vez e bloqueia nova escolha", async () => {
      const onChoose = vi.fn();
      const user = userEvent.setup();
      render(
        <QuestionFeedback response={clarification()} onChoose={onChoose} />,
      );

      const first = screen.getByRole("button", { name: "2025" });
      await user.click(first);
      await user.click(first);
      await user.click(screen.getByRole("button", { name: "2026" }));

      expect(onChoose).toHaveBeenCalledTimes(1);
      expect(onChoose).toHaveBeenCalledWith("Qual a receita em junho de 2025?");
      expect(screen.getByRole("button", { name: "2026" })).toBeDisabled();
    });

    it("permite escolher por teclado e oferece resposta livre", async () => {
      const onChoose = vi.fn();
      const user = userEvent.setup();
      render(
        <QuestionFeedback response={clarification()} onChoose={onChoose} />,
      );

      await user.tab();
      expect(screen.getByRole("button", { name: "2025" })).toHaveFocus();
      await user.tab();
      expect(screen.getByRole("button", { name: "2026" })).toHaveFocus();
      await user.keyboard("{Enter}");

      expect(onChoose).toHaveBeenCalledWith("Qual a receita em junho de 2026?");
      expect(
        screen.getByText(/ou escreva outra resposta na caixa de texto/i),
      ).toBeVisible();
    });

    it("desabilita as escolhas enquanto outra consulta está em andamento", () => {
      render(
        <QuestionFeedback
          response={clarification()}
          onChoose={vi.fn()}
          choicesDisabled
        />,
      );
      expect(screen.getByRole("button", { name: "2025" })).toBeDisabled();
      expect(screen.getByRole("button", { name: "2026" })).toBeDisabled();
    });

    it("não oferece opções quando o serviço não enviou nenhuma", () => {
      render(
        <QuestionFeedback
          response={response("needs_clarification", "Qual município?", {
            reason: "missing_context",
          })}
          onChoose={vi.fn()}
        />,
      );
      expect(screen.queryByRole("button")).not.toBeInTheDocument();
      expect(screen.queryByRole("group")).not.toBeInTheDocument();
    });
  });
});
