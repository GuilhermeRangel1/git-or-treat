import { StrictMode } from "react";
import { act, render, screen } from "@testing-library/react";
import { MemoryRouter, useLocation } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import OidcCallback from "./OidcCallback";

const auth = vi.hoisted(() => ({
  finishLogin: vi.fn<() => Promise<void>>(),
}));

vi.mock("./useSession", () => ({
  useSession: () => ({ finishLogin: auth.finishLogin }),
}));

function CurrentPath() {
  return <output data-testid="current-path">{useLocation().pathname}</output>;
}

function deferred<T>() {
  let resolve!: (value: T | PromiseLike<T>) => void;
  let reject!: (reason?: unknown) => void;
  const promise = new Promise<T>((resolvePromise, rejectPromise) => {
    resolve = resolvePromise;
    reject = rejectPromise;
  });
  return { promise, resolve, reject };
}

function renderCallback() {
  return render(
    <StrictMode>
      <MemoryRouter initialEntries={["/auth/callback"]}>
        <OidcCallback />
        <CurrentPath />
      </MemoryRouter>
    </StrictMode>,
  );
}

describe("retorno OIDC", () => {
  beforeEach(() => {
    auth.finishLogin.mockReset();
  });

  it("troca o código uma vez sob StrictMode e navega após autenticar", async () => {
    const callback = deferred<void>();
    auth.finishLogin.mockReturnValue(callback.promise);
    renderCallback();

    expect(auth.finishLogin).toHaveBeenCalledOnce();
    expect(screen.getByText("Concluindo autenticação…")).toBeVisible();
    expect(screen.getByTestId("current-path")).toHaveTextContent(
      "/auth/callback",
    );

    await act(async () => callback.resolve());

    expect(screen.getByTestId("current-path")).toHaveTextContent("/panorama");
  });

  it("mostra erro seguro e mantém a rota quando a troca do código falha", async () => {
    auth.finishLogin.mockRejectedValue(new Error("private provider details"));
    renderCallback();

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Não foi possível concluir a autenticação. Tente entrar novamente.",
    );
    expect(screen.getByTestId("current-path")).toHaveTextContent(
      "/auth/callback",
    );
    expect(
      screen.queryByText("private provider details"),
    ).not.toBeInTheDocument();
  });
});
