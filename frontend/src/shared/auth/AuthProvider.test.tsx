import {
  useQueryClient,
  QueryClient,
  QueryClientProvider,
} from "@tanstack/react-query";
import { act, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { User } from "oidc-client-ts";
import { AuthProvider } from "./AuthProvider";
import { useOrderAccess, useSession } from "./useSession";
import { apiClient } from "@/shared/api/client";
import { getAccessToken } from "./authorization";
import RequireSession from "./RequireSession";

const oidc = vi.hoisted(() => {
  let loaded: ((user: User) => void) | undefined;
  let unloaded: (() => void) | undefined;
  let currentUser: User | null;
  return {
    setCurrent: (user: User | null) => {
      currentUser = user;
    },
    emitLoaded: (user: User) => loaded?.(user),
    emitUnloaded: () => unloaded?.(),
    manager: {
      events: {
        addUserLoaded: vi.fn((callback: (user: User) => void) => {
          loaded = callback;
        }),
        removeUserLoaded: vi.fn(),
        addUserUnloaded: vi.fn((callback: () => void) => {
          unloaded = callback;
        }),
        removeUserUnloaded: vi.fn(),
      },
      getUser: vi.fn(async () => currentUser),
      signinRedirect: vi.fn(async () => undefined),
      signinRedirectCallback: vi.fn(async () => currentUser),
      signinSilent: vi.fn(async () => currentUser),
      removeUser: vi.fn(async () => {
        currentUser = null;
      }),
      signoutRedirect: vi.fn(async () => undefined),
    },
    resetCallbacks: () => {
      loaded = undefined;
      unloaded = undefined;
    },
  };
});

vi.mock("./oidc", () => ({
  getOidcConfig: () => ({
    authority: "http://localhost:8082/realms/grid360",
    clientId: "grid360-web",
  }),
  createOidcUserManager: () => oidc.manager,
}));

function user(sub: string, accessToken: string): User {
  return {
    profile: { sub },
    access_token: accessToken,
    id_token: `id-${sub}`,
    token_type: "Bearer",
    expires_at: Math.floor(Date.now() / 1000) + 3600,
  } as User;
}

function Probe() {
  const session = useSession();
  const queries = useQueryClient();
  return (
    <div>
      <span>{session.user?.profile.sub ?? "signed-out"}</span>
      <span>{session.needsReauthentication ? "reauth" : "ready"}</span>
      <button onClick={() => void session.beginLogin()}>login</button>
      <button onClick={() => void session.beginLogout()}>logout</button>
      <button
        onClick={() => queries.setQueryData(["remote", "user"], "cached")}
      >
        seed-cache
      </button>
    </div>
  );
}

function mount(client = new QueryClient()) {
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
  const access = useOrderAccess();
  return (
    <section>
      <button>protected action</button>
      <span>{access.data?.permissions.join(", ") ?? "loading access"}</span>
    </section>
  );
}

function UnauthorizedTrigger() {
  return (
    <button
      onClick={() =>
        void apiClient("/api/v1/inspections/orders/search").catch(() => {})
      }
    >
      trigger protected 401
    </button>
  );
}

function mountProtected(
  client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  }),
) {
  render(
    <QueryClientProvider client={client}>
      <AuthProvider>
        <Probe />
        <RequireSession>
          <ProtectedContent />
        </RequireSession>
        <UnauthorizedTrigger />
      </AuthProvider>
    </QueryClientProvider>,
  );
  return client;
}

function accessResponse(permissions: string[]) {
  return Response.json({
    actor: "oidc:subject-a",
    auth_mode: "oidc",
    permissions,
  });
}

beforeEach(() => {
  oidc.setCurrent(user("subject-a", "token-a"));
  oidc.resetCallbacks();
  for (const method of Object.values(oidc.manager.events)) method.mockClear();
  for (const method of [
    oidc.manager.getUser,
    oidc.manager.signinRedirect,
    oidc.manager.signinRedirectCallback,
    oidc.manager.signinSilent,
    oidc.manager.removeUser,
    oidc.manager.signoutRedirect,
  ])
    method.mockClear();
});

describe("sessao OIDC", () => {
  it("dispara login e injeta token do usuario atual", async () => {
    const userEvents = userEvent.setup();
    mount();
    await screen.findByText("subject-a");
    await userEvents.click(screen.getByRole("button", { name: "login" }));
    expect(oidc.manager.signinRedirect).toHaveBeenCalledOnce();
    await expect(getAccessToken()).resolves.toBe("token-a");
  });

  it("nao usa token renovado para uma identidade diferente", async () => {
    const expired = {
      ...user("subject-a", "expired-token"),
      expires_at: Math.floor(Date.now() / 1000) - 1,
    } as User;
    oidc.setCurrent(expired);
    oidc.manager.signinSilent.mockResolvedValueOnce(
      user("subject-b", "token-b"),
    );
    mount();
    await screen.findByText("subject-a");

    await expect(getAccessToken()).resolves.toBeNull();
  });

  it("preserva cache na renovacao da mesma identidade e limpa ao trocar subject", async () => {
    const client = mount();
    await screen.findByText("subject-a");
    const generation = client.getQueryData(["remote", "user"]);
    await userEvent.click(screen.getByRole("button", { name: "seed-cache" }));
    await waitFor(() =>
      expect(client.getQueryData(["remote", "user"])).toBe("cached"),
    );
    await act(async () => {
      oidc.setCurrent(user("subject-a", "token-a-renewed"));
      oidc.emitLoaded(user("subject-a", "token-a-renewed"));
    });
    expect(client.getQueryData(["remote", "user"])).toBe("cached");
    await expect(getAccessToken()).resolves.toBe("token-a-renewed");
    await act(async () => {
      oidc.setCurrent(user("subject-b", "token-b"));
      oidc.emitLoaded(user("subject-b", "token-b"));
    });
    await screen.findByText("subject-b");
    expect(client.getQueryData(["remote", "user"])).toBeUndefined();
    expect(generation).toBeUndefined();
  });

  it("remove credencial e cache antes de iniciar logout", async () => {
    const client = mount();
    await screen.findByText("subject-a");
    await userEvent.click(screen.getByRole("button", { name: "seed-cache" }));
    await waitFor(() =>
      expect(client.getQueryData(["remote", "user"])).toBe("cached"),
    );
    await userEvent.click(screen.getByRole("button", { name: "logout" }));
    await waitFor(() =>
      expect(oidc.manager.signoutRedirect).toHaveBeenCalledOnce(),
    );
    await expect(getAccessToken()).resolves.toBeNull();
    expect(client.getQueryData(["remote", "user"])).toBeUndefined();
  });

  it("esconde e inativa o portal após 401 e refaz permissões ao renovar a mesma identidade", async () => {
    const fetchMock = vi
      .fn<typeof fetch>()
      .mockResolvedValueOnce(accessResponse(["orders:read"]))
      .mockResolvedValueOnce(
        Response.json({ detail: "unauthorized" }, { status: 401 }),
      )
      .mockResolvedValueOnce(accessResponse(["orders:read", "orders:write"]));
    vi.stubGlobal("fetch", fetchMock);
    const client = mountProtected();

    await screen.findByText("orders:read");
    expect(fetchMock).toHaveBeenCalledOnce();
    const protectedButton = screen.getByRole("button", {
      name: "protected action",
    });

    await userEvent.click(
      screen.getByRole("button", { name: "trigger protected 401" }),
    );
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "A API recusou a sessão.",
    );
    expect(
      screen.queryByRole("button", { name: "protected action" }),
    ).toBeNull();
    expect(protectedButton.closest("[hidden]")).toHaveAttribute("inert");

    oidc.setCurrent(user("subject-a", "token-a-renewed"));
    await userEvent.click(
      screen.getByRole("button", { name: "Renovar sessão" }),
    );

    await screen.findByText("orders:read, orders:write");
    expect(fetchMock).toHaveBeenCalledTimes(3);
    expect(screen.getByRole("button", { name: "protected action" })).toBe(
      protectedButton,
    );
    expect(
      screen.getByRole("button", { name: "protected action" }),
    ).toBeVisible();
    await expect(getAccessToken()).resolves.toBe("token-a-renewed");
    expect(client.getQueryData(["order-access", "subject-a"])).toMatchObject({
      permissions: ["orders:read", "orders:write"],
      canWrite: true,
    });
  });
});
