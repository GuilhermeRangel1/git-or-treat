import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, expect, it, vi } from "vitest";
import { AuthProvider } from "@/shared/auth/AuthProvider";
import RequireSession from "@/shared/auth/RequireSession";
import { useSession } from "@/shared/auth/useSession";
import AssistentePage from "./AssistentePage";

function RevalidateSession() {
  const session = useSession();
  return (
    <button onClick={() => void session.reloadSession()}>
      Verificar acesso
    </button>
  );
}

afterEach(() => vi.unstubAllGlobals());

it("descarta conversa e contexto anteriores ao confirmar outra identidade", async () => {
  const session = (id: string) => ({
    enabled: true,
    user: {
      id,
      username: id,
      profile: "admin",
      permissions: [
        "panorama:read",
        "revenue:read",
        "ucs:read",
        "inspections:read",
        "orders:read",
        "orders:write",
        "operations:read",
        "ai:ask",
      ],
    },
    expires_at: "2099-01-01T00:00:00Z",
  });
  const answer = (text: string) => ({
    contract_version: "v1",
    correlation_id: "a".repeat(32),
    audit_reference: "b".repeat(32),
    status: "answered",
    answer: text,
    evidence: [
      {
        source: "gold.local",
        description: "Agregado de teste.",
        is_demo: false,
      },
    ],
    limitations: [],
    analysis_context: { metric: "Receita", unit: "R$", filters: {} },
  });
  const fetchMock = vi
    .fn()
    .mockResolvedValueOnce(Response.json(session("person-a")))
    .mockResolvedValueOnce(
      Response.json(answer("Resposta privada da pessoa A.")),
    )
    .mockResolvedValueOnce(Response.json(session("person-b")))
    .mockResolvedValueOnce(Response.json(answer("Nova conversa.")));
  vi.stubGlobal("fetch", fetchMock);
  render(
    <QueryClientProvider
      client={
        new QueryClient({ defaultOptions: { queries: { retry: false } } })
      }
    >
      <MemoryRouter>
        <AuthProvider>
          <RevalidateSession />
          <RequireSession>
            <AssistentePage />
          </RequireSession>
        </AuthProvider>
      </MemoryRouter>
    </QueryClientProvider>,
  );
  const user = userEvent.setup();
  await user.type(
    await screen.findByRole("textbox", { name: "Escreva sua pergunta" }),
    "Qual a receita em janeiro?",
  );
  await user.click(screen.getByRole("button", { name: "Enviar pergunta" }));
  expect(
    await screen.findByText("Resposta privada da pessoa A."),
  ).toBeVisible();
  await user.click(screen.getByRole("button", { name: "Verificar acesso" }));
  await waitFor(() =>
    expect(
      screen.queryByText("Resposta privada da pessoa A."),
    ).not.toBeInTheDocument(),
  );
  expect(
    screen.queryByText("Qual a receita em janeiro?"),
  ).not.toBeInTheDocument();
  await user.type(
    screen.getByRole("textbox", { name: "Escreva sua pergunta" }),
    "E fevereiro?",
  );
  await user.click(screen.getByRole("button", { name: "Enviar pergunta" }));
  expect(await screen.findByText("Nova conversa.")).toBeVisible();
  expect(JSON.parse(fetchMock.mock.calls[3][1].body).context).toEqual([]);
});

it("aborta pergunta e descarta conversa quando o mesmo usuario perde o perfil admin", async () => {
  const session = (profile: "admin" | "commercial", permissions: string[]) => ({
    enabled: true,
    user: { id: "same-user", username: "same-user", profile, permissions },
    expires_at: "2099-01-01T00:00:00Z",
  });
  const answer = {
    contract_version: "v1",
    correlation_id: "a".repeat(32),
    audit_reference: "b".repeat(32),
    status: "answered",
    answer: "Resposta que chegou tarde.",
    evidence: [],
    limitations: [],
    analysis_context: { metric: "Receita", unit: "R$", filters: {} },
  };
  let resolveAnswer!: (response: Response) => void;
  let requestSignal: AbortSignal | null | undefined;
  const fetchMock = vi
    .fn()
    .mockResolvedValueOnce(
      Response.json(
        session("admin", [
          "panorama:read",
          "revenue:read",
          "ucs:read",
          "inspections:read",
          "orders:read",
          "orders:write",
          "operations:read",
          "ai:ask",
        ]),
      ),
    )
    .mockImplementationOnce((_input: RequestInfo | URL, init?: RequestInit) => {
      requestSignal = init?.signal;
      return new Promise<Response>((resolve) => {
        resolveAnswer = resolve;
      });
    })
    .mockResolvedValueOnce(
      Response.json(
        session("commercial", ["panorama:read", "revenue:read", "ai:ask"]),
      ),
    );
  vi.stubGlobal("fetch", fetchMock);
  render(
    <QueryClientProvider
      client={
        new QueryClient({ defaultOptions: { queries: { retry: false } } })
      }
    >
      <MemoryRouter>
        <AuthProvider>
          <RevalidateSession />
          <RequireSession>
            <AssistentePage />
          </RequireSession>
        </AuthProvider>
      </MemoryRouter>
    </QueryClientProvider>,
  );
  const user = userEvent.setup();
  const composer = await screen.findByRole("textbox", {
    name: "Escreva sua pergunta",
  });
  await user.type(composer, "Pergunta privada");
  await user.click(screen.getByRole("button", { name: "Enviar pergunta" }));
  await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2));
  expect(requestSignal?.aborted).toBe(false);
  await user.click(screen.getByRole("button", { name: "Verificar acesso" }));
  await waitFor(() => expect(requestSignal?.aborted).toBe(true));
  await act(async () => resolveAnswer(Response.json(answer)));
  expect(screen.queryByText("Pergunta privada")).not.toBeInTheDocument();
  expect(
    screen.queryByText("Resposta que chegou tarde."),
  ).not.toBeInTheDocument();
});
