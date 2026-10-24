import { beforeEach, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import AppProviders from "./providers";
import { AppRoutes } from "./router";

beforeEach(() => {
  localStorage.clear();
  vi.stubGlobal(
    "matchMedia",
    vi.fn().mockReturnValue({
      matches: false,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
    }),
  );
  vi.stubGlobal(
    "fetch",
    vi.fn().mockRejectedValue(new Error("network offline")),
  );
});

it("mantém a estrutura e o tema ao navegar e consulta dados nas jornadas implementadas", async () => {
  const fetchSpy = vi.fn().mockRejectedValue(new Error("network offline"));
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
      "/api/v1/revenue",
      "/api/v1/inspections/queue",
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
