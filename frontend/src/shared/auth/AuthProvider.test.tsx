import {
  QueryClient,
  QueryClientProvider,
  useQueryClient,
} from "@tanstack/react-query";
import { act, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { AuthProvider } from "./AuthProvider";
import RequireSession from "./RequireSession";
import {
  advanceAuthorizationGeneration,
  setSessionConfigured,
} from "./authorization";
import { useSession } from "./useSession";
import { apiClient } from "@/shared/api/client";

const account = {
  enabled: true,
  user: { id: "user-a", username: "reader", permissions: ["orders:read"] },
  expires_at: "2026-10-29T15:00:00Z",
};
const accountB = {
  enabled: true,
  user: {
    id: "user-b",
    username: "operator",
    permissions: ["orders:read", "orders:write"],
  },
  expires_at: "2026-10-29T15:00:00Z",
};
const anonymous = { enabled: true, user: null, expires_at: null };
const fetchMock = vi.fn<typeof fetch>();

function Probe() {
  const session = useSession();
  const queryClient = useQueryClient();
  return (
    <div>
      <span>{session.user?.id ?? "signed-out"}</span>
      <span>{session.needsReauthentication ? "reauth" : "ready"}</span>
      <button
        onClick={() => void session.login("sample-user", "sample-password")}
      >
        login
      </button>
      <button onClick={() => void session.logout()}>logout</button>
      <button onClick={() => void session.reloadSession()}>reload</button>
      <button
        onClick={() =>
          void apiClient("/api/v1/inspections/orders/search").catch(() => {})
        }
      >
        Protected action
      </button>
      <button
        onClick={() =>
          queryClient.setQueryData(["private", "orders"], "cached")
        }
      >
        seed-cache
      </button>
    </div>
  );
}

function mount(
  client = new QueryClient({ defaultOptions: { queries: { retry: false } } }),
) {
  render(
    <QueryClientProvider client={client}>
      <AuthProvider>
        <Probe />
      </AuthProvider>
    </QueryClientProvider>,
  );
  return client;
}

function ProtectedContent() {
  return (
    <button
      onClick={() =>
        void apiClient("/api/v1/inspections/orders/search").catch(() => {})
      }
    >
      Protected action
    </button>
  );
}

function mountGuarded() {
  render(
    <QueryClientProvider
      client={
        new QueryClient({ defaultOptions: { queries: { retry: false } } })
      }
    >
      <MemoryRouter>
        <AuthProvider>
          <RequireSession>
            <ProtectedContent />
          </RequireSession>
        </AuthProvider>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  fetchMock.mockReset();
  vi.stubGlobal("fetch", fetchMock);
  setSessionConfigured(false);
  advanceAuthorizationGeneration();
});

describe("sessão por cookie", () => {
  it("restaura a sessão pelo envelope e envia consultas com credentials include sem Bearer", async () => {
    fetchMock
      .mockResolvedValueOnce(Response.json(account))
      .mockResolvedValueOnce(Response.json({ ok: true }));
    mount();
    expect(await screen.findByText("user-a")).toBeVisible();
    await userEvent.click(
      screen.getByRole("button", { name: "Protected action" }),
    );
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2));
    expect(fetchMock.mock.calls[0][0]).toContain("/api/v1/auth/session");
    for (const [, request] of fetchMock.mock.calls) {
      expect(request?.credentials).toBe("include");
      expect(new Headers(request?.headers).has("Authorization")).toBe(false);
    }
  });

  it("envia usuário e senha ao login, revoga no logout e limpa cache", async () => {
    fetchMock
      .mockResolvedValueOnce(Response.json(anonymous))
      .mockResolvedValueOnce(Response.json(account))
      .mockResolvedValueOnce(new Response(null, { status: 204 }));
    const client = mount();
    await screen.findByText("signed-out");
    await userEvent.click(screen.getByRole("button", { name: "login" }));
    expect(await screen.findByText("user-a")).toBeVisible();
    const loginRequest = fetchMock.mock.calls[1]?.[1];
    expect(loginRequest?.method).toBe("POST");
    expect(JSON.parse(String(loginRequest?.body))).toEqual({
      username: "sample-user",
      password: "sample-password",
    });
    await userEvent.click(screen.getByRole("button", { name: "seed-cache" }));
    await waitFor(() =>
      expect(client.getQueryData(["private", "orders"])).toBe("cached"),
    );
    await userEvent.click(screen.getByRole("button", { name: "logout" }));
    await screen.findByText("signed-out");
    expect(fetchMock.mock.calls[2]?.[0]).toContain("/api/v1/auth/logout");
    expect(fetchMock.mock.calls[2]?.[1]?.method).toBe("POST");
    expect(client.getQueryData(["private", "orders"])).toBeUndefined();
  });

  it("limpa cache ao mudar identidade", async () => {
    fetchMock
      .mockResolvedValueOnce(Response.json(account))
      .mockResolvedValueOnce(Response.json(accountB));
    const client = mount();
    await screen.findByText("user-a");
    await userEvent.click(screen.getByRole("button", { name: "seed-cache" }));
    await waitFor(() =>
      expect(client.getQueryData(["private", "orders"])).toBe("cached"),
    );
    await userEvent.click(screen.getByRole("button", { name: "reload" }));
    expect(await screen.findByText("user-b")).toBeVisible();
    expect(client.getQueryData(["private", "orders"])).toBeUndefined();
  });

  it("ignora uma leitura de sessão atrasada após login", async () => {
    let resolveRestore!: (response: Response) => void;
    fetchMock.mockImplementationOnce(
      () =>
        new Promise((resolve) => {
          resolveRestore = resolve;
        }),
    );
    fetchMock.mockResolvedValueOnce(Response.json(accountB));
    const second = mount();
    await userEvent.click(screen.getByRole("button", { name: "login" }));
    expect(await screen.findByText("user-b")).toBeVisible();
    await act(async () => resolveRestore(Response.json(account)));
    expect(screen.getByText("user-b")).toBeVisible();
    second.clear();
  });

  it("oculta o conteúdo protegido em 401 e volta após sessão confirmada", async () => {
    fetchMock
      .mockResolvedValueOnce(Response.json(account))
      .mockResolvedValueOnce(new Response("{}", { status: 401 }))
      .mockResolvedValueOnce(Response.json(account));
    mountGuarded();
    await userEvent.click(
      await screen.findByRole("button", { name: "Protected action" }),
    );
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "A API recusou a sessão",
    );
    expect(
      screen.queryByRole("button", { name: "Protected action" }),
    ).toBeNull();
    await userEvent.click(
      screen.getByRole("button", { name: "Verificar sessão" }),
    );
    expect(
      await screen.findByRole("button", { name: "Protected action" }),
    ).toBeVisible();
  });

  it("bloqueia o portal se não consegue confirmar a sessão inicial", async () => {
    fetchMock.mockRejectedValueOnce(new TypeError("offline"));
    mountGuarded();
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Não foi possível conectar ao serviço de acesso.",
    );
    expect(
      screen.queryByRole("button", { name: "Protected action" }),
    ).toBeNull();
    expect(fetchMock).toHaveBeenCalledOnce();
  });
});
