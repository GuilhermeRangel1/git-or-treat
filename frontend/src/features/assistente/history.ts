import { apiClient } from "@/shared/api/client";
import {
  decodeAIQuestionResponse,
  decodeSqlAnalysisResponse,
  type AIQuestionResponse,
} from "./contract";

export type ConversationSummary = {
  id: string;
  title: string;
  revision: number;
  created_at: string;
  updated_at: string;
  expires_at: string;
  message_count: number;
};
export type SavedExchange = {
  request_id: string;
  state: "pending" | "completed" | "interrupted" | "unavailable";
  question: string | null;
  response: AIQuestionResponse | null;
};
export type ConversationDetail = {
  conversation: ConversationSummary;
  exchanges: SavedExchange[];
  historical: true;
};
const base = "/api/v1/ai/conversations";
const uuid = /^[a-f0-9-]{36}$/;
function object(value: unknown): Record<string, unknown> {
  if (!value || typeof value !== "object" || Array.isArray(value))
    throw new Error("Histórico inválido.");
  return value as Record<string, unknown>;
}
export function decodeSummary(value: unknown): ConversationSummary {
  const row = object(value);
  if (
    typeof row.id !== "string" ||
    !uuid.test(row.id) ||
    typeof row.title !== "string" ||
    !row.title.trim() ||
    row.title.length > 120 ||
    !Number.isInteger(row.revision) ||
    Number(row.revision) < 1 ||
    !Number.isInteger(row.message_count) ||
    Number(row.message_count) < 0 ||
    [row.created_at, row.updated_at, row.expires_at].some(
      (d) => typeof d !== "string" || !Number.isFinite(Date.parse(d)),
    )
  )
    throw new Error("Histórico inválido.");
  return row as ConversationSummary;
}
export function decodeDetail(value: unknown): ConversationDetail {
  const row = object(value);
  if (
    row.historical !== true ||
    !Array.isArray(row.exchanges) ||
    row.exchanges.length > 200
  )
    throw new Error("Histórico inválido.");
  const exchanges = row.exchanges.map((value) => {
    const entry = object(value);
    if (
      typeof entry.request_id !== "string" ||
      !uuid.test(entry.request_id) ||
      !["pending", "completed", "interrupted", "unavailable"].includes(
        String(entry.state),
      ) ||
      (entry.question !== null &&
        (typeof entry.question !== "string" || entry.question.length > 1000))
    )
      throw new Error("Histórico inválido.");
    const response =
      entry.sql_response != null
        ? decodeSqlAnalysisResponse(entry.sql_response)
        : entry.response == null
          ? null
          : decodeAIQuestionResponse(entry.response);
    return {
      request_id: entry.request_id,
      state: entry.state as SavedExchange["state"],
      question: entry.question as string | null,
      response,
    };
  });
  return {
    conversation: decodeSummary(row.conversation),
    exchanges,
    historical: true,
  };
}
export async function createConversation(requestId: string) {
  return decodeSummary(
    await apiClient<unknown>(base, {
      method: "POST",
      body: JSON.stringify({ request_id: requestId }),
    }),
  );
}
export async function listConversations(offset: number, signal?: AbortSignal) {
  const row = object(
    await apiClient<unknown>(`${base}?offset=${offset}`, { signal }),
  );
  if (
    !Array.isArray(row.items) ||
    row.items.length > 50 ||
    typeof row.has_more !== "boolean"
  )
    throw new Error("Histórico inválido.");
  return { items: row.items.map(decodeSummary), hasMore: row.has_more };
}
export async function openConversation(id: string) {
  const result = decodeDetail(
    await apiClient<unknown>(`${base}/${encodeURIComponent(id)}`),
  );
  if (result.conversation.id !== id)
    throw new Error("A conversa recebida não corresponde à selecionada.");
  return result;
}
export async function renameConversation(
  row: ConversationSummary,
  title: string,
) {
  return decodeSummary(
    await apiClient<unknown>(`${base}/${row.id}`, {
      method: "PATCH",
      body: JSON.stringify({ title, expected_revision: row.revision }),
    }),
  );
}
export async function deleteConversation(id: string) {
  await apiClient<unknown>(`${base}/${id}`, { method: "DELETE" });
}
