import { afterEach, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import DeleteOrder from "./DeleteOrder";

afterEach(() => vi.unstubAllGlobals());
it("exige confirmação do ID e só anuncia exclusão após resposta do servidor", async () => {
  const fetch = vi.fn().mockResolvedValue(new Response(null, { status: 204 }));
  vi.stubGlobal("fetch", fetch);
  const onDeleted = vi.fn();
  const order = {
    id: 42,
    version: 3,
    uc_id: "UC-TESTE",
    reason: "Visita",
    priority: "MEDIA" as const,
    status: "CONCLUIDA" as const,
    notes: null,
    result: "Sem irregularidade",
    created_at: "2026-11-02T00:00:00Z",
    updated_at: "2026-11-02T00:00:00Z",
    suspicion_reference: null,
    cancellation_reason: null,
  };
  render(
    <QueryClientProvider client={new QueryClient()}>
      <DeleteOrder order={order} onDeleted={onDeleted} />
    </QueryClientProvider>,
  );
  const user = userEvent.setup();
  await user.click(screen.getByRole("button", { name: "Excluir ordem" }));
  expect(
    screen.getByRole("button", { name: "Confirmar exclusão" }),
  ).toBeDisabled();
  expect(fetch).not.toHaveBeenCalled();
  await user.type(screen.getByLabelText("Digite 42 para confirmar"), "42");
  await user.click(screen.getByRole("button", { name: "Confirmar exclusão" }));
  await waitFor(() => expect(onDeleted).toHaveBeenCalledOnce());
  expect(fetch.mock.calls[0][1].method).toBe("DELETE");
  expect(JSON.parse(fetch.mock.calls[0][1].body)).toEqual({
    version: 3,
    confirmed_order_id: 42,
  });
});
