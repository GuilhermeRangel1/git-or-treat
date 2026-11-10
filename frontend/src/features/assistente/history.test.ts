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
  it("reabre resposta SQL F1 versionada pela mesma apresentação pública", () => {
    const value = decodeDetail({
      conversation,
      historical: true,
      exchanges: [
        {
          request_id: conversation.id,
          state: "completed",
          question: "E no ano anterior?",
          response: null,
          batch_ref:
            "gold-csv-v2:GOLD_20261106T000000Z_aaaaaaaa:12345678-1234-4123-8123-123456789abc",
          sql_response: {
            correlation_id: "a".repeat(32),
            audit_reference: "b".repeat(32),
            status: "needs_clarification",
            clarification: {
              question: "Qual período você quer comparar?",
              missing_fields: ["period"],
            },
          },
        },
      ],
    });
    expect(value.exchanges[0].response?.sql_analysis_mode).toBe(true);
    expect(value.exchanges[0].response?.message).toBe(
      "Qual período você quer comparar?",
    );
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
