import { expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import CreateOrder from "./CreateOrder";

function setup(onRefresh = vi.fn()) {
  const client = new QueryClient({
    defaultOptions: { mutations: { retry: false } },
  });
  render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <CreateOrder
          uc="UC-1004"
          sourceVersion="demo-v1"
          ruleVersion="dev05-v1"
          disabled={false}
          onRefresh={onRefresh}
        />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

const confirmed = {
  id: 42,
  uc_id: "UC-1004",
  reason: "Suspeita de teste",
  priority: "MEDIA",
  status: "PENDENTE",
  notes: null,
  result: null,
  created_at: "2026-10-23T12:00:00Z",
  updated_at: "2026-10-23T12:00:00Z",
  suspicion_reference: "reference",
  version: 1,
  cancellation_reason: null,
};

it("aguarda confirmação, bloqueia cliques durante envio e permite acompanhar", async () => {
  let respond!: (r: Response) => void;
  const fetch = vi.fn(
    () =>
      new Promise<Response>((resolve) => {
        respond = resolve;
      }),
  );
  vi.stubGlobal("fetch", fetch);
  setup();
  await userEvent.click(
    screen.getByRole("button", { name: "Criar ordem de inspeção" }),
  );
  expect(screen.getByRole("button")).toBeDisabled();
  expect(
    screen.queryByText(/confirmada pelo servidor/),
  ).not.toBeInTheDocument();
  respond(new Response(JSON.stringify(confirmed), { status: 201 }));
  expect(await screen.findByRole("status")).toHaveTextContent(
    "Ordem 42 confirmada pelo servidor",
  );
  expect(
    screen.getByRole("link", { name: "Acompanhar ordem" }),
  ).toHaveAttribute("href", "/ordens?uc_id=UC-1004");
  expect(fetch).toHaveBeenCalledTimes(1);
});

it("reenvia com a mesma chave após perda de resposta e recusa falso sucesso", async () => {
  const fetch = vi
    .fn()
    .mockRejectedValueOnce(new Error("response lost"))
    .mockResolvedValueOnce(
      new Response(JSON.stringify(confirmed), { status: 200 }),
    );
  vi.stubGlobal("fetch", fetch);
  setup();
  const button = screen.getByRole("button", {
    name: "Criar ordem de inspeção",
  });
  await userEvent.click(button);
  expect(await screen.findByRole("alert")).toHaveTextContent(
    "A criação não foi confirmada",
  );
  expect(
    screen.getByRole("button", { name: "Reenviar mesma criação" }),
  ).toBeVisible();
  expect(
    screen.getByRole("button", { name: "Criar ordem de inspeção" }),
  ).toBeDisabled();
  expect(screen.queryByRole("status")).not.toBeInTheDocument();
  await userEvent.click(
    screen.getByRole("button", { name: "Reenviar mesma criação" }),
  );
  await waitFor(() =>
    expect(screen.getByRole("status")).toHaveTextContent(
      "confirmada pelo servidor",
    ),
  );
  expect(fetch.mock.calls[0][1].headers).toEqual(
    fetch.mock.calls[1][1].headers,
  );
  expect(fetch.mock.calls[0][1].body).toBe(fetch.mock.calls[1][1].body);
});

it("explica suspeita desatualizada e permite atualizar sem repetir o conflito", async () => {
  const onRefresh = vi.fn();
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({
          detail: "A suspeita mudou.",
          error: { code: "stale_suspicion", message: "A suspeita mudou." },
        }),
        { status: 409 },
      ),
    ),
  );
  setup(onRefresh);
  await userEvent.click(
    screen.getByRole("button", { name: "Criar ordem de inspeção" }),
  );
  expect(await screen.findByRole("alert")).toHaveTextContent(
    "A suspeita mudou desde a consulta",
  );
  expect(
    screen.getByRole("button", { name: "Atualizar dados da suspeita" }),
  ).toBeVisible();
  expect(
    screen.queryByRole("button", { name: "Reenviar mesma criação" }),
  ).toBeNull();
  await userEvent.click(
    screen.getByRole("button", { name: "Atualizar dados da suspeita" }),
  );
  expect(onRefresh).toHaveBeenCalledTimes(1);
});

it("direciona conflito de ordem ativa para a OS retornada pelo servidor", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({
          detail: "Ordem ativa.",
          error: {
            code: "active_order_exists",
            message: "Ordem ativa.",
            order_id: 77,
          },
        }),
        { status: 409 },
      ),
    ),
  );
  setup();
  await userEvent.click(
    screen.getByRole("button", { name: "Criar ordem de inspeção" }),
  );
  expect(await screen.findByRole("alert")).toHaveTextContent(
    "Já existe uma ordem ativa para esta UC",
  );
  expect(
    screen.getByRole("link", { name: "Acompanhar OS-000077" }),
  ).toHaveAttribute("href", "/ordens?uc_id=UC-1004&order_id=77");
  expect(
    screen.queryByRole("button", { name: "Reenviar mesma criação" }),
  ).toBeNull();
});
