import { beforeEach, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
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

it("mantém a estrutura e o tema ao navegar entre as sete áreas, sem consultar dados", async () => {
  const fetchSpy = vi.fn();
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
  }
  expect(document.documentElement).toHaveAttribute("data-theme", "dark");
  expect(fetchSpy).not.toHaveBeenCalled();
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
