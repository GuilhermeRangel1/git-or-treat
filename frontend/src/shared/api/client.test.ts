// @vitest-environment node
import { beforeEach, describe, expect, it, vi } from "vitest";
import { apiClient, ApiError } from "./client";
import { resetGoldPublication } from "../analytics/goldPublication";
import {
  advanceAuthorizationGeneration,
  setAccessTokenProvider,
} from "../auth/authorization";

const fetchMock = vi.fn<typeof fetch>();

beforeEach(() => {
  setAccessTokenProvider(null);
  advanceAuthorizationGeneration();
  resetGoldPublication();
  fetchMock.mockReset();
  vi.stubGlobal("fetch", fetchMock);
  vi.stubEnv("VITE_API_URL", "http://localhost:8000");
});

describe("fronteira HTTP", () => {
  it("envia o token de acesso individual sem substituir headers da chamada", async () => {
    setAccessTokenProvider(async () => "user-access-token");
    fetchMock.mockResolvedValue(new Response("{}"));
    await apiClient("/api/v1/inspections/orders/search", {
      headers: { "X-Trace-Id": "request-1" },
    });
    const headers = new Headers(fetchMock.mock.calls[0][1]?.headers);
    expect(headers.get("Authorization")).toBe("Bearer user-access-token");
    expect(headers.get("X-Trace-Id")).toBe("request-1");
  });

  it("descarta uma resposta de ordens que chega depois da troca de identidade", async () => {
    let respond!: (value: Response) => void;
    setAccessTokenProvider(async () => "first-user-token");
    fetchMock.mockImplementation(
      () =>
        new Promise((resolve) => {
          respond = resolve;
        }),
    );
    const pending = apiClient("/api/v1/inspections/orders/search");
    await vi.waitFor(() => expect(fetchMock).toHaveBeenCalledOnce());
    advanceAuthorizationGeneration();
    respond(new Response(JSON.stringify({ items: [], pagination: {} })));
    await expect(pending).rejects.toMatchObject({ kind: "session-changed" });
  });

  it("envia guardas somente nas leituras analíticas e recusa publicação divergente", async () => {
    const metadata = {
      contract_version: "2.0.0",
      status: "partial",
      period: null,
      temporal_scope: "snapshot",
      schema_version: "gold-csv-v1",
      fingerprint: "a".repeat(64),
      filters: {
        municipio: null,
        bairro: null,
        classe: null,
        alimentador: null,
      },
      source: {
        kind: "gold",
        version: "artificial-batch",
        is_demo: false,
        updated_at: "2026-10-29T12:00:00Z",
      },
      limitations: [],
    };
    fetchMock.mockImplementation(
      async () => new Response(JSON.stringify({ data: {}, metadata })),
    );
    await apiClient("/api/v1/operations/options");
    await apiClient("/api/v1/inspections/queue?page=2");
    expect(String(fetchMock.mock.calls[1][0])).toContain(
      "expected_lote=artificial-batch",
    );
    expect(String(fetchMock.mock.calls[1][0])).toContain(
      "expected_fingerprint=" + "a".repeat(64),
    );
    await apiClient("/api/v1/inspections/orders/search");
    expect(String(fetchMock.mock.calls[2][0])).not.toContain("expected_lote");
    fetchMock.mockResolvedValue(
      new Response(
        JSON.stringify({
          data: {},
          metadata: { ...metadata, fingerprint: "b".repeat(64) },
        }),
      ),
    );
    await expect(apiClient("/api/v1/operations/options")).rejects.toMatchObject(
      { status: 409 },
    );
  });

  it("recusa resposta em trânsito de uma geração anterior após atualização coordenada", async () => {
    let respond!: (value: Response) => void;
    fetchMock.mockImplementation(
      () =>
        new Promise((resolve) => {
          respond = resolve;
        }),
    );
    const pending = apiClient("/api/v1/operations/options");
    await vi.waitFor(() => expect(fetchMock).toHaveBeenCalledOnce());
    resetGoldPublication();
    respond(
      new Response(
        JSON.stringify({
          data: {},
          metadata: {
            contract_version: "2.0.0",
            status: "empty",
            period: null,
            temporal_scope: "snapshot",
            schema_version: "gold-csv-v1",
            fingerprint: "a".repeat(64),
            filters: {
              municipio: null,
              bairro: null,
              classe: null,
              alimentador: null,
            },
            source: {
              kind: "gold",
              version: "artificial-batch",
              is_demo: false,
              updated_at: "2026-10-29T12:00:00Z",
            },
            limitations: [],
          },
        }),
      ),
    );
    await expect(pending).rejects.toMatchObject({ status: 409 });
  });

  it("preserva status e corpo de erro textual sem ler o corpo duas vezes", async () => {
    fetchMock.mockResolvedValue(
      new Response("Serviço indisponível", { status: 503 }),
    );
    await expect(apiClient("/example")).rejects.toMatchObject({
      status: 503,
      data: "Serviço indisponível",
    });
  });

  it("aceita uma resposta sem conteúdo", async () => {
    fetchMock.mockResolvedValue(new Response(null, { status: 204 }));
    await expect(apiClient<void>("/example")).resolves.toBeUndefined();
  });

  it("preserva a distinção entre JSON inválido e falha de rede", async () => {
    fetchMock.mockResolvedValue(new Response("invalid", { status: 200 }));
    await expect(apiClient("/example")).rejects.toMatchObject({
      status: 200,
      kind: "invalid-response",
    });
  });

  it("preserva o cancelamento original para a camada de consultas", async () => {
    const aborted = new DOMException("Cancelada", "AbortError");
    fetchMock.mockRejectedValue(aborted);
    await expect(apiClient("/example")).rejects.toBe(aborted);
  });

  it("aceita Headers e não força JSON em FormData", async () => {
    fetchMock.mockResolvedValue(new Response("{}"));
    const body = new FormData();
    body.set("example", "value");
    await apiClient("/example", {
      method: "POST",
      body,
      headers: new Headers({ "X-Example": "value" }),
    });
    const request = fetchMock.mock.calls[0]?.[1];
    const headers = new Headers(request?.headers);
    expect(headers.get("X-Example")).toBe("value");
    expect(headers.has("Content-Type")).toBe(false);
  });

  it("devolve JSON e distingue falha de transporte de erro HTTP", async () => {
    fetchMock.mockResolvedValueOnce(Response.json({ example: 1 }));
    await expect(apiClient("/example")).resolves.toEqual({ example: 1 });
    fetchMock.mockRejectedValueOnce(new TypeError("offline"));
    await expect(apiClient("/example")).rejects.toBeInstanceOf(ApiError);
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it("exige configuração explícita fora do desenvolvimento", async () => {
    vi.stubEnv("DEV", false);
    vi.stubEnv("VITE_API_URL", undefined);
    await expect(apiClient("/example")).rejects.toMatchObject({
      kind: "configuration",
    });
    expect(fetchMock).not.toHaveBeenCalled();
  });
});

it("usa a origem do portal no desenvolvimento para funcionar fora do localhost", async () => {
  vi.stubEnv("DEV", true);
  vi.stubEnv("VITE_API_URL", undefined);
  fetchMock.mockResolvedValueOnce(Response.json({ ok: true }));
  await expect(apiClient("/api/v1/panorama")).resolves.toEqual({ ok: true });
  expect(fetchMock.mock.calls[0]?.[0]).toBe("/api/v1/panorama");
});
