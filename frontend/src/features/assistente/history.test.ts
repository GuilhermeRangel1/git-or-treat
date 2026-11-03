import { describe, expect, it } from "vitest";
import { decodeDetail, decodeSummary } from "./history";

const conversation = {
  id: "00000000-0000-0000-0000-000000000001",
  title: "Receita",
  revision: 1,
  created_at: "2026-11-02T12:00:00Z",
  updated_at: "2026-11-02T12:00:00Z",
  expires_at: "2026-12-02T12:00:00Z",
  message_count: 2,
};

describe("contrato do histórico", () => {
  it("mantém envio interrompido sem fabricar uma resposta", () => {
    const value = decodeDetail({
      conversation,
      historical: true,
      exchanges: [
        {
          request_id: conversation.id,
          state: "interrupted",
          question: null,
          response: null,
        },
      ],
    });
    expect(value.exchanges[0].response).toBeNull();
    expect(value.exchanges[0].state).toBe("interrupted");
  });
  it.each([
    { ...conversation, revision: 0 },
    { ...conversation, expires_at: "invalid" },
    { ...conversation, message_count: -1 },
  ])("rejeita metadado inválido", (value) => {
    expect(() => decodeSummary(value)).toThrow();
  });
  it("rejeita resposta corrompida sem renderizar JSON arbitrário", () => {
    expect(() =>
      decodeDetail({
        conversation,
        historical: true,
        exchanges: [
          {
            request_id: conversation.id,
            state: "completed",
            question: "Receita?",
            response: { answer: "sem contrato" },
          },
        ],
      }),
    ).toThrow();
  });
});
