import { it, expect, vi, afterEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import FieldFiles from "./FieldFiles";

afterEach(() => vi.unstubAllGlobals());

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
