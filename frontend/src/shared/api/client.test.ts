// @vitest-environment node
import { beforeEach, describe, expect, it, vi } from "vitest";
import { apiClient, ApiError } from "./client";

const fetchMock = vi.fn<typeof fetch>();

beforeEach(() => {
  fetchMock.mockReset();
  vi.stubGlobal("fetch", fetchMock);
  vi.stubEnv("VITE_API_URL", "http://localhost:8000");
});

describe("fronteira HTTP", () => {
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
