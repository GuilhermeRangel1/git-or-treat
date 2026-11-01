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
      "Não foi possível apresentar a resposta. Tente uma nova pergunta em instantes.",
    );
  });
});

it.each([401, 403, 409, 422, 429])(
  "trata HTTP %s sem expor o corpo técnico nem repetir automaticamente",
  async (status) => {
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValue(
          Response.json({ detail: "SELECT secret FROM internal" }, { status }),
        ),
    );
    await expect(
      askAIQuestion({
        contract_version: "v1",
        question: "Qual a receita?",
        context: [],
      }),
    ).rejects.toMatchObject({ status, retryable: false });
    await expect(
      askAIQuestion({
        contract_version: "v1",
        question: "Qual a receita?",
        context: [],
      }),
    ).rejects.not.toHaveProperty("message", expect.stringContaining("SELECT"));
  },
);

it("interrompe uma consulta que não responde e permite repetição manual", async () => {
  vi.useFakeTimers();
  try {
    vi.stubGlobal(
      "fetch",
      vi.fn(
        (_url, options: RequestInit) =>
          new Promise((_resolve, reject) =>
            options.signal?.addEventListener("abort", () =>
              reject(new DOMException("Aborted", "AbortError")),
            ),
          ),
      ),
    );
    const result = expect(
      askAIQuestion({
        contract_version: "v1",
        question: "Qual a receita?",
        context: [],
      }),
    ).rejects.toMatchObject({
      retryable: true,
      message: expect.stringContaining("demorou"),
    });
    await vi.advanceTimersByTimeAsync(40_000);
    await result;
  } finally {
    vi.useRealTimers();
  }
});
