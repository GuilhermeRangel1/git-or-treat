import { decodeGoldMetadata } from "@/shared/analytics/goldContract";
import {
  acceptGoldPublication,
  resetGoldPublication,
  isGoldPublicationStale,
} from "@/shared/analytics/goldPublication";
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

afterEach(() => {
  vi.unstubAllGlobals();
  resetGoldPublication();
});

describe("cliente do chat", () => {
  it("usa a rota F1 sem streaming legado nem publicação fornecida pelo navegador", async () => {
    const response = {
      correlation_id: "0123456789abcdef0123456789abcdef",
      audit_reference: "abcdef0123456789abcdef0123456789",
      status: "answered",
      evidence: {
        batch_ref:
          "gold-csv-v2:GOLD_20261106T000000Z_aaaaaaaa:12345678-1234-4123-8123-123456789abc",
        evidence_digest: "a".repeat(64),
        columns: [{ name: "revenue", role: "measure", unit: "R$" }],
        rows: [["1234.50"]],
      },
      presentation: {
        contract_version: "text-to-sql-f1-presentation-v1",
        state: "ready",
        operation: "total",
        answer: "O faturamento total foi R$ 1.234,50.",
        period: "2026-06",
        filters: [],
        universe: [],
        limitations: [
          "Faturamento representa valor faturado e não confirma recebimento ou pagamento.",
        ],
        columns: [
          {
            key: "revenue",
            label: "Faturamento",
            role: "measure",
            semantic_id: "revenue_total",
            unit: "R$",
          },
        ],
        rows: [{ observation_id: "row_1", cells: ["1234.50"] }],
        evidence_digest: "a".repeat(64),
      },
      continuation_token: "signed-continuation-token",
    };
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify(response), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
    vi.stubGlobal("fetch", fetchMock);
    const onData = vi.fn();
    const result = await askAIQuestion(
      {
        contract_version: "v1",
        question: "Faturamento total de Recife em junho?",
        context: [{ role: "user", content: "Faturamento anterior" }],
        conversation_id: "8abf4322-17ab-4a75-98f1-29481ee9f456",
        continuation_token: "previous-signed-token",
      },
      onData,
      undefined,
      "sql_f1",
    );
    const [url, options] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toBe("/api/v1/ai/sql-analyses");
    expect(new Headers(options.headers).get("Accept")).not.toBe(
      "application/x-ndjson",
    );
    expect(JSON.parse(String(options.body))).toEqual({
      contract_version: "v1",
      question: "Faturamento total de Recife em junho?",
      conversation_id: "8abf4322-17ab-4a75-98f1-29481ee9f456",
      continuation_token: "previous-signed-token",
    });
    expect(result.sql_analysis_mode).toBe(true);
    expect(result.continuation_token).toBe("signed-continuation-token");
    expect(onData).not.toHaveBeenCalled();
  });

  it("expiração do contexto não invalida os dados do portal", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(
          JSON.stringify({
            contract_version: "v1",
            status: "error",
            correlation_id: "a".repeat(32),
            message: "Contexto inválido.",
            error: { code: "invalid_continuation", retryable: false },
          }),
          { status: 409, headers: { "Content-Type": "application/json" } },
        ),
      ),
    );
    await expect(
      askAIQuestion({
        contract_version: "v1",
        question: "E em Olinda?",
        context: [],
      }),
    ).rejects.toMatchObject({ code: "invalid_continuation", retryable: false });
    expect(isGoldPublicationStale()).toBe(false);
  });

  it("salva consultas F1 pela rota de conversas mantendo o contrato F1", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({}), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
    vi.stubGlobal("fetch", fetchMock);
    await expect(
      askAIQuestion(
        {
          contract_version: "v1",
          question: "E no ano anterior?",
          context: [],
          conversation_id: "8abf4322-17ab-4a75-98f1-29481ee9f456",
          history_request_id: "c0f6d390-c3a2-4d4f-b72c-31e070df9f77",
        },
        undefined,
        undefined,
        "sql_f1",
      ),
    ).rejects.toThrow("Não foi possível apresentar a resposta.");
    const [url, options] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toBe(
      "/api/v1/ai/conversations/8abf4322-17ab-4a75-98f1-29481ee9f456/questions",
    );
    expect(JSON.parse(String(options.body))).toEqual({
      request_id: "c0f6d390-c3a2-4d4f-b72c-31e070df9f77",
      question: "E no ano anterior?",
      strategy: "sql_f1",
      refresh_context: false,
    });
  });

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
    const fetchMock = vi.fn().mockImplementation(
      (_path, init) =>
        new Promise((_resolve, reject) => {
          init.signal.addEventListener("abort", () =>
            reject(new DOMException("Aborted", "AbortError")),
          );
        }),
    );
    vi.stubGlobal("fetch", fetchMock);
    const controller = new AbortController();
    const request = askAIQuestion(
      { contract_version: "v1", question: "Pergunta", context: [] },
      undefined,
      controller.signal,
    );
    controller.abort();
    await expect(request).rejects.toBeDefined();
    expect(fetchMock.mock.calls[0][1]?.signal.aborted).toBe(true);
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
    await vi.advanceTimersByTimeAsync(60_000);
    expect(fetch).toHaveBeenCalledTimes(1);
    expect(
      (vi.mocked(fetch).mock.calls[0][1] as RequestInit).signal?.aborted,
    ).toBe(false);
    await vi.advanceTimersByTimeAsync(10_000);
    await result;
  } finally {
    vi.useRealTimers();
  }
});

it("pins publication and rejects an in-flight response after refresh", async () => {
  acceptGoldPublication(
    decodeGoldMetadata({
      contract_version: "2.0.0",
      status: "partial",
      period: null,
      temporal_scope: "snapshot",
      schema_version: "gold-csv-v2",
      fingerprint: "a".repeat(64),
      filters: {
        municipio: null,
        bairro: null,
        classe: null,
        alimentador: null,
      },
      source: {
        kind: "gold",
        version: "local-test",
        is_demo: false,
        updated_at: "2026-11-01T12:00:00Z",
      },
      limitations: [],
    }),
  );
  let finish!: (response: Response) => void;
  const fetchMock = vi.fn().mockReturnValue(
    new Promise<Response>((resolve) => {
      finish = resolve;
    }),
  );
  vi.stubGlobal("fetch", fetchMock);
  const pending = askAIQuestion({
    contract_version: "v1",
    question: "Qual a receita?",
    context: [],
  });
  expect(
    JSON.parse(fetchMock.mock.calls[0][1].body).expected_publication,
  ).toEqual({ lote: "local-test", fingerprint: "a".repeat(64) });
  resetGoldPublication();
  finish(Response.json(validResponse));
  await expect(pending).rejects.toMatchObject({
    status: 409,
    retryable: false,
  });
});

it("does not invalidate a newer publication when an older request returns 409", async () => {
  let finish!: (response: Response) => void;
  vi.stubGlobal(
    "fetch",
    vi.fn().mockReturnValue(
      new Promise<Response>((resolve) => {
        finish = resolve;
      }),
    ),
  );
  const pending = askAIQuestion({
    contract_version: "v1",
    question: "Qual a receita?",
    context: [],
  });
  resetGoldPublication();
  finish(Response.json({}, { status: 409 }));
  await expect(pending).rejects.toMatchObject({
    code: "superseded_request",
    retryable: false,
  });
  expect(isGoldPublicationStale()).toBe(false);
});
