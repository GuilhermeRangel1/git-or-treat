import { it, expect, vi, afterEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import FieldFiles from "./FieldFiles";

afterEach(() => vi.unstubAllGlobals());

it("mostra apenas exportação em Inspeções e apenas resultados em Ordens", () => {
  const client = new QueryClient();
  const { rerender } = render(
    <QueryClientProvider client={client}>
      <FieldFiles mode="export" />
    </QueryClientProvider>,
  );
  expect(
    screen.getByRole("button", { name: "Exportar fila" }),
  ).toBeInTheDocument();
  expect(
    screen.queryByRole("button", { name: "Selecionar planilha" }),
  ).not.toBeInTheDocument();
  rerender(
    <QueryClientProvider client={client}>
      <FieldFiles mode="results" />
    </QueryClientProvider>,
  );
  expect(
    screen.queryByRole("button", { name: "Exportar fila" }),
  ).not.toBeInTheDocument();
  const help =
    "Baixe o modelo, preencha a coluna resultado e importe de volta. XLSX ou CSV, até 1 MB, 500 ordens.";
  expect(
    screen.getByRole("button", { name: "Importar resultados" }),
  ).toHaveAccessibleDescription(help);
  expect(
    screen.getByRole("button", { name: "Baixar modelo" }),
  ).toBeInTheDocument();
  expect(screen.queryByRole("heading")).not.toBeInTheDocument();
  expect(
    screen.getByLabelText("Importar resultados de campo"),
  ).toHaveAccessibleDescription(help);
  expect(screen.getByText(help)).toBeVisible();
  expect(screen.queryByText("Planilha preenchida")).not.toBeInTheDocument();
  expect(screen.queryByText(/Cada linha válida/)).not.toBeInTheDocument();
});

it("no modo de resultados só orienta a correção quando a importação tem erros", async () => {
  const fetch = vi
    .fn<() => Promise<Response>>()
    .mockResolvedValueOnce(
      new Response(JSON.stringify({ imported: 2, errors: [] }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    )
    .mockResolvedValueOnce(
      new Response(
        JSON.stringify({
          imported: 1,
          errors: [{ line: 3, message: "Ordem alterada." }],
        }),
        { status: 200, headers: { "Content-Type": "application/json" } },
      ),
    );
  vi.stubGlobal("fetch", fetch);
  render(
    <QueryClientProvider client={new QueryClient()}>
      <FieldFiles mode="results" />
    </QueryClientProvider>,
  );
  const user = userEvent.setup();
  const file = new File(["ordem;resultado"], "resultados.csv", {
    type: "text/csv",
  });
  Object.defineProperty(file, "text", {
    value: async () => "ordem;resultado",
  });
  const input = screen.getByLabelText("Importar resultados de campo");

  await user.upload(input, file);
  expect(await screen.findByRole("status")).toHaveTextContent(
    "2 resultado(s) registrado(s)",
  );
  expect(screen.queryByText(/Cada linha válida/)).not.toBeInTheDocument();

  await user.upload(input, file);
  expect(await screen.findByText(/Cada linha válida/)).toBeInTheDocument();
  expect(screen.getByRole("status")).toHaveTextContent(
    "Linha 3: Ordem alterada",
  );

  await user.upload(
    input,
    new File(["x".repeat(1_000_001)], "grande.csv", { type: "text/csv" }),
  );
  expect(await screen.findByRole("status")).toHaveTextContent(
    "O arquivo deve ter até 1 MB.",
  );
  expect(screen.queryByText(/Cada linha válida/)).not.toBeInTheDocument();
});

it("pergunta o formato antes de solicitar o modelo e mantém explicação de erro no diálogo", async () => {
  const fetch = vi.fn<(url: string) => Promise<Response>>(
    async () =>
      new Response(
        JSON.stringify({ detail: "Não existem ordens em andamento." }),
        { status: 422 },
      ),
  );
  vi.stubGlobal("fetch", fetch);
  render(
    <QueryClientProvider client={new QueryClient()}>
      <FieldFiles request="" />
    </QueryClientProvider>,
  );
  const user = userEvent.setup();
  await user.click(
    screen.getByRole("button", { name: "Baixar modelo de resultados" }),
  );
  expect(fetch).not.toHaveBeenCalled();
  expect(screen.getByRole("radio", { name: /Excel \(XLSX\)/ })).toBeChecked();
  await user.click(screen.getByRole("radio", { name: /CSV/ }));
  await user.click(screen.getByRole("button", { name: "Baixar CSV" }));
  expect(
    await screen.findByText("Não existem ordens em andamento."),
  ).toBeInTheDocument();
  expect(fetch.mock.calls[0][0]).toContain("template?format=csv");
});

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
