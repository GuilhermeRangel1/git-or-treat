import { beforeEach, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import {
  clearReauthenticationRequired,
  setSessionConfigured,
} from "@/shared/auth/authorization";
import AppProviders from "./providers";
import { AppRoutes } from "./router";

beforeEach(() => {
  setSessionConfigured(false);
  clearReauthenticationRequired();
  localStorage.clear();
  vi.stubGlobal(
    "matchMedia",
    vi.fn().mockReturnValue({
      matches: false,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
    }),
  );
  vi.stubGlobal("fetch", async (input: RequestInfo | URL) => {
    if (String(input).includes("/api/v1/auth/session")) {
      return Response.json({ enabled: false, user: null, expires_at: null });
    }
    throw new Error("network offline");
  });
});

it("mantém a estrutura e o tema ao navegar e consulta dados nas jornadas implementadas", async () => {
  const fetchSpy = vi.fn(async (input: RequestInfo | URL) => {
    if (String(input).includes("/api/v1/auth/session")) {
      return Response.json({ enabled: false, user: null, expires_at: null });
    }
    throw new Error("network offline");
  });
  vi.stubGlobal("fetch", fetchSpy);
  const user = userEvent.setup();
  render(
    <AppProviders>
      <MemoryRouter initialEntries={["/panorama"]}>
        <AppRoutes />
      </MemoryRouter>
    </AppProviders>,
  );
  await screen.findByRole("heading", {
    level: 1,
    name: "Sua rede, em perspectiva.",
  });
  const sidebar = screen.getByLabelText("Menu lateral principal");
  await user.click(
    screen.getByRole("button", { name: "Alternar para tema escuro" }),
  );
  for (const [name, title] of [
    ["Receita", "Entenda a receita."],
    ["UC 360", "Cada unidade tem uma história."],
    ["Inspeções", "Priorize a próxima inspeção."],
    ["Ordens", "Acompanhe o trabalho de campo."],
    ["Operação", "Continuidade, onde importa."],
    ["Assistente", "O que você quer investigar?"],
    ["Panorama", "Sua rede, em perspectiva."],
  ]) {
    await user.click(screen.getByRole("link", { name }));
    expect(
      await screen.findByRole("heading", {
        level: 1,
        name: title,
      }),
    ).toBeVisible();
    expect(screen.getByLabelText("Menu lateral principal")).toBe(sidebar);
    expect(screen.getByRole("link", { name })).toHaveAttribute(
      "aria-current",
      "page",
    );
    if (name === "Receita") {
      await waitFor(() =>
        expect(
          fetchSpy.mock.calls.filter((call) =>
            String(call[0]).includes("/api/v1/revenue?"),
          ),
        ).toHaveLength(1),
      );
    }
    if (name === "Inspeções") {
      await waitFor(() =>
        expect(
          fetchSpy.mock.calls.some((call) =>
            String(call[0]).includes("/api/v1/inspections/queue?"),
          ),
        ).toBe(true),
      );
    }
    if (name === "Operação") {
      await waitFor(() => {
        const paths = fetchSpy.mock.calls.map(
          (call) => new URL(String(call[0]), window.location.origin).pathname,
        );
        expect(paths).toContain("/api/v1/operations/options");
        // Sem descoberta da fonte, não consultar uma janela demonstrativa como fallback.
        expect(paths).not.toContain("/api/v1/operations/summary");
        expect(paths).not.toContain("/api/v1/operations/ranking");
      });
    }
  }
  expect(document.documentElement).toHaveAttribute("data-theme", "dark");
  // As jornadas de dados consultam APIs; o chat só envia após ação da pessoa.
  await waitFor(() =>
    expect(
      fetchSpy.mock.calls.some((call) =>
        String(call[0]).includes("/api/v1/panorama?"),
      ),
    ).toBe(true),
  );
  for (const call of fetchSpy.mock.calls) {
    const path = new URL(String(call[0]), window.location.origin).pathname;
    expect([
      "/api/v1/panorama",
      "/api/v1/auth/session",
      "/api/v1/revenue",
      "/api/v1/inspections/queue",
      "/api/v1/inspections/orders/search",
      "/api/v1/operations/summary",
      "/api/v1/operations/ranking",
      "/api/v1/operations/options",
    ]).toContain(path);
  }
  expect(screen.queryByText("FastAPI Online")).not.toBeInTheDocument();
}, 15000);

it("inicia e permite alternar o tema quando o armazenamento está indisponível", async () => {
  vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => {
    throw new Error("storage unavailable");
  });
  vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
    throw new Error("storage unavailable");
  });
  render(
    <AppProviders>
      <MemoryRouter initialEntries={["/panorama"]}>
        <AppRoutes />
      </MemoryRouter>
    </AppProviders>,
  );
  await screen.findByRole("heading", {
    level: 1,
    name: "Sua rede, em perspectiva.",
  });
  await userEvent.click(
    screen.getByRole("button", { name: "Alternar para tema escuro" }),
  );
  expect(document.documentElement).toHaveAttribute("data-theme", "dark");
}, 10000);

it("mantém o redirecionamento inicial e trata caminhos desconhecidos", async () => {
  render(
    <AppProviders>
      <MemoryRouter initialEntries={["/inexistente"]}>
        <AppRoutes />
      </MemoryRouter>
    </AppProviders>,
  );
  expect(
    await screen.findByRole("heading", {
      level: 1,
      name: "Sua rede, em perspectiva.",
    }),
  ).toBeVisible();
});

function renderForProfile(
  initialEntry: string,
  profile: string | null,
  permissions: string[],
) {
  const fetchSpy = vi.fn(async (input: RequestInfo | URL) => {
    if (String(input).includes("/api/v1/auth/session")) {
      return Response.json({
        enabled: true,
        user: { id: "profile-user", username: "perfil", profile, permissions },
        expires_at: "2099-10-29T15:00:00Z",
      });
    }
    return Response.json({ detail: "forbidden" }, { status: 403 });
  });
  vi.stubGlobal("fetch", fetchSpy);
  render(
    <AppProviders>
      <MemoryRouter initialEntries={[initialEntry]}>
        <AppRoutes />
      </MemoryRouter>
    </AppProviders>,
  );
  return fetchSpy;
}

it("uses the Atendimento entry and filters navigation by profile", async () => {
  renderForProfile("/", "customer_service", ["ucs:read", "ai:ask"]);
  expect(
    await screen.findByRole("heading", {
      name: "Cada unidade tem uma história.",
    }),
  ).toBeVisible();
  expect(screen.getByRole("link", { name: "UC 360" })).toBeVisible();
  expect(screen.getByRole("link", { name: "Assistente" })).toBeVisible();
  expect(screen.queryByRole("link", { name: "Panorama" })).toBeNull();
  expect(screen.queryByRole("link", { name: "Inspeções" })).toBeNull();
});

it("denies a forbidden URL before mounting its page query", async () => {
  const fetchSpy = renderForProfile("/panorama", "customer_service", [
    "ucs:read",
    "ai:ask",
  ]);
  expect(await screen.findByRole("alert")).toHaveTextContent(
    "Você não tem acesso a esta área",
  );
  expect(
    fetchSpy.mock.calls.some((call) =>
      String(call[0]).includes("/api/v1/panorama"),
    ),
  ).toBe(false);
});

it("protects UC detail without starting UC 360 queries", async () => {
  const fetchSpy = renderForProfile("/uc-360/UC-1001", "commercial", [
    "panorama:read",
    "revenue:read",
    "ai:ask",
  ]);
  expect(await screen.findByRole("alert")).toHaveTextContent(
    "Você não tem acesso a esta área",
  );
  expect(
    fetchSpy.mock.calls.some((call) => String(call[0]).includes("/api/v1/ucs")),
  ).toBe(false);
});

it("hides cross-links that the current profile cannot open", async () => {
  renderForProfile("/panorama", "commercial", [
    "panorama:read",
    "revenue:read",
    "ai:ask",
  ]);
  await screen.findByRole("heading", {
    level: 1,
    name: "Sua rede, em perspectiva.",
  });
  expect(screen.getByRole("link", { name: "Receita" })).toBeVisible();
  expect(screen.getByRole("link", { name: "Assistente" })).toBeVisible();
  expect(screen.queryByRole("link", { name: "OperaÃ§Ã£o" })).toBeNull();
  expect(screen.queryByRole("link", { name: "Abrir operaÃ§Ã£o" })).toBeNull();
});

it("reserva o diagnostico de contratos para admin com sessao configurada", async () => {
  const fetchSpy = renderForProfile("/dev/contratos", "commercial", [
    "panorama:read",
    "revenue:read",
    "ai:ask",
  ]);
  expect(await screen.findByRole("alert")).toHaveTextContent(
    "Você não tem acesso a esta área",
  );
  expect(fetchSpy).toHaveBeenCalledOnce();
});
