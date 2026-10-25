import { expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import CreateOrder from "./CreateOrder";

function setup() {
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
  expect(screen.queryByRole("status")).not.toBeInTheDocument();
  await userEvent.click(button);
  await waitFor(() =>
    expect(screen.getByRole("status")).toHaveTextContent(
      "confirmada pelo servidor",
    ),
  );
  expect(fetch.mock.calls[0][1].headers).toEqual(
    fetch.mock.calls[1][1].headers,
  );
});
