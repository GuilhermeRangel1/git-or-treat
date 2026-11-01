import { beforeEach, describe, expect, it, vi } from "vitest";
import {
  getSession,
  loginSession,
  logoutSession,
  SessionApiError,
} from "./session-api";

const fetchMock = vi.fn<typeof fetch>();

beforeEach(() => {
  fetchMock.mockReset();
  vi.stubGlobal("fetch", fetchMock);
  vi.stubEnv("VITE_API_URL", undefined);
  vi.stubEnv("DEV", true);
});

describe("transporte de sessão", () => {
  it("restaura a sessão sem cache e inclui o cookie", async () => {
    const envelope = {
      enabled: true,
      user: {
        id: "usr-1",
        username: "operador",
        profile: "losses",
        permissions: [
          "inspections:read",
          "orders:read",
          "orders:write",
          "ai:ask",
        ],
      },
      expires_at: "2099-10-29T15:00:00Z",
    };
    fetchMock.mockResolvedValueOnce(Response.json(envelope));
    await expect(getSession()).resolves.toEqual(envelope);
    const [url, request] = fetchMock.mock.calls[0];
    expect(url).toBe("/api/v1/auth/session");
    expect(request?.method).toBe("GET");
    expect(request?.credentials).toBe("include");
    expect(request?.cache).toBe("no-store");
  });

  it("aceita login apenas quando o envelope confirma usuário e sessão", async () => {
    fetchMock.mockResolvedValueOnce(
      Response.json({
        enabled: true,
        user: {
          id: "usr-1",
          username: "pessoa",
          profile: "losses",
          permissions: [
            "inspections:read",
            "orders:read",
            "orders:write",
            "ai:ask",
          ],
        },
        expires_at: "2099-10-29T15:00:00-03:00",
      }),
    );
    const result = await loginSession("pessoa", "senha");
    expect(result.user?.permissions).toEqual([
      "inspections:read",
      "orders:read",
      "orders:write",
      "ai:ask",
    ]);
    const request = fetchMock.mock.calls[0]?.[1];
    expect(request?.method).toBe("POST");
    expect(JSON.parse(String(request?.body))).toEqual({
      username: "pessoa",
      password: "senha",
    });
    expect(request?.credentials).toBe("include");
  });

  it("rejeita datas inválidas e sessões expiradas", async () => {
    for (const expires_at of [
      "amanhã",
      "2099-13-29T15:00:00-03:00",
      "2099-02-30T15:00:00-03:00",
      "2000-01-01T00:00:00Z",
    ]) {
      fetchMock.mockResolvedValueOnce(
        Response.json({
          enabled: true,
          user: { id: "usr-1", username: "pessoa", permissions: [] },
          expires_at,
        }),
      );
      await expect(getSession()).rejects.toBeInstanceOf(SessionApiError);
    }
  });

  it("não inclui segredos do backend nas mensagens e valida coerência do envelope", async () => {
    fetchMock.mockResolvedValueOnce(
      Response.json({ detail: "password hash internals" }, { status: 401 }),
    );
    await expect(loginSession("pessoa", "senha")).rejects.toMatchObject({
      message:
        "Usuário ou senha incorretos. Confira os dados e tente novamente.",
      status: 401,
    });
    fetchMock.mockResolvedValueOnce(
      Response.json({
        enabled: true,
        user: null,
        expires_at: "2099-10-29T15:00:00Z",
      }),
    );
    await expect(getSession()).rejects.toBeInstanceOf(SessionApiError);
    fetchMock.mockResolvedValueOnce(
      Response.json({
        enabled: false,
        user: { id: "usr-1", username: "pessoa", permissions: [] },
        expires_at: "2099-10-29T15:00:00Z",
      }),
    );
    await expect(getSession()).rejects.toBeInstanceOf(SessionApiError);
  });

  it("exige 204 no logout e não envia dados no corpo", async () => {
    fetchMock.mockResolvedValueOnce(new Response(null, { status: 204 }));
    await expect(logoutSession()).resolves.toBeUndefined();
    const [url, request] = fetchMock.mock.calls[0];
    expect(url).toBe("/api/v1/auth/logout");
    expect(request?.method).toBe("POST");
    expect(request?.body).toBeUndefined();
    expect(request?.credentials).toBe("include");
  });

  it("exige perfil conhecido e uma matriz de permissoes coerente", async () => {
    const base = {
      enabled: true,
      expires_at: "2099-10-29T15:00:00Z",
    };
    for (const user of [
      { id: "usr-1", username: "pessoa", permissions: [] },
      {
        id: "usr-1",
        username: "pessoa",
        profile: "unknown",
        permissions: [],
      },
      {
        id: "usr-1",
        username: "pessoa",
        profile: "commercial",
        permissions: ["ucs:read"],
      },
      {
        id: "usr-1",
        username: "pessoa",
        profile: null,
        permissions: ["panorama:read"],
      },
    ]) {
      fetchMock.mockResolvedValueOnce(Response.json({ ...base, user }));
      await expect(getSession()).rejects.toBeInstanceOf(SessionApiError);
    }
    fetchMock.mockResolvedValueOnce(
      Response.json({
        ...base,
        user: {
          id: "usr-1",
          username: "pessoa",
          profile: "operations",
          permissions: ["operations:read", "ai:ask"],
        },
      }),
    );
    await expect(getSession()).resolves.toMatchObject({
      user: {
        profile: "operations",
        permissions: ["operations:read", "ai:ask"],
      },
    });
    fetchMock.mockResolvedValueOnce(
      Response.json({
        ...base,
        user: {
          id: "usr-unprovisioned",
          username: "sem-perfil",
          profile: null,
          permissions: [],
        },
      }),
    );
    await expect(getSession()).resolves.toMatchObject({
      user: { profile: null, permissions: [] },
    });
  });
});
