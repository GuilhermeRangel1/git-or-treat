import { beforeEach, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import TestProviders from "../../shared/test/TestProviders";
import PanoramaPage from "./PanoramaPage";

beforeEach(() => {
  localStorage.clear();
});

it("exibe o conteúdo hostil do filtro como texto, sem criar elementos ou executar scripts", async () => {
  const attack = "<img src=x onerror=alert(1)>";
  const alert = vi.spyOn(window, "alert").mockImplementation(() => {});
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue(new Response("{}", { status: 422 })),
  );
  render(
    <TestProviders>
      <MemoryRouter
        initialEntries={["/panorama?municipio=" + encodeURIComponent(attack)]}
      >
        <PanoramaPage />
      </MemoryRouter>
    </TestProviders>,
  );
  expect(
    await screen.findByText("Erro na consulta dos indicadores"),
  ).toBeVisible();
  expect(screen.getByText(attack, { exact: true })).toBeVisible();
  expect(document.querySelector('img[src="x"]')).toBeNull();
  expect(alert).not.toHaveBeenCalled();
});

it("mantém os filtros e a tentativa de recuperação quando a API devolve HTTP 500", async () => {
  vi.stubGlobal(
    "fetch",
    vi
      .fn()
      .mockResolvedValue(
        new Response("Internal Server Error", { status: 500 }),
      ),
  );
  render(
    <TestProviders>
      <MemoryRouter initialEntries={["/panorama"]}>
        <PanoramaPage />
      </MemoryRouter>
    </TestProviders>,
  );
  expect(
    await screen.findByText("Erro na consulta dos indicadores"),
  ).toBeVisible();
  expect(screen.getByLabelText("Município")).toBeEnabled();
  expect(
    screen.getByRole("button", { name: "Tentar novamente" }),
  ).toBeEnabled();
  expect(
    screen.queryByRole("region", {
      name: "Indicadores principais do Panorama",
    }),
  ).not.toBeInTheDocument();
});
