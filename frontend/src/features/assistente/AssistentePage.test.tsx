import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import TestProviders from "@/shared/test/TestProviders";
import AssistentePage from "./AssistentePage";

const answered = {
  contract_version: "v1",
  correlation_id: "0123456789abcdef0123456789abcdef",
  status: "answered",
  answer: "O consumo demonstrativo aumentou 12% no período informado.",
  message: null,
  evidence: [
    {
      source: "synthetic.fixture",
      description: "Cenário artificial de consumo.",
      is_demo: true,
    },
  ],
  limitations: ["Os valores não representam dados reais da V-Energy."],
  analysis_context: {
    metric: "Consumo",
    unit: "kWh fictícios",
    period: "2025-01 a 2025-02",
    filters: { municipio: "Exemplo" },
  },
};

function jsonResponse(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function renderPage() {
  return render(<AssistentePage />, { wrapper: TestProviders });
}

afterEach(() => vi.unstubAllGlobals());

describe("Assistente Grid 360", () => {
  it("mostra carregamento e bloqueia outro envio até a resposta", async () => {
    let resolveResponse: (response: Response) => void = () => undefined;
    const pendingResponse = new Promise<Response>((resolve) => {
      resolveResponse = resolve;
    });
    vi.stubGlobal("fetch", vi.fn().mockReturnValue(pendingResponse));
    const user = userEvent.setup();
    renderPage();

    const textbox = screen.getByRole("textbox", {
      name: "Escreva sua pergunta",
    });
    await user.type(textbox, "Qual é o consumo fictício?");
    await user.keyboard("{Enter}");

    expect(await screen.findByRole("status")).toHaveTextContent(
      "Analisando a pergunta e consultando evidências",
    );
    const sendButton = screen.getByRole("button", { name: "Enviar pergunta" });
    expect(sendButton).toBeVisible();
    expect(sendButton).toBeDisabled();
    expect(screen.queryByText("Enviando")).not.toBeInTheDocument();
    expect(textbox).toBeDisabled();
    resolveResponse(jsonResponse(answered));
    expect(await screen.findByText(answered.answer)).toBeVisible();
  });

  it("envia a pergunta ao Backend e mostra resposta, recorte e evidência demonstrativa", async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(answered));
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();
    renderPage();

    await user.type(
      screen.getByRole("textbox", { name: "Escreva sua pergunta" }),
      "Como variou o consumo?",
    );
    await user.click(screen.getByRole("button", { name: "Enviar pergunta" }));

    expect(await screen.findByText(answered.answer)).toBeVisible();
    expect(screen.getByText("Resposta fundamentada")).toBeVisible();
    expect(screen.getByText(/Demonstração sintética/)).toBeVisible();
    expect(screen.getByText(/Cenário artificial de consumo/)).toBeVisible();
    expect(screen.getByText(/2025-01 a 2025-02/)).toBeVisible();
    expect(
      screen.getByText(/Os valores não representam dados reais/),
    ).toBeVisible();

    const [, options] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(options.method).toBe("POST");
    expect(JSON.parse(String(options.body))).toEqual({
      contract_version: "v1",
      question: "Como variou o consumo?",
      context: [],
    });
    expect(String(fetchMock.mock.calls[0][0])).toBe("/api/v1/ai/questions");
  });

  it("mantém esclarecimento sem evidência separado de uma resposta", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        jsonResponse({
          contract_version: "v1",
          status: "needs_clarification",
          answer: null,
          message: "Qual período você quer consultar?",
          evidence: [],
          limitations: [],
        }),
      ),
    );
    const user = userEvent.setup();
    renderPage();

    await user.type(
      screen.getByRole("textbox", { name: "Escreva sua pergunta" }),
      "E o consumo?",
    );
    await user.keyboard("{Enter}");

    expect(
      await screen.findByText("Qual período você quer consultar?"),
    ).toBeVisible();
    expect(screen.getByText("Preciso de um esclarecimento")).toBeVisible();
    expect(
      screen.queryByText(/Demonstração sintética/),
    ).not.toBeInTheDocument();
  });

  it.each([
    [
      "refused",
      "Solicitação recusada",
      "Não posso responder a esse pedido.",
      { code: "out_of_scope", retryable: false },
    ],
    [
      "no_evidence",
      "Sem evidência para esse recorte",
      "Não há dados para esse recorte.",
      null,
    ],
    [
      "recoverable_error",
      "Erro recuperável",
      "A fonte está temporariamente indisponível.",
      { code: "service_unavailable", retryable: true },
    ],
  ] as const)(
    "identifica explicitamente o estado %s",
    async (status, label, message, error) => {
      vi.stubGlobal(
        "fetch",
        vi.fn().mockResolvedValue(
          jsonResponse({
            contract_version: "v1",
            status,
            answer: null,
            message,
            error,
            evidence: [],
            limitations: [],
          }),
        ),
      );
      const user = userEvent.setup();
      renderPage();

      await user.type(
        screen.getByRole("textbox", { name: "Escreva sua pergunta" }),
        "Pergunta de teste",
      );
      await user.keyboard("{Enter}");

      expect(await screen.findByText(label)).toBeVisible();
      expect(screen.getByText(message)).toBeVisible();
    },
  );

  it("apresenta falha de rede e permite repetir manualmente o envio", async () => {
    const fetchMock = vi
      .fn()
      .mockRejectedValueOnce(new TypeError("Failed to fetch"))
      .mockResolvedValueOnce(jsonResponse(answered));
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();
    renderPage();

    await user.type(
      screen.getByRole("textbox", { name: "Escreva sua pergunta" }),
      "Como variou o consumo?",
    );
    await user.keyboard("{Enter}");

    expect(
      await screen.findByText(
        /Não foi possível conectar ao serviço de resposta/,
      ),
    ).toBeVisible();
    await user.click(screen.getByRole("button", { name: "Tentar novamente" }));
    expect(await screen.findByText(answered.answer)).toBeVisible();
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it("envia no máximo três turnos de contexto e mantém a conversa só em memória", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse(answered))
      .mockResolvedValueOnce(
        jsonResponse({
          ...answered,
          answer: "A receita demonstrativa foi estável.",
          analysis_context: null,
        }),
      )
      .mockResolvedValueOnce(
        jsonResponse({
          ...answered,
          answer: "Há duas interrupções artificiais.",
          analysis_context: null,
        }),
      );
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();
    renderPage();

    const textbox = screen.getByRole("textbox", {
      name: "Escreva sua pergunta",
    });
    await user.type(textbox, "Como variou o consumo?");
    await user.keyboard("{Enter}");
    await screen.findByText(answered.answer);
    await user.type(textbox, "E quanto à receita?");
    await user.keyboard("{Enter}");
    await screen.findByText("A receita demonstrativa foi estável.");
    await user.type(textbox, "E as interrupções?");
    await user.keyboard("{Enter}");
    await screen.findByText("Há duas interrupções artificiais.");

    const history = screen.getByRole("log", { name: "Histórico da conversa" });
    expect(history).not.toContainElement(textbox);
    expect(textbox.closest("form")).not.toBeNull();

    const secondRequest = JSON.parse(
      String((fetchMock.mock.calls[2] as [string, RequestInit])[1].body),
    );
    expect(secondRequest.context).toEqual([
      { role: "assistant", content: answered.answer },
      { role: "user", content: "E quanto à receita?" },
      { role: "assistant", content: "A receita demonstrativa foi estável." },
    ]);
    expect(Object.keys(localStorage)).toEqual(["grid360_theme"]);

    await user.click(screen.getByRole("button", { name: /Nova conversa/ }));
    expect(screen.queryByText(answered.answer)).not.toBeInTheDocument();
    expect(screen.getByText(/fica apenas nesta tela/)).toBeVisible();
  });

  it("oferece repetição manual somente quando o erro diz que é recuperável", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        jsonResponse(
          {
            contract_version: "v1",
            status: "error",
            correlation_id: "0123456789abcdef0123456789abcdef",
            message: "O serviço de resposta está temporariamente indisponível.",
            error: { code: "service_unavailable", retryable: true },
          },
          503,
        ),
      )
      .mockResolvedValueOnce(jsonResponse(answered));
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();
    renderPage();

    await user.type(
      screen.getByRole("textbox", { name: "Escreva sua pergunta" }),
      "Como variou o consumo?",
    );
    await user.keyboard("{Enter}");
    expect(
      await screen.findByText(
        "O serviço de resposta está temporariamente indisponível.",
      ),
    ).toBeVisible();
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1));
    await user.click(screen.getByRole("button", { name: "Tentar novamente" }));
    expect(await screen.findByText(answered.answer)).toBeVisible();
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });
});
