import { it, expect, vi, afterEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import FieldFiles from "./FieldFiles";

afterEach(() => vi.unstubAllGlobals());

it("restringe bairros ao município e limpa o bairro ao trocar de cidade", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(
      async (url: string) =>
        new Response(
          JSON.stringify(
            url.includes("options_only")
              ? {
                  options: {
                    municipio: ["Recife", "Olinda"],
                    bairro: ["Boa Vista", "Carmo"],
                  },
                  neighborhoods: [
                    { municipio: "Recife", bairro: "Boa Vista" },
                    { municipio: "Olinda", bairro: "Carmo" },
                  ],
                }
              : { count: 2 },
          ),
          { status: 200 },
        ),
    ),
  );
  render(
    <QueryClientProvider client={new QueryClient()}>
      <FieldFiles request="" />
    </QueryClientProvider>,
  );
  const user = userEvent.setup();
  await user.click(screen.getByRole("button", { name: "Exportar fila" }));
  await screen.findByText("2 UC(s) serão incluídas no arquivo.");
  await user.click(screen.getByLabelText("Escolher filtros"));
  const neighborhood = screen.getByLabelText("Bairro");
  expect(neighborhood).toBeDisabled();
  await user.selectOptions(screen.getByLabelText("Município"), "Recife");
  expect(screen.getByRole("option", { name: "Boa Vista" })).toBeInTheDocument();
  expect(
    screen.queryByRole("option", { name: "Carmo" }),
  ).not.toBeInTheDocument();
  await user.selectOptions(neighborhood, "Boa Vista");
  await user.selectOptions(screen.getByLabelText("Município"), "Olinda");
  expect(neighborhood).toHaveValue("");
  expect(screen.getByRole("option", { name: "Carmo" })).toBeInTheDocument();
  expect(
    screen.queryByRole("option", { name: "Boa Vista" }),
  ).not.toBeInTheDocument();
});

it("envia a planilha Excel e apresenta importação parcial por linha", async () => {
  const fetch = vi.fn().mockResolvedValue(
    new Response(
      JSON.stringify({
        imported: 1,
        errors: [{ line: 3, message: "Ordem alterada." }],
      }),
      { status: 200 },
    ),
  );
  vi.stubGlobal("fetch", fetch);
  render(
    <QueryClientProvider client={new QueryClient()}>
      <FieldFiles request="page=2" />
    </QueryClientProvider>,
  );
  const file = new File(["excel"], "campo.xlsx", {
    type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
  });
  Object.defineProperty(file, "arrayBuffer", {
    value: async () => new TextEncoder().encode("excel").buffer,
  });
  await userEvent.upload(
    screen.getByLabelText("Importar resultados de campo"),
    file,
  );
  expect(
    await screen.findByText(
      /1 resultado\(s\) registrado\(s\).*Linha 3: Ordem alterada/,
    ),
  ).toBeInTheDocument();
  expect(JSON.parse(fetch.mock.calls[0][1].body)).toEqual({
    xlsx: btoa("excel"),
  });
});

it("recusa arquivo acima do limite antes de enviar", async () => {
  const fetch = vi.fn();
  vi.stubGlobal("fetch", fetch);
  render(
    <QueryClientProvider client={new QueryClient()}>
      <FieldFiles request="" />
    </QueryClientProvider>,
  );
  await userEvent.upload(
    screen.getByLabelText("Importar resultados de campo"),
    new File([new Uint8Array(1_000_001)], "campo.xlsx"),
  );
  expect(screen.getByText("O arquivo deve ter até 1 MB.")).toBeInTheDocument();
  expect(fetch).not.toHaveBeenCalled();
});

it("atualiza a contagem com os filtros e bloqueia recorte vazio", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string) => {
      const params = new URL(url, "http://localhost").searchParams;
      const value = params.has("options_only")
        ? {
            options: {
              municipio: ["Recife"],
              bairro: [],
              categoria: [],
              classe: [],
            },
          }
        : { count: params.has("municipio") ? 0 : 42 };
      return new Response(JSON.stringify(value), { status: 200 });
    }),
  );
  render(
    <QueryClientProvider client={new QueryClient()}>
      <FieldFiles request="page=3" />
    </QueryClientProvider>,
  );
  const user = userEvent.setup();
  await user.click(screen.getByRole("button", { name: "Exportar fila" }));
  expect(
    await screen.findByText("42 UC(s) serão incluídas no arquivo."),
  ).toBeInTheDocument();
  await user.click(screen.getByLabelText("Escolher filtros"));
  await user.selectOptions(screen.getByLabelText("Município"), "Recife");
  expect(
    await screen.findByText(
      "Não existem UCs com esses filtros. Altere a seleção para exportar.",
    ),
  ).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Baixar CSV" })).toBeDisabled();
});

it("explica filtros incompatíveis sem exibir código HTTP", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string) => {
      const options = url.includes("options_only");
      return new Response(
        JSON.stringify(options ? { options: {} } : { detail: [] }),
        { status: options ? 200 : 422 },
      );
    }),
  );
  render(
    <QueryClientProvider client={new QueryClient()}>
      <FieldFiles request="" />
    </QueryClientProvider>,
  );
  await userEvent.click(screen.getByRole("button", { name: "Exportar fila" }));
  expect(
    await screen.findByText(/Não existem UCs para essa combinação/),
  ).toBeInTheDocument();
  expect(screen.queryByText(/Falha HTTP/)).not.toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Baixar CSV" })).toBeDisabled();
});
