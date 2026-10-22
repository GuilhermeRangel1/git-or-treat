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
});

it("mantém a estrutura e o tema ao navegar e consulta dados nas jornadas implementadas", async () => {
  const fetchSpy = vi
    .fn()
    .mockResolvedValue(new Response(JSON.stringify({}), { status: 503 }));
  vi.stubGlobal("fetch", fetchSpy);
  const user = userEvent.setup();
  render(
    <AppProviders>
      <MemoryRouter initialEntries={["/panorama"]}>
        <AppRoutes />
      </MemoryRouter>
    </AppProviders>,
  );
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
      screen.getByRole("heading", {
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
      await waitFor(() => expect(fetchSpy).toHaveBeenCalledTimes(1));
      expect(String(fetchSpy.mock.calls[0][0])).toContain("/api/v1/revenue?");
    }
    if (name === "Inspeções") {
      await waitFor(() => expect(fetchSpy).toHaveBeenCalledTimes(2));
      expect(String(fetchSpy.mock.calls[1][0])).toContain(
        "/api/v1/inspections/queue?",
      );
    }
  }
  expect(document.documentElement).toHaveAttribute("data-theme", "dark");
  expect(fetchSpy).toHaveBeenCalledTimes(2);
  expect(screen.queryByText("FastAPI Online")).not.toBeInTheDocument();
});

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
  await userEvent.click(
    screen.getByRole("button", { name: "Alternar para tema escuro" }),
  );
  expect(document.documentElement).toHaveAttribute("data-theme", "dark");
});

it("mantém o redirecionamento inicial e trata caminhos desconhecidos", () => {
  render(
    <AppProviders>
      <MemoryRouter initialEntries={["/inexistente"]}>
        <AppRoutes />
      </MemoryRouter>
    </AppProviders>,
  );
  expect(
    screen.getByRole("heading", {
      level: 1,
      name: "Sua rede, em perspectiva.",
    }),
  ).toBeVisible();
});
