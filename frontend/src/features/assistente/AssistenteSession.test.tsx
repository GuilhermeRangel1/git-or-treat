import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, expect, it, vi } from "vitest";
import { PROFILE_PERMISSIONS } from "@/shared/auth/platformAccess";
import { AuthProvider } from "@/shared/auth/AuthProvider";
import RequireSession from "@/shared/auth/RequireSession";
import { useSession } from "@/shared/auth/useSession";
import AssistentePage from "./AssistentePage";

function RevalidateSession() {
  const session = useSession();
  return (
    <>
      <button onClick={() => void session.reloadSession()}>
        Verificar acesso
      </button>
      <button onClick={() => void session.logout()}>Sair da conta</button>
    </>
  );
}

afterEach(() => vi.unstubAllGlobals());

it("envia nova tentativa ao restaurar histórico interrompido sem opção de atualizar dados", async () => {
  const conversation = {
    id: "44444444-4444-4444-8444-444444444444",
    title: "Conversa interrompida",
    revision: 2,
    created_at: "2026-11-02T12:00:00Z",
    updated_at: "2026-11-02T12:00:00Z",
    expires_at: "2026-12-02T12:00:00Z",
    message_count: 0,
  };
  const originalRequest = "55555555-5555-4555-8555-555555555555";
  const payloads: Array<Record<string, unknown>> = [];
  vi.stubGlobal(
    "fetch",
    vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const path = new URL(String(input), "http://localhost").pathname;
      if (path.endsWith("/auth/session"))
        return Promise.resolve(
          Response.json({
            enabled: true,
            user: {
              id: "history-person",
              username: "history-person",
              profile: "losses",
              permissions: PROFILE_PERMISSIONS.losses,
            },
            expires_at: "2099-01-01T00:00:00Z",
          }),
        );
      if (path.endsWith("/questions")) {
        const payload = JSON.parse(String(init?.body));
        payloads.push(payload);
        if (payload.request_id === originalRequest)
          throw new Error(
            "Não reutilizar tentativa com parâmetros desconhecidos",
          );
        return Promise.resolve(
          Response.json({
            contract_version: "v1",
            correlation_id: "a".repeat(32),
            audit_reference: "b".repeat(32),
            status: "answered",
            answer: "Nova consulta concluída.",
            evidence: [
              {
                source: "gold.local",
                description: "Agregado de teste.",
                is_demo: false,
              },
            ],
            limitations: [],
            analysis_context: { metric: "Receita", unit: "R$", filters: {} },
          }),
        );
      }
      if (path.endsWith(`/conversations/${conversation.id}`))
        return Promise.resolve(
          Response.json({
            conversation,
            historical: true,
            exchanges: [
              {
                request_id: originalRequest,
                state: "interrupted",
                question: null,
                response: null,
              },
            ],
          }),
        );
      if (path.endsWith("/conversations"))
        return Promise.resolve(
          Response.json({ items: [conversation], has_more: false }),
        );
      throw new Error(`Rota inesperada: ${path}`);
    }),
  );
  render(
    <QueryClientProvider
      client={
        new QueryClient({ defaultOptions: { queries: { retry: false } } })
      }
    >
      <MemoryRouter>
        <AuthProvider>
          <RequireSession>
            <AssistentePage />
          </RequireSession>
        </AuthProvider>
      </MemoryRouter>
    </QueryClientProvider>,
  );
  const user = userEvent.setup();
  await user.click(
    await screen.findByRole("button", { name: "Conversa interrompida" }),
  );
  await screen.findByText(/Há um envio sem resposta salva/);
  expect(
    screen.queryByRole("button", { name: "Retomar com dados atuais" }),
  ).not.toBeInTheDocument();
  expect(
    screen.queryByText(/Você está vendo respostas salvas/),
  ).not.toBeInTheDocument();
  await user.type(
    screen.getByRole("textbox", { name: "Escreva sua pergunta" }),
    "Qual o consumo em junho de 2026?",
  );
  await user.click(screen.getByRole("button", { name: "Enviar pergunta" }));
  expect(await screen.findByText("Nova consulta concluída.")).toBeVisible();
  expect(payloads).toHaveLength(1);
  expect(payloads[0].request_id).not.toBe(originalRequest);
  expect(payloads[0].refresh_context).toBe(false);
  expect(payloads[0].question).toBe("Qual o consumo em junho de 2026?");
});

it.each([false, true])(
  "descarta conversa e resposta anterior ao trocar identidade (resposta atrasada: %s)",
  async (late) => {
    let settle: (value: Response) => void = () => {};
    const pending = new Promise<Response>((resolve) => {
      settle = resolve;
    });
    const session = (id: string) => ({
      enabled: true,
      user: {
        id,
        username: id,
        profile: "customer_service",
        permissions: PROFILE_PERMISSIONS.customer_service,
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
    const sessionResponses = [session("person-a"), session("person-b")];
    const summaries = [
      "11111111-1111-4111-8111-111111111111",
      "22222222-2222-4222-8222-222222222222",
    ];
    let questionCount = 0;
    const questionPayloads: Array<Record<string, unknown>> = [];
    const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const path = new URL(String(input), "http://localhost").pathname;
      if (path.endsWith("/api/v1/auth/session")) {
        return Promise.resolve(Response.json(sessionResponses.shift()));
      }
      if (path === "/api/v1/ai/conversations" && init?.method === "POST") {
        const conversationId = summaries.shift()!;
        const now = "2026-11-02T12:00:00Z";
        return Promise.resolve(
          Response.json({
            id: conversationId,
            title: "Nova conversa",
            revision: 1,
            created_at: now,
            updated_at: now,
            expires_at: "2026-12-02T12:00:00Z",
            message_count: 0,
          }),
        );
      }
      if (path.endsWith("/questions")) {
        questionPayloads.push(JSON.parse(String(init?.body)));
        questionCount++;
        if (questionCount === 1 && late) return pending;
        return Promise.resolve(
          Response.json(
            answer(
              questionCount === 1
                ? "Resposta privada da pessoa A."
                : "Nova conversa.",
            ),
          ),
        );
      }
      throw new Error(`Rota inesperada no teste: ${path}`);
    });
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
    if (!late)
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
    expect(questionPayloads[1]).not.toHaveProperty("context");
    if (late) {
      await act(async () => {
        settle(Response.json(answer("Resposta privada da pessoa A.")));
        await pending;
      });
      expect(
        screen.queryByText("Resposta privada da pessoa A."),
      ).not.toBeInTheDocument();
      expect(screen.getByText("Nova conversa.")).toBeVisible();
    }
  },
);

it.each([false, true])(
  "remove conversa e descarta resposta após logout (resposta atrasada: %s)",
  async (late) => {
    let settle: (value: Response) => void = () => {};
    const pending = new Promise<Response>((resolve) => {
      settle = resolve;
    });
    const account = {
      enabled: true,
      user: {
        id: "person-logout",
        username: "person-logout",
        profile: "customer_service",
        permissions: PROFILE_PERMISSIONS.customer_service,
      },
      expires_at: "2099-01-01T00:00:00Z",
    };
    const summary = {
      id: "33333333-3333-4333-8333-333333333333",
      title: "Nova conversa",
      revision: 1,
      created_at: "2026-11-02T12:00:00Z",
      updated_at: "2026-11-02T12:00:00Z",
      expires_at: "2026-12-02T12:00:00Z",
      message_count: 0,
    };
    const response = {
      contract_version: "v1",
      correlation_id: "c".repeat(32),
      audit_reference: "d".repeat(32),
      status: "answered",
      answer: "Resposta privada antes do logout.",
      evidence: [
        {
          source: "gold.local",
          description: "Agregado de teste.",
          is_demo: false,
        },
      ],
      limitations: [],
      analysis_context: { metric: "Receita", unit: "R$", filters: {} },
    };
    const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const path = new URL(String(input), "http://localhost").pathname;
      if (path.endsWith("/api/v1/auth/session"))
        return Promise.resolve(Response.json(account));
      if (path.endsWith("/api/v1/auth/logout"))
        return Promise.resolve(new Response(null, { status: 204 }));
      if (path === "/api/v1/ai/conversations" && init?.method === "POST")
        return Promise.resolve(Response.json(summary));
      if (path.endsWith("/questions"))
        return late ? pending : Promise.resolve(Response.json(response));
      throw new Error(`Rota inesperada no teste: ${path}`);
    });
    vi.stubGlobal("fetch", fetchMock);
    render(
      <QueryClientProvider
        client={
          new QueryClient({ defaultOptions: { queries: { retry: false } } })
        }
      >
        <MemoryRouter initialEntries={["/assistente"]}>
          <AuthProvider>
            <RevalidateSession />
            <Routes>
              <Route
                path="/assistente"
                element={
                  <RequireSession>
                    <AssistentePage />
                  </RequireSession>
                }
              />
              <Route path="/login" element={<p>Entrada</p>} />
            </Routes>
          </AuthProvider>
        </MemoryRouter>
      </QueryClientProvider>,
    );
    const user = userEvent.setup();
    await user.type(
      await screen.findByRole("textbox", { name: "Escreva sua pergunta" }),
      "Qual foi a receita?",
    );
    await user.click(screen.getByRole("button", { name: "Enviar pergunta" }));
    if (!late) await screen.findByText("Resposta privada antes do logout.");
    await user.click(screen.getByRole("button", { name: "Sair da conta" }));
    expect(await screen.findByText("Entrada")).toBeVisible();
    if (late) {
      await act(async () => {
        settle(Response.json(response));
        await pending;
      });
    }
    expect(
      screen.queryByText("Resposta privada antes do logout."),
    ).not.toBeInTheDocument();
    expect(screen.queryByText("Qual foi a receita?")).not.toBeInTheDocument();
  },
);
