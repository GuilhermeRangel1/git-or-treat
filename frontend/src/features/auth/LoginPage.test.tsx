import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { AuthProvider } from "@/shared/auth/AuthProvider";
import { ThemeProvider } from "@/shared/theme/ThemeProvider";
import LoginPage from "./LoginPage";

vi.mock("./EnergyArtwork", () => ({
  default: () => <canvas aria-hidden="true" />,
}));

const fetchMock = vi.fn<typeof fetch>();
const anonymous = { enabled: true, user: null, expires_at: null };
const account = {
  enabled: true,
  user: {
    id: "user-1",
    username: "reader",
    profile: "commercial",
    permissions: ["panorama:read", "revenue:read", "ai:ask"],
  },
  expires_at: "2099-10-29T15:00:00Z",
};
const customerServiceAccount = {
  enabled: true,
  user: {
    id: "user-cs",
    username: "atendimento",
    profile: "customer_service",
    permissions: ["ucs:read", "ai:ask"],
  },
  expires_at: "2099-10-29T15:00:00Z",
};

function renderLogin() {
  render(
    <QueryClientProvider client={new QueryClient()}>
      <ThemeProvider>
        <AuthProvider>
          <MemoryRouter initialEntries={["/login"]}>
            <Routes>
              <Route path="/login" element={<LoginPage />} />
              <Route path="/panorama" element={<h1>Panorama autenticado</h1>} />
              <Route path="/uc-360" element={<h1>Entrada de Atendimento</h1>} />
            </Routes>
          </MemoryRouter>
        </AuthProvider>
      </ThemeProvider>
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  fetchMock.mockReset();
  vi.stubGlobal("fetch", fetchMock);
  localStorage.clear();
});

describe("página de entrada", () => {
  it("mantém formulário disponível enquanto a sessão anterior ainda está sendo verificada", async () => {
    let resolveRestore!: (response: Response) => void;
    fetchMock.mockImplementationOnce(
      () =>
        new Promise((resolve) => {
          resolveRestore = resolve;
        }),
    );
    fetchMock.mockResolvedValueOnce(Response.json(account));
    renderLogin();
    const username = screen.getByLabelText("Usuário");
    await userEvent.type(username, "reader");
    await userEvent.type(screen.getByLabelText("Senha"), "secret");
    await userEvent.click(screen.getByRole("button", { name: "Entrar" }));
    expect(
      await screen.findByRole("heading", { name: "Panorama autenticado" }),
    ).toBeVisible();
    await act(async () => resolveRestore(Response.json(anonymous)));
    expect(
      screen.getByRole("heading", { name: "Panorama autenticado" }),
    ).toBeVisible();
  });

  it("aceita usuário, alterna a senha e navega apenas após confirmação do backend", async () => {
    fetchMock
      .mockResolvedValueOnce(Response.json(anonymous))
      .mockResolvedValueOnce(Response.json(account));
    renderLogin();
    const username = await screen.findByLabelText("Usuário");
    const currentTheme = document.documentElement.dataset.theme;
    const themeToggle = screen.getByRole("button", {
      name: /Ativar tema (claro|escuro)/,
    });
    await userEvent.click(themeToggle);
    expect(document.documentElement.dataset.theme).not.toBe(currentTheme);
    const password = screen.getByLabelText("Senha");
    expect(username).toHaveAttribute("type", "text");
    await userEvent.type(username, "  pessoa-01  ");
    await userEvent.type(password, "segredo");
    await userEvent.click(
      screen.getByRole("button", { name: "Mostrar senha" }),
    );
    expect(password).toHaveAttribute("type", "text");
    await userEvent.click(screen.getByRole("button", { name: "Entrar" }));
    expect(
      await screen.findByRole("heading", { name: "Panorama autenticado" }),
    ).toBeVisible();
    const loginRequest = fetchMock.mock.calls[1]?.[1];
    expect(JSON.parse(String(loginRequest?.body))).toEqual({
      username: "pessoa-01",
      password: "segredo",
    });
    expect(loginRequest?.credentials).toBe("include");
  });

  it("mostra erro seguro e mantém os campos quando credenciais não são aceitas", async () => {
    fetchMock
      .mockResolvedValueOnce(Response.json(anonymous))
      .mockResolvedValueOnce(
        Response.json({ detail: "private auth internals" }, { status: 401 }),
      );
    renderLogin();
    await userEvent.type(await screen.findByLabelText("Usuário"), "reader");
    await userEvent.type(screen.getByLabelText("Senha"), "bad-password");
    await userEvent.click(screen.getByRole("button", { name: "Entrar" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Usuário ou senha incorretos. Confira os dados e tente novamente.",
    );
    expect(screen.getByLabelText("Usuário")).toHaveValue("reader");
    expect(screen.getByLabelText("Senha")).toHaveValue("bad-password");
    expect(screen.queryByText("private auth internals")).toBeNull();
  });

  it("encaminha perfil de atendimento para UC 360 depois do login", async () => {
    fetchMock
      .mockResolvedValueOnce(Response.json(anonymous))
      .mockResolvedValueOnce(Response.json(customerServiceAccount));
    renderLogin();
    await userEvent.type(
      await screen.findByLabelText("Usu\u00e1rio"),
      "atendimento",
    );
    await userEvent.type(screen.getByLabelText("Senha"), "segredo");
    await userEvent.click(screen.getByRole("button", { name: "Entrar" }));
    expect(
      await screen.findByRole("heading", { name: "Entrada de Atendimento" }),
    ).toBeVisible();
  });
});
