import { chatChartPoints } from "./visualization";
import { verifyVisualExport } from "@/shared/analytics/verifyVisualExport";
import VisualEvidence from "@/shared/analytics/VisualEvidence";
import { isGoldPublicationStale } from "@/shared/analytics/goldPublication";
import { ASSISTANT_HOME_SUGGESTIONS } from "@/shared/help/assistantExamples";
import IndicatorHelp from "@/shared/help/IndicatorHelp";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useSession } from "@/shared/auth/useSession";
import { currentAuthorizationGeneration } from "@/shared/auth/authorization";
import ConversationHistory from "./ConversationHistory";
import QuestionFeedback from "./QuestionFeedback";
import { createConversation, openConversation } from "./history";
import {
  AlertCircle,
  Check,
  CircleHelp,
  Info,
  MessageCircle,
  Plus,
  RotateCcw,
  Send,
  Sparkles,
} from "lucide-react";
import {
  useEffect,
  useMemo,
  useRef,
  useState,
  type FormEvent,
  type KeyboardEvent,
} from "react";
import { useGoldPublicationRevision } from "@/shared/analytics/goldPublication";
import Button from "@/shared/ui/Button";
import { AIChatApiError, askAIQuestion } from "./api";
import { AssistantIdentity, ProcessingIndicator } from "./AssistantIdentity";
import "./assistant.css";
import type {
  AIConversationTurn,
  AIQuestionRequest,
  AIQuestionResponse,
} from "./contract";

type RetryRequest = Pick<
  AIQuestionRequest,
  | "question"
  | "context"
  | "continuation_token"
  | "conversation_id"
  | "history_request_id"
  | "refresh_context"
> & {
  sqlF1Mode: boolean;
  userMessageId: number;
  assistantMessageId: number;
};
type ChatMessage = {
  id: number;
  role: "user" | "assistant";
  content: string;
  response?: AIQuestionResponse;
  error?: AIChatApiError;
  retryRequest?: RetryRequest;
  contextEligible: boolean;
  outdated?: boolean;
  historical?: boolean;
  preliminary?: boolean;
};

const SUGGESTIONS = ASSISTANT_HOME_SUGGESTIONS;

const RESPONSE_STATES: Record<
  AIQuestionResponse["status"],
  { label: string; appearance: string }
> = {
  answered: { label: "Resposta fundamentada", appearance: "text-content" },
  needs_clarification: {
    label: "Preciso de um esclarecimento",
    appearance: "text-brand",
  },
  refused: {
    label: "Solicitação recusada",
    appearance: "text-[var(--action-danger-text)]",
  },
  no_evidence: {
    label: "Não encontrei dados suficientes",
    appearance: "text-muted",
  },
  recoverable_error: {
    label: "Não consegui concluir a consulta",
    appearance: "text-[var(--action-danger-text)]",
  },
};

function responseContent(response: AIQuestionResponse) {
  return response.status === "answered" ? response.answer! : response.message!;
}

function makeContext(messages: ChatMessage[]): AIConversationTurn[] {
  return messages
    .filter((message) => message.contextEligible)
    .map((message) => ({
      role: message.role,
      content: message.content.slice(0, 1000),
    }))
    .slice(-3);
}

function updateConversationInteraction(
  messages: ChatMessage[],
  userMessageId: number,
  assistantMessage: ChatMessage,
  moveToEnd: boolean,
): ChatMessage[] {
  const updated = messages.map((message) => {
    if (message.id === userMessageId) {
      return {
        ...message,
        contextEligible: assistantMessage.contextEligible,
      };
    }
    return message.id === assistantMessage.id ? assistantMessage : message;
  });
  const withAssistant = updated.some(
    (message) => message.id === assistantMessage.id,
  )
    ? updated
    : [...updated, assistantMessage];
  if (!moveToEnd) return withAssistant;

  const userMessage = withAssistant.find(
    (message) => message.id === userMessageId,
  );
  const previousPosition = withAssistant.filter(
    (message) =>
      message.id !== userMessageId && message.id !== assistantMessage.id,
  );
  return userMessage
    ? [...previousPosition, userMessage, assistantMessage]
    : [...previousPosition, assistantMessage];
}

function formatFilterValue(value: string | number | boolean) {
  return typeof value === "boolean" ? (value ? "Sim" : "Não") : String(value);
}

function formatExactDecimal(value: string, unit: string | null) {
  if (!/^-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?$/.test(value))
    return "Valor indisponível";
  const negative = value.startsWith("-");
  const unsigned = negative ? value.slice(1) : value;
  const [integer, fraction] = unsigned.split(".");
  const grouped = integer.replace(/\B(?=(\d{3})+(?!\d))/g, ".");
  const formatted = `${negative ? "−" : ""}${grouped}${fraction ? `,${fraction}` : ""}`;
  if (unit === "R$") return `R$ ${formatted}`;
  if (unit === "%") return `${formatted}%`;
  return unit === "kWh" || unit === "kWh por UC com leitura no mês"
    ? `${formatted} ${unit}`
    : formatted;
}

function formatSqlPublication(batchReference: string | null | undefined) {
  const match = batchReference?.match(
    /^gold-csv-v2:GOLD_(\d{4})(\d{2})(\d{2})T/,
  );
  if (!match) return "Gold v2";
  const date = new Date(
    Date.UTC(Number(match[1]), Number(match[2]) - 1, Number(match[3])),
  );
  return `Gold v2, publicação de ${new Intl.DateTimeFormat("pt-BR", {
    dateStyle: "short",
    timeZone: "UTC",
  }).format(date)}`;
}

const PERIOD_MONTHS = [
  "Jan",
  "Fev",
  "Mar",
  "Abr",
  "Mai",
  "Jun",
  "Jul",
  "Ago",
  "Set",
  "Out",
  "Nov",
  "Dez",
];

function formatPeriod(value: string) {
  const dates = [
    ...value.matchAll(/\b(\d{4})-(0[1-9]|1[0-2])(?:-(\d{2}))?\b/g),
  ];
  if (dates.length === 0) return value;

  const formatMonth = (year: string, month: string) =>
    `${PERIOD_MONTHS[Number(month) - 1]}/${year}`;
  const isValidDate = (year: number, month: number, day: number) => {
    const date = new Date(Date.UTC(year, month - 1, day));
    return (
      date.getUTCFullYear() === year &&
      date.getUTCMonth() === month - 1 &&
      date.getUTCDate() === day
    );
  };
  const isCompleteMonth = (date: RegExpMatchArray, edge: "start" | "end") => {
    const [, yearValue, monthValue, dayValue] = date;
    if (!dayValue) return true;
    const year = Number(yearValue);
    const month = Number(monthValue);
    const day = Number(dayValue);
    if (!isValidDate(year, month, day)) return false;
    const lastDay = new Date(Date.UTC(year, month, 0)).getUTCDate();
    return edge === "start" ? day === 1 : day === lastDay;
  };

  if (
    dates.length === 2 &&
    isCompleteMonth(dates[0], "start") &&
    isCompleteMonth(dates[1], "end")
  ) {
    const [, firstYear, firstMonth] = dates[0];
    const [, lastYear, lastMonth] = dates[1];
    return firstYear === lastYear && firstMonth === lastMonth
      ? formatMonth(firstYear, firstMonth)
      : `${formatMonth(firstYear, firstMonth)} – ${formatMonth(lastYear, lastMonth)}`;
  }

  return value.replace(
    /\b(\d{4})-(0[1-9]|1[0-2])(?:-(\d{2}))?\b/g,
    (match, year: string, month: string, day?: string) => {
      if (!day) return formatMonth(year, month);
      const numericYear = Number(year);
      const numericMonth = Number(month);
      const numericDay = Number(day);
      if (!isValidDate(numericYear, numericMonth, numericDay)) return match;
      return `${day}/${month}/${year}`;
    },
  );
}

function formatVisualLabel(value: string) {
  // Category names are literal business labels, even when they contain a date.
  const separator = value.lastIndexOf(" · ");
  if (separator >= 0)
    return `${value.slice(0, separator)} · ${formatPeriod(value.slice(separator + 3))}`;
  return /^\d{4}(?:-\d{2}(?:-\d{2})?)?$/.test(value)
    ? formatPeriod(value)
    : value;
}

function AnalysisContext({ response }: { response: AIQuestionResponse }) {
  const context = response.analysis_context;
  if (!context) return null;
  const details = [
    context.metric_label && ["Indicador", context.metric_label],
    context.unit && ["Unidade", context.unit],
    context.metric_definition && [
      "Definição do indicador",
      context.metric_definition,
    ],
    context.period && ["Período", formatPeriod(context.period)],
    ...Object.entries(context.filters).map(([key, value]) => [
      context.filter_labels?.[key] ?? "Filtro aplicado",
      formatFilterValue(value),
    ]),
  ].filter((detail): detail is [string, string] => Boolean(detail));
  if (details.length === 0) return null;
  return (
    <dl
      className="mt-3 flex flex-wrap gap-2"
      aria-label="Recorte analisado"
      title={context.metric_definition ?? undefined}
    >
      {details.map(([label, value]) => (
        <div
          key={label}
          className="rounded-md border border-divider bg-surface px-2.5 py-1 text-sm text-muted"
        >
          <dt className="inline font-medium">{label}</dt>
          <dd className="inline">: {value}</dd>
        </div>
      ))}
    </dl>
  );
}

function AssistantResult({
  response,
  preliminary = false,
  interpretationFailed = false,
  onChooseOption,
  choicesDisabled = true,
}: {
  response: AIQuestionResponse;
  preliminary?: boolean;
  interpretationFailed?: boolean;
  onChooseOption?: (question: string) => void;
  choicesDisabled?: boolean;
}) {
  const answered = response.status === "answered";
  const state = RESPONSE_STATES[response.status];
  if (
    !preliminary &&
    !interpretationFailed &&
    (response.status === "needs_clarification" || response.status === "refused")
  ) {
    return (
      <QuestionFeedback
        response={response}
        onChoose={onChooseOption ?? (() => {})}
        choicesDisabled={choicesDisabled || !onChooseOption}
      />
    );
  }
  return (
    <div className="mt-3 space-y-3">
      <p className={`text-sm font-semibold ${state.appearance}`}>
        {preliminary ? "Dados da consulta" : state.label}
      </p>
      <p className="whitespace-pre-wrap [overflow-wrap:anywhere] text-base sm:text-[17px] leading-7 text-content">
        {interpretationFailed
          ? "A interpretação não pôde ser concluída. Os dados da consulta continuam disponíveis."
          : preliminary
            ? "Os dados já estão disponíveis. Preparando a interpretação."
            : responseContent(response)}
      </p>
      {answered && response.visualization && (
        <VisualEvidence
          key={`${response.analysis_context?.batch_reference}-${response.visualization.metric}-${response.visualization.period}-${JSON.stringify(response.analysis_context?.filters)}`}
          canExport={() =>
            !isGoldPublicationStale() &&
            verifyVisualExport({
              metric: response.visualization!.metric,
              dimension_ids: response.visualization!.dimension_ids,
              batch_reference: response.analysis_context!.batch_reference!,
            })
          }
          data={{
            kind: response.visualization.kind,
            reading: response.visualization.reading,
            title: response.visualization.title,
            unit: response.visualization.unit,
            precision: response.visualization.precision,
            scope: response.sql_presentation
              ? [
                  formatPeriod(response.sql_presentation.period),
                  ...response.sql_presentation.filters,
                  ...response.sql_presentation.universe.map(
                    (item) => `Universo: ${item}`,
                  ),
                ].join(" · ")
              : [
                  formatPeriod(response.visualization.period),
                  ...Object.entries(
                    response.analysis_context?.filters ?? {},
                  ).map(
                    ([key, value]) =>
                      `${response.analysis_context?.filter_labels?.[key] ?? "Filtro aplicado"}: ${formatFilterValue(value)}`,
                  ),
                ].join(" · "),
            categoryLabel: response.visualization.category_label,
            note: response.visualization.note,
            ...chatChartPoints(response.visualization, formatVisualLabel),
          }}
          exportsEnabled={!response.sql_presentation}
          tableEnabled={!response.sql_presentation}
        />
      )}
      {answered && response.sql_presentation && (
        <section
          aria-label="Tabela do resultado Text-to-SQL"
          className="overflow-hidden rounded-xl border border-divider bg-surface"
        >
          <div className="border-b border-divider px-4 py-3">
            <h3 className="font-semibold text-content">Resultado detalhado</h3>
            <p className="mt-1 text-sm text-muted">
              Período: {formatPeriod(response.sql_presentation.period)}
            </p>
            {response.sql_presentation.filters.map((filter) => (
              <p key={filter} className="mt-1 text-sm text-muted">
                {filter}
              </p>
            ))}
            {response.sql_presentation.universe.map((item) => (
              <p key={item} className="mt-1 text-sm text-muted">
                Universo: {item}
              </p>
            ))}
          </div>
          <div
            tabIndex={0}
            aria-label="Resultados em tabela; use as setas para rolar"
            className="max-h-96 max-w-full overflow-auto focus-visible:outline-2 focus-visible:outline-offset-[-2px] focus-visible:outline-brand"
          >
            <table className="min-w-full border-collapse text-left text-sm">
              <caption className="sr-only">
                Valores retornados pela consulta Text-to-SQL
              </caption>
              <thead className="sticky top-0 bg-canvas text-xs text-muted">
                <tr>
                  {response.sql_presentation.columns.map((column) => (
                    <th
                      key={column.key}
                      scope="col"
                      className="whitespace-nowrap border-b border-divider px-3 py-2 font-semibold"
                    >
                      {column.label}
                      {column.unit ? ` (${column.unit})` : ""}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {response.sql_presentation.rows.map((row) => (
                  <tr
                    key={row.observation_id}
                    className="border-b border-divider last:border-0"
                  >
                    {row.cells.map((cell, index) => {
                      const column = response.sql_presentation!.columns[index];
                      const display =
                        cell === null
                          ? "Sem valor disponível"
                          : column.role === "measure"
                            ? formatExactDecimal(cell, column.unit)
                            : formatVisualLabel(cell);
                      return (
                        <td
                          key={`${row.observation_id}-${column.key}`}
                          className="whitespace-nowrap px-3 py-2 text-content"
                        >
                          {display}
                        </td>
                      );
                    })}
                  </tr>
                ))}
                {response.sql_presentation.rows.length === 0 && (
                  <tr>
                    <td
                      colSpan={response.sql_presentation.columns.length}
                      className="px-3 py-4 text-muted"
                    >
                      {response.sql_presentation.state === "empty"
                        ? "A consulta não retornou linhas neste recorte."
                        : "Não há valores de faturamento disponíveis nas linhas retornadas."}
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </section>
      )}
      {answered && response.sql_compound_analysis && (
        <section
          aria-label="Análise composta de consumo e faturamento"
          className="overflow-hidden rounded-xl border border-divider bg-surface"
        >
          <div className="border-b border-divider px-4 py-3">
            <h3 className="font-semibold text-content">
              Consumo e decomposição da receita
            </h3>
            <p className="mt-1 text-sm text-muted">
              Jul/2024–jun/2025 vs. jul/2025–jun/2026
            </p>
            <details className="mt-2 text-xs text-muted">
              <summary className="min-h-9 cursor-pointer py-2 font-medium text-content focus-visible:rounded focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand">
                Origem e método da análise
              </summary>
              <div className="space-y-1 break-words pb-2">
                <p>
                  Gold ativa:{" "}
                  {formatSqlPublication(
                    response.sql_compound_analysis.active_gold_batch,
                  )}
                </p>
                <p>Decomposição lida de staging local.</p>
                <p>Método técnico: {response.sql_compound_analysis.method}</p>
                <p>
                  Evidência: {response.sql_compound_analysis.evidence_digest}
                </p>
                <p>
                  Manifesto:{" "}
                  {response.sql_compound_analysis.staging_manifest_digest}
                </p>
              </div>
            </details>
          </div>
          <div
            tabIndex={0}
            aria-label="Detalhamento da análise composta; use as setas para rolar"
            className="max-h-96 max-w-full overflow-auto focus-visible:outline-2 focus-visible:outline-offset-[-2px] focus-visible:outline-brand"
          >
            <table className="min-w-full border-collapse text-left text-sm">
              <caption className="sr-only">
                Consumo por município e decomposição de faturamento por classe
              </caption>
              <thead className="sticky top-0 bg-canvas text-xs text-muted">
                <tr>
                  {[
                    "Município",
                    "Bairro",
                    "Classe",
                    "Consumo anterior (kWh)",
                    "Consumo atual (kWh)",
                    "Variação (kWh)",
                    "Variação (%)",
                    "Receita (R$)",
                    "Volume (R$)",
                    "Preço observado (R$)",
                    "Interação (R$)",
                  ].map((label) => (
                    <th
                      key={label}
                      scope="col"
                      className="whitespace-nowrap border-b border-divider px-3 py-2 font-semibold"
                    >
                      {label}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {response.sql_compound_analysis.municipalities.flatMap(
                  (municipality) =>
                    municipality.revenue_by_class.map((effect) => (
                      <tr
                        key={`${municipality.municipality}-${effect.consumption_class}`}
                        className="border-b border-divider last:border-0"
                      >
                        <td className="whitespace-nowrap px-3 py-2 text-content">
                          {municipality.municipality}
                        </td>
                        <td className="whitespace-nowrap px-3 py-2 text-content">
                          {effect.neighborhood}
                        </td>
                        <td className="whitespace-nowrap px-3 py-2 text-content">
                          {effect.consumption_class}
                        </td>
                        <td className="whitespace-nowrap px-3 py-2 text-content">
                          {formatExactDecimal(
                            municipality.previous_consumption_kwh,
                            "kWh",
                          )}
                        </td>
                        <td className="whitespace-nowrap px-3 py-2 text-content">
                          {formatExactDecimal(
                            municipality.current_consumption_kwh,
                            "kWh",
                          )}
                        </td>
                        <td className="whitespace-nowrap px-3 py-2 text-content">
                          {formatExactDecimal(municipality.change_kwh, "kWh")}
                        </td>
                        <td className="whitespace-nowrap px-3 py-2 text-content">
                          {formatExactDecimal(municipality.change_percent, "%")}
                        </td>
                        <td className="whitespace-nowrap px-3 py-2 text-content">
                          {formatExactDecimal(effect.variation_brl, "R$")}
                        </td>
                        <td className="whitespace-nowrap px-3 py-2 text-content">
                          {effect.volume_effect_brl === null
                            ? "Sem base comparável"
                            : formatExactDecimal(
                                effect.volume_effect_brl,
                                "R$",
                              )}
                        </td>
                        <td className="whitespace-nowrap px-3 py-2 text-content">
                          {effect.price_effect_brl === null
                            ? "Sem base comparável"
                            : formatExactDecimal(effect.price_effect_brl, "R$")}
                        </td>
                        <td className="whitespace-nowrap px-3 py-2 text-content">
                          {effect.interaction_effect_brl === null
                            ? "Sem base comparável"
                            : formatExactDecimal(
                                effect.interaction_effect_brl,
                                "R$",
                              )}
                        </td>
                      </tr>
                    )),
                )}
                {response.sql_compound_analysis.municipalities.length === 0 && (
                  <tr>
                    <td colSpan={11} className="px-3 py-4 text-muted">
                      Nenhum município apresentou queda de consumo nas janelas
                      comparadas.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
          <ul className="space-y-1 border-t border-divider px-4 py-3 text-sm text-muted">
            {response.sql_compound_analysis.limitations.map((limitation) => (
              <li key={limitation}>{limitation}</li>
            ))}
          </ul>
        </section>
      )}
      {answered &&
        response.sql_presentation?.state === "ready" &&
        !response.visualization &&
        ["monthly_series", "grouped_total", "ranking"].includes(
          response.sql_presentation.operation,
        ) && (
          <p className="text-sm text-muted">
            O gráfico foi omitido porque a série pode conter lacunas ou os
            valores excedem a precisão segura de visualização. A tabela mantém
            os valores exatos retornados.
          </p>
        )}
      {response.evidence.some((item) => item.is_demo) && (
        <p className="flex items-center gap-2 text-sm font-medium text-[var(--status-warning-text)]">
          <Info aria-hidden="true" className="size-4" />
          Exemplo com dados fictícios
        </p>
      )}
      {answered && response.evidence.length > 0 && (
        <div
          aria-label="Fundamento da resposta"
          className="space-y-2 text-sm leading-6 text-muted"
        >
          <p>
            {response.evidence.some((item) => item.is_demo)
              ? "Dados de demonstração"
              : response.evidence.some(
                    (item) => item.source === "documentation.indicators",
                  )
                ? "Documentação interna"
                : "Fonte: dados internos da Grid 360"}
          </p>
          {response.sql_analysis_mode && response.analysis_context && (
            <details className="text-xs text-muted">
              <summary className="min-h-9 cursor-pointer py-2 font-medium text-content focus-visible:rounded focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand">
                Detalhes da fonte
              </summary>
              <div className="space-y-1 break-words pb-2">
                <p>Fonte técnica: Diagnóstico de receita</p>
                <p>
                  {formatSqlPublication(
                    response.analysis_context.batch_reference,
                  )}
                </p>
                {response.audit_reference && (
                  <p className="break-all">
                    Registro de auditoria: {response.audit_reference}
                  </p>
                )}
              </div>
            </details>
          )}
          {response.evidence
            .filter(
              (item) =>
                item.source === "documentation.indicators" && !item.is_demo,
            )
            .map((item, index) => (
              <p key={index} className="break-words">
                {item.description}
              </p>
            ))}
        </div>
      )}
      <AnalysisContext response={response} />
      {response.limitations.length > 0 && (
        <ul
          aria-label="Limitações"
          className="space-y-1 text-sm leading-5 text-muted"
        >
          {response.limitations.map((limitation) => (
            <li key={limitation} className="flex gap-2">
              <Info aria-hidden="true" className="mt-0.5 size-3.5 shrink-0" />
              <span>{limitation}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function MessageCard({
  message,
  onRetry,
  onChooseOption,
  choicesDisabled,
}: {
  message: ChatMessage;
  onRetry: (request: RetryRequest) => void;
  onChooseOption: (question: string) => void;
  choicesDisabled: boolean;
}) {
  if (message.role === "user") {
    return (
      <article className="ml-auto w-fit max-w-[min(85%,680px)] rounded-2xl rounded-br-sm bg-selected px-4 py-3 text-base leading-6 text-content">
        <p className="whitespace-pre-wrap [overflow-wrap:anywhere]">
          {message.content}
        </p>
      </article>
    );
  }

  if (message.outdated) {
    return (
      <article className="rounded-xl border border-divider p-4 text-base text-muted">
        Os dados mudaram. Faça uma nova consulta para atualizar esta resposta.
      </article>
    );
  }

  if (message.error) {
    return (
      <article
        aria-label="Falha ao consultar o assistente"
        className="flex max-w-[min(95%,720px)] gap-3 rounded-2xl rounded-bl-sm border border-[var(--status-danger)]/30 bg-[var(--status-danger)]/5 px-4 py-3"
      >
        <AlertCircle
          aria-hidden="true"
          className="mt-0.5 size-4 shrink-0 text-[var(--status-danger)]"
        />
        <div className="min-w-0">
          <p className="text-base leading-6 text-content">{message.content}</p>
          {message.response && (
            <AssistantResult
              response={message.response}
              preliminary
              interpretationFailed
            />
          )}
          {message.error.correlationId && (
            <p className="mt-1 break-all font-mono text-xs text-muted">
              Referência: {message.error.correlationId}
            </p>
          )}
          {message.error.retryable && message.retryRequest && (
            <Button
              variant="outline"
              size="sm"
              className="mt-3"
              onClick={() => onRetry(message.retryRequest!)}
              leftIcon={<RotateCcw aria-hidden="true" className="size-3.5" />}
            >
              Tentar novamente
            </Button>
          )}
        </div>
      </article>
    );
  }

  return (
    <article className="max-w-[min(95%,720px)] rounded-2xl rounded-bl-sm border border-divider bg-surface px-4 py-3">
      <div className="flex items-center gap-2 text-sm font-semibold text-content">
        <Sparkles aria-hidden="true" className="size-4 text-brand" />
        Assistente Grid 360
      </div>
      {message.historical && (
        <p className="mt-2 text-sm text-muted">
          Resposta salva · consulte novamente para obter dados atuais.
        </p>
      )}
      {!message.response && <p className="mt-2">{message.content}</p>}
      {message.response && (
        <AssistantResult
          response={message.response}
          preliminary={message.preliminary}
          onChooseOption={onChooseOption}
          choicesDisabled={choicesDisabled}
        />
      )}
      {message.response?.status === "recoverable_error" &&
        message.response.error?.retryable &&
        message.retryRequest && (
          <Button
            variant="outline"
            size="sm"
            className="mt-3"
            onClick={() => onRetry(message.retryRequest!)}
            leftIcon={<RotateCcw aria-hidden="true" className="size-3.5" />}
          >
            Tentar novamente
          </Button>
        )}
    </article>
  );
}

export default function AssistentePage() {
  const sqlF1ModeAvailable =
    import.meta.env.VITE_GENAI_SQL_ANALYSIS_ENABLED === "true";
  const session = useSession();
  const historyEnabled = session.configured && Boolean(session.user);
  const queryClient = useQueryClient();
  const savedIdRef = useRef<string | null>(null);
  const interactionRevision = useRef(0);
  const drafts = useRef(new Map<string, string>());
  const [loadingHistory, setLoadingHistory] = useState(false);
  const [activeSavedId, setActiveSavedId] = useState<string | null>(null);
  const [hasInterruptedSend, setHasInterruptedSend] = useState(false);
  const publicationRevision = useGoldPublicationRevision();
  const { user } = session;
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [requestPhase, setRequestPhase] = useState<
    "idle" | "consulting" | "interpreting"
  >("idle");
  const isSending = requestPhase !== "idle";
  const [draft, setDraft] = useState("");
  const sqlF1Mode = sqlF1ModeAvailable;
  const [conversationId, setConversationId] = useState<string>(() =>
    crypto.randomUUID(),
  );
  const nextMessageId = useRef(0);
  const sendingRef = useRef(false);
  const composerRef = useRef<HTMLTextAreaElement>(null);
  const historyRef = useRef<HTMLDivElement>(null);
  const requestAbort = useRef<AbortController | null>(null);
  const mutation = useMutation({
    mutationFn: (input: {
      request: Parameters<typeof askAIQuestion>[0];
      onData: (response: AIQuestionResponse) => void;
      signal: AbortSignal;
      sqlF1Mode: boolean;
    }) =>
      askAIQuestion(
        input.request,
        input.onData,
        input.signal,
        input.sqlF1Mode ? "sql_f1" : "legacy",
      ),
    retry: false,
  });
  const identityKey = `${user?.id ?? ""}:${user?.profile ?? ""}:${user?.permissions.join(",") ?? ""}`;
  useEffect(() => {
    interactionRevision.current++;
    requestAbort.current?.abort();
    requestAbort.current = null;
    sendingRef.current = false;
    savedIdRef.current = null;
    // Identity changes clear the private conversation state.
    // oxlint-disable-next-line react(set-state-in-effect)
    setActiveSavedId(null);
    setConversationId(crypto.randomUUID());
    setDraft("");
    setRequestPhase("idle");
    setHasInterruptedSend(false);
    setLoadingHistory(false);
    drafts.current.clear();
    setMessages([]);
  }, [identityKey]);
  useEffect(
    () => () => {
      interactionRevision.current++;
      requestAbort.current?.abort();
    },
    [],
  );
  // Publication changes invalidate interpretation history, including saved retries.
  useEffect(() => {
    requestAbort.current?.abort();
    requestAbort.current = null;
    sendingRef.current = false;
    // eslint-disable-next-line react/set-state-in-effect -- external publication invalidates local conversation evidence.
    setRequestPhase("idle");
    setMessages((current) =>
      current.map((message) => ({
        ...message,
        contextEligible: false,
        retryRequest: undefined,
        outdated: message.role === "assistant" && Boolean(message.response),
      })),
    );
  }, [publicationRevision]);
  const hasMessages = messages.length > 0;
  const conversationContext = useMemo(() => makeContext(messages), [messages]);

  useEffect(() => {
    const history = historyRef.current;
    if (history) history.scrollTop = history.scrollHeight;
  }, [messages.length]);

  async function send(
    questionText: string,
    context: AIConversationTurn[],
    addUserMessage: boolean,
    retryAttempt?: RetryRequest,
  ) {
    const question = questionText.trim();
    if (
      !question ||
      question.length > 1000 ||
      sendingRef.current ||
      loadingHistory
    )
      return;
    const revision = interactionRevision.current;
    const authorization = currentAuthorizationGeneration();
    const current = () =>
      revision === interactionRevision.current &&
      authorization === currentAuthorizationGeneration();
    const userMessageId = addUserMessage
      ? nextMessageId.current++
      : retryAttempt?.userMessageId;
    const assistantMessageId = addUserMessage
      ? nextMessageId.current++
      : retryAttempt?.assistantMessageId;
    if (userMessageId === undefined || assistantMessageId === undefined) return;
    sendingRef.current = true;
    const retryRequest: RetryRequest = retryAttempt ?? {
      question,
      context,
      conversation_id: conversationId,
      ...(historyEnabled
        ? {
            history_request_id: crypto.randomUUID(),
            refresh_context: false,
          }
        : {}),
      sqlF1Mode,
      continuation_token:
        [...messages]
          .reverse()
          .find(
            (message) =>
              message.contextEligible &&
              message.response != null &&
              (["answered", "no_evidence"].includes(message.response.status) ||
                message.response.continuation_token != null),
          )?.response?.continuation_token ?? undefined,
      userMessageId,
      assistantMessageId,
    };
    if (addUserMessage) {
      setMessages((current) => [
        ...current,
        {
          id: userMessageId!,
          role: "user",
          content: question,
          contextEligible: true,
        },
      ]);
    }

    let preview: AIQuestionResponse | undefined;
    const abortController = new AbortController();
    requestAbort.current = abortController;
    setRequestPhase("consulting");
    try {
      const saveHistory = historyEnabled;
      if (saveHistory && !savedIdRef.current) {
        const created = await createConversation(conversationId);
        if (!current()) return;
        savedIdRef.current = created.id;
        setActiveSavedId(created.id);
        setConversationId(created.id);
      }
      if (saveHistory) retryRequest.conversation_id = savedIdRef.current!;
      const response = await mutation.mutateAsync({
        request: {
          contract_version: "v1",
          question,
          context: context.slice(-3),
          conversation_id: retryRequest.conversation_id,
          continuation_token: retryRequest.continuation_token,
          ...(saveHistory
            ? {
                history_request_id: retryRequest.history_request_id,
                refresh_context: retryRequest.refresh_context,
              }
            : {}),
        },
        signal: abortController.signal,
        sqlF1Mode: retryRequest.sqlF1Mode,
        onData: (data) => {
          if (!current()) return;
          setRequestPhase("interpreting");
          preview = data;
          setMessages((messages) =>
            updateConversationInteraction(
              messages,
              userMessageId,
              {
                id: assistantMessageId,
                role: "assistant",
                content: "Dados da consulta disponíveis.",
                response: data,
                preliminary: true,
                contextEligible: false,
              },
              true,
            ),
          );
        },
      });
      if (!current()) return;
      if (preview && response.status === "recoverable_error")
        throw new AIChatApiError(
          response.message ?? "Não foi possível concluir a interpretação.",
          response.error?.retryable ?? false,
        );
      setHasInterruptedSend(false);
      void queryClient.invalidateQueries({
        queryKey: ["ai-conversations", session.user?.id],
      });
      if (addUserMessage && response.status !== "recoverable_error") {
        setDraft("");
        if (composerRef.current) composerRef.current.style.height = "";
      }
      const assistantMessage: ChatMessage = {
        id: assistantMessageId,
        role: "assistant",
        content: responseContent(response),
        response,
        retryRequest:
          response.status === "recoverable_error" && response.error?.retryable
            ? retryRequest
            : undefined,
        contextEligible: !["recoverable_error", "refused"].includes(
          response.status,
        ),
      };
      setMessages((current) => {
        const received = response.analysis_context?.batch_reference;
        const changed =
          received &&
          current.some((turn) => {
            const previous = turn.response?.analysis_context?.batch_reference;
            return turn.contextEligible && previous && previous !== received;
          });
        return updateConversationInteraction(
          current.map((message) =>
            !changed || message.id === userMessageId
              ? message
              : {
                  ...message,
                  contextEligible: false,
                  retryRequest: undefined,
                  outdated:
                    message.role === "assistant" && Boolean(message.response),
                },
          ),
          userMessageId,
          assistantMessage,
          retryAttempt !== undefined,
        );
      });
    } catch (error) {
      const publicationConflict =
        error instanceof AIChatApiError && error.status === 409;
      if (
        !current() ||
        (abortController.signal.aborted && !publicationConflict)
      )
        return;
      if (
        error instanceof AIChatApiError &&
        error.code === "superseded_request"
      )
        return;
      const safeError =
        error instanceof AIChatApiError
          ? error
          : new AIChatApiError(
              "Não foi possível concluir a pergunta. Tente novamente mais tarde.",
              false,
            );
      const retained =
        preview &&
        ![401, 403, 409, 422].includes(safeError.status ?? 0) &&
        (await verifyVisualExport({
          metric: preview.visualization!.metric,
          dimension_ids: preview.visualization!.dimension_ids,
          batch_reference: preview.analysis_context!.batch_reference!,
        }))
          ? preview
          : undefined;
      if (!current()) return;
      const assistantMessage: ChatMessage = {
        id: assistantMessageId,
        role: "assistant",
        content: safeError.message,
        error: safeError,
        response: retained,
        preliminary: Boolean(preview),
        retryRequest: safeError.retryable ? retryRequest : undefined,
        contextEligible: false,
      };
      setMessages((current) =>
        updateConversationInteraction(
          [401, 403, 409].includes(safeError.status ?? 0)
            ? current.map((message) => ({
                ...message,
                contextEligible: false,
                retryRequest: undefined,
                outdated:
                  safeError.code !== "invalid_continuation" &&
                  message.role === "assistant" &&
                  Boolean(message.response),
              }))
            : current,
          userMessageId,
          assistantMessage,
          retryAttempt !== undefined || Boolean(preview),
        ),
      );
    } finally {
      if (requestAbort.current === abortController) {
        requestAbort.current = null;
      }
      if (current() && !abortController.signal.aborted) {
        sendingRef.current = false;
        setRequestPhase("idle");
        requestAnimationFrame(() => composerRef.current?.focus());
      }
    }
  }

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    void send(draft, conversationContext, true);
  }

  function handleComposerKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (
      event.key === "Enter" &&
      !event.shiftKey &&
      !event.nativeEvent.isComposing
    ) {
      event.preventDefault();
      event.currentTarget.form?.requestSubmit();
    }
  }

  function startNewConversation() {
    requestAbort.current?.abort();
    drafts.current.set(savedIdRef.current ?? conversationId, draft);
    interactionRevision.current++;
    sendingRef.current = false;
    setRequestPhase("idle");
    savedIdRef.current = null;
    setActiveSavedId(null);
    setHasInterruptedSend(false);
    setLoadingHistory(false);
    setMessages([]);
    setConversationId(crypto.randomUUID());
    setDraft("");
    if (composerRef.current) composerRef.current.style.height = "";
    mutation.reset();
  }

  async function openSaved(id: string) {
    requestAbort.current?.abort();
    drafts.current.set(savedIdRef.current ?? conversationId, draft);
    const revision = ++interactionRevision.current;
    const authorization = currentAuthorizationGeneration();
    setLoadingHistory(true);
    setRequestPhase("idle");
    mutation.reset();
    sendingRef.current = false;
    try {
      const saved = await openConversation(id);
      if (
        revision !== interactionRevision.current ||
        authorization !== currentAuthorizationGeneration()
      )
        return;
      savedIdRef.current = id;
      setActiveSavedId(id);
      setConversationId(id);
      const restored: ChatMessage[] = [];
      for (const entry of saved.exchanges) {
        const storedQuestion = entry.question?.trim();
        if (storedQuestion && storedQuestion !== "Pergunta não armazenada.") {
          restored.push({
            id: nextMessageId.current++,
            role: "user",
            content: storedQuestion,
            contextEligible: false,
          });
        }
        restored.push({
          id: nextMessageId.current++,
          role: "assistant",
          content: entry.response
            ? responseContent(entry.response)
            : "Envio interrompido ou indisponível. Você pode enviar uma nova pergunta.",
          response: entry.response ?? undefined,
          historical: true,
          contextEligible: false,
        });
      }
      setMessages(restored);
      setDraft(drafts.current.get(id) ?? "");
      const last = saved.exchanges.at(-1);
      setHasInterruptedSend(
        Boolean(last && ["pending", "interrupted"].includes(last.state)),
      );
    } finally {
      if (revision === interactionRevision.current) setLoadingHistory(false);
    }
  }

  return (
    <section
      aria-labelledby="assistant-heading"
      className="assistant-workspace mx-auto h-full min-h-0 w-full rounded-[20px] border border-divider bg-surface"
    >
      <header className="assistant-toolbar flex min-h-12 shrink-0 flex-wrap items-end justify-between gap-2 border-b border-divider px-3 py-2 sm:gap-3 sm:px-4 sm:py-3">
        <div className="flex items-center gap-2.5">
          <span className="flex size-9 items-center justify-center rounded-full bg-brand/10 text-brand">
            <MessageCircle aria-hidden="true" className="size-4" />
          </span>
          <div>
            <p className="font-heading text-base leading-6 font-semibold lg:text-lg">
              Assistente Grid 360
            </p>
            <p className="text-sm text-muted">
              Respostas com base nos dados disponíveis
            </p>
          </div>
        </div>
        <div className="flex min-w-0 flex-wrap items-center gap-1">
          <IndicatorHelp screen="assistente" />
          {hasMessages && (
            <Button
              variant="ghost"
              size="sm"
              onClick={startNewConversation}
              leftIcon={<Plus aria-hidden="true" className="size-4" />}
            >
              <span className="hidden sm:inline">Nova conversa</span>
              <span className="sm:hidden">Nova</span>
            </Button>
          )}
        </div>
      </header>

      <AssistantIdentity
        pending={isSending}
        interpreting={requestPhase === "interpreting"}
      />
      <div className="assistant-conversation flex min-h-0 min-w-0 flex-1 flex-col gap-3 p-3 lg:p-5">
        {loadingHistory && <p role="status">Abrindo conversa…</p>}
        {hasInterruptedSend && (
          <p
            className="rounded-xl border border-divider p-3 text-sm"
            role="status"
          >
            Há um envio sem resposta salva. Se ele ainda estiver em
            processamento, aguarde antes de enviar uma nova pergunta.
          </p>
        )}
        <div
          ref={historyRef}
          role="log"
          aria-label="Histórico da conversa"
          aria-live="polite"
          aria-relevant="additions text"
          tabIndex={0}
          className="flex min-h-0 flex-1 flex-col gap-4 overflow-y-auto overscroll-contain rounded-xl focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand lg:-mr-0.5 lg:p-4"
        >
          {!hasMessages ? (
            <div className="m-auto flex w-full max-w-[680px] flex-col gap-3 py-3 sm:gap-5 sm:py-5 lg:-translate-y-2">
              <div className="space-y-3 text-center">
                <h1
                  id="assistant-heading"
                  className="font-heading text-[24px] leading-[30px] sm:text-[30px] sm:leading-[38px] font-semibold lg:text-[36px] lg:leading-[44px] lg:tracking-[-0.64px]"
                >
                  O que você quer investigar?
                </h1>
                <p className="mx-auto max-w-[560px] text-base leading-[22px] text-muted">
                  Explore consumo, receita e continuidade. Cada resposta informa
                  a fonte, o período, o recorte e o fundamento disponível.
                </p>
              </div>
              <section aria-label="Perguntas comuns">
                <h2 className="mb-2 text-center text-sm font-semibold text-muted">
                  Perguntas comuns
                </h2>
                <div className="grid gap-2 sm:grid-cols-2">
                  {SUGGESTIONS.map((suggestion) => (
                    <button
                      key={suggestion}
                      type="button"
                      onClick={() => void send(suggestion, [], true)}
                      disabled={isSending}
                      className="group flex min-h-16 items-start gap-3 rounded-xl border border-divider bg-canvas/50 p-3 text-left text-base leading-6 text-content transition-colors hover:border-brand/50 hover:bg-surface-hover focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand disabled:opacity-60"
                    >
                      <CircleHelp
                        aria-hidden="true"
                        className="mt-0.5 size-4 shrink-0 text-brand"
                      />
                      <span>{suggestion}</span>
                    </button>
                  ))}
                </div>
              </section>
            </div>
          ) : (
            <>
              <h1 id="assistant-heading" className="sr-only">
                Conversa com o Assistente Grid 360
              </h1>
              {messages.map((message, index) => (
                <div
                  key={message.id}
                  id={`assistant-message-${message.id}`}
                  tabIndex={-1}
                  className="outline-none focus-visible:ring-2 focus-visible:ring-brand"
                >
                  <MessageCard
                    message={message}
                    onChooseOption={(question) =>
                      void send(question, conversationContext, true)
                    }
                    choicesDisabled={isSending || index !== messages.length - 1}
                    onRetry={(request) =>
                      void send(
                        request.question,
                        request.context,
                        false,
                        request,
                      )
                    }
                  />
                </div>
              ))}
              {isSending && (
                <ProcessingIndicator
                  interpreting={requestPhase === "interpreting"}
                />
              )}
            </>
          )}
        </div>

        <form
          onSubmit={submit}
          className="shrink-0 border-t border-divider pt-3 lg:pt-4"
        >
          <label htmlFor="assistant-question" className="sr-only">
            Escreva sua pergunta
          </label>
          <div className="flex items-end gap-2 rounded-2xl border border-control bg-canvas p-2 focus-within:outline-2 focus-within:outline-offset-2 focus-within:outline-brand">
            <textarea
              ref={composerRef}
              id="assistant-question"
              name="question"
              rows={1}
              maxLength={1000}
              placeholder="Pergunte sobre consumo, receita ou continuidade…"
              value={draft}
              onChange={(event) => {
                setDraft(event.target.value);
                event.currentTarget.style.height = "auto";
                event.currentTarget.style.height = `${Math.min(event.currentTarget.scrollHeight, 144)}px`;
              }}
              onKeyDown={handleComposerKeyDown}
              disabled={isSending}
              className="max-h-36 min-h-12 min-w-0 flex-1 resize-none overflow-y-auto bg-transparent px-2 py-2 text-base leading-6 text-content outline-none placeholder:text-muted disabled:opacity-60"
            />
            <Button
              type="submit"
              variant="primary"
              size="md"
              aria-label="Enviar pergunta"
              title="Enviar pergunta"
              disabled={!draft.trim() || isSending}
              isLoading={isSending}
              loadingLabel={null}
              className="size-12 shrink-0 rounded-xl !p-0"
            >
              {!isSending && <Send aria-hidden="true" className="size-6" />}
            </Button>
          </div>
          {sqlF1Mode && (
            <p className="mt-2 px-1 text-xs leading-4 text-muted">
              {historyEnabled
                ? "Esta conversa ficará no seu histórico privado."
                : "Esta conversa ficará disponível apenas durante esta sessão."}
            </p>
          )}
          <div className="mt-2 flex flex-wrap items-center justify-between gap-x-3 gap-y-1 px-1 text-xs leading-4 text-muted">
            <span>Enter envia · Shift + Enter quebra linha</span>
            <span className="inline-flex items-center gap-1.5">
              {draft.length}/1000
              {hasMessages && !isSending && (
                <>
                  <span aria-hidden="true">·</span>
                  <Check aria-hidden="true" className="size-3.5" />
                  {historyEnabled ? "histórico privado" : "conversa temporária"}
                </>
              )}
            </span>
          </div>
        </form>
      </div>
      <aside
        aria-label="Conversas salvas"
        className="assistant-history-sidebar min-h-0 overflow-hidden p-3 sm:p-4"
      >
        {historyEnabled ? (
          <ConversationHistory
            actor={session.user!.id}
            activeId={activeSavedId}
            onOpen={openSaved}
            onDeleted={(id) => {
              if (savedIdRef.current === id) startNewConversation();
            }}
          />
        ) : (
          <section aria-labelledby="assistant-conversations-heading">
            <h2
              id="assistant-conversations-heading"
              className="text-sm font-semibold uppercase tracking-wider text-muted"
            >
              Conversas
            </h2>
            <p className="mt-3 text-sm leading-5 text-muted">
              Entre na sua conta para salvar e gerenciar conversas. Esta
              conversa fica somente nesta tela.
            </p>
          </section>
        )}
      </aside>
    </section>
  );
}
