import { afterEach, describe, expect, it, vi } from "vitest";
import { askAIQuestion } from "./api";

const validResponse = {
  contract_version: "v1",
  correlation_id: "0123456789abcdef0123456789abcdef",
  status: "answered",
  answer: "Resposta demonstrativa.",
  message: null,
  evidence: [
    {
      source: "synthetic.fixture",
      description: "Evidência artificial.",
      is_demo: true,
    },
  ],
  limitations: [],
};

afterEach(() => vi.unstubAllGlobals());

describe("cliente do chat", () => {
  it("envia o contrato v1 ao Backend e valida a resposta", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify(validResponse), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
    vi.stubGlobal("fetch", fetchMock);

    const result = await askAIQuestion({
      contract_version: "v1",
      question: "Qual foi o consumo?",
      context: [{ role: "user", content: "No período de demonstração." }],
    });

    const [url, options] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toBe("/api/v1/ai/questions");
    expect(options.method).toBe("POST");
    expect(new Headers(options.headers).get("Content-Type")).toBe(
      "application/json",
    );
    expect(options.body).toBe(
      JSON.stringify({
        contract_version: "v1",
        question: "Qual foi o consumo?",
        context: [{ role: "user", content: "No período de demonstração." }],
      }),
    );
    expect(result).toMatchObject({
      status: "answered",
      evidence: [{ is_demo: true }],
    });
  });

  it("mantém o código retryable do erro HTTP sem expor detalhes técnicos", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(
          JSON.stringify({
            contract_version: "v1",
            status: "error",
            correlation_id: "0123456789abcdef0123456789abcdef",
            message: "O serviço de resposta está temporariamente indisponível.",
            error: { code: "service_unavailable", retryable: true },
          }),
          { status: 503, headers: { "Content-Type": "application/json" } },
        ),
      ),
    );

    await expect(
      askAIQuestion({
        contract_version: "v1",
        question: "Pergunta",
        context: [],
      }),
    ).rejects.toMatchObject({
      retryable: true,
      message: "O serviço de resposta está temporariamente indisponível.",
      correlationId: "0123456789abcdef0123456789abcdef",
    });
  });

  it("encaminha sinal de cancelamento para a pergunta em voo", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify(validResponse), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
    vi.stubGlobal("fetch", fetchMock);
    const controller = new AbortController();
    await askAIQuestion(
      { contract_version: "v1", question: "Pergunta", context: [] },
      controller.signal,
    );
    expect(fetchMock.mock.calls[0][1]?.signal).toBe(controller.signal);
  });

  it("rejeita JSON de sucesso fora do contrato v1", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(JSON.stringify({ ...validResponse, evidence: [] }), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }),
      ),
    );

    await expect(
      askAIQuestion({
        contract_version: "v1",
        question: "Pergunta",
        context: [],
      }),
    ).rejects.toThrow(
      "O serviço retornou uma resposta fora do contrato esperado.",
    );
  });
});
