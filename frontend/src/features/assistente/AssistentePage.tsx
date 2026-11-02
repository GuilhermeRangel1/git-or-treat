import { useMutation } from "@tanstack/react-query";
import {
  AlertCircle,
  Check,
  CircleHelp,
  Database,
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

type RetryRequest = Pick<AIQuestionRequest, "question" | "context"> & {
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
};

const SUGGESTIONS = [
  "Qual foi a receita faturada em junho de 2026?",
  "Qual foi a receita residencial em junho de 2026?",
  "Quanto foi o consumo medido em Recife em junho de 2026?",
  "Qual município teve maior receita em junho de 2026?",
  "Compare a receita de maio e junho de 2026.",
  "Qual o DEC do alimentador ALM-JAB-015 em junho de 2026?",
  "Quantos chamados constam no histórico acumulado?",
];

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

function AnalysisContext({ response }: { response: AIQuestionResponse }) {
  const context = response.analysis_context;
  if (!context) return null;
  const details = [
    context.metric_label && ["Indicador", context.metric_label],
    context.unit && ["Unidade", context.unit],
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

function AssistantResult({ response }: { response: AIQuestionResponse }) {
  const answered = response.status === "answered";
  const state = RESPONSE_STATES[response.status];
  return (
    <div className="mt-3 space-y-3">
      <p className={`text-sm font-semibold ${state.appearance}`}>
        {state.label}
      </p>
      <p className="whitespace-pre-wrap text-base sm:text-[17px] leading-7 text-content">
        {responseContent(response)}
      </p>
      {response.evidence.some((item) => item.is_demo) && (
        <p className="flex items-center gap-2 text-sm font-medium text-[var(--status-warning-text)]">
          <Info aria-hidden="true" className="size-4" />
          Exemplo com dados fictícios
        </p>
      )}
      {answered && response.evidence.length > 0 && (
        <details
          aria-label="Fundamento da resposta"
          className="rounded-xl border border-divider bg-canvas/70 p-3"
        >
          <summary className="cursor-pointer text-sm font-semibold text-content focus-visible:outline-2 focus-visible:outline-brand">
            <Database aria-hidden="true" className="mr-2 inline-block size-4" />
            Como chegamos à resposta
          </summary>
          <ul className="mt-2 space-y-2">
            {response.evidence.map((item, index) => (
              <li
                key={`${item.source}-${index}`}
                className="flex flex-wrap items-start gap-x-2 gap-y-1 text-sm leading-5 text-muted"
              >
                <span>
                  {item.is_demo
                    ? "Dados de demonstração"
                    : "Fonte de dados interna"}
                </span>
                {item.is_demo && (
                  <span className="inline-flex items-center gap-1 rounded-full bg-[var(--status-warning)]/10 px-2 py-0.5 font-medium text-[var(--status-warning-text)]">
                    <Info aria-hidden="true" className="size-3" />
                    Demonstração sintética
                  </span>
                )}
              </li>
            ))}
          </ul>
          {response.analysis_context?.metric_definition && (
            <p className="mt-3 text-sm leading-5 text-muted">
              {response.analysis_context.metric_definition}
            </p>
          )}
        </details>
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
}: {
  message: ChatMessage;
  onRetry: (request: RetryRequest) => void;
}) {
  if (message.role === "user") {
    return (
      <article className="ml-auto w-fit max-w-[min(85%,680px)] rounded-2xl rounded-br-sm bg-selected px-4 py-3 text-base leading-6 text-content">
        <p className="whitespace-pre-wrap">{message.content}</p>
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
      {message.response && <AssistantResult response={message.response} />}
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
  const publicationRevision = useGoldPublicationRevision();
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [draft, setDraft] = useState("");
  const nextMessageId = useRef(0);
  const sendingRef = useRef(false);
  const composerRef = useRef<HTMLTextAreaElement>(null);
  const historyRef = useRef<HTMLDivElement>(null);
  const mutation = useMutation({ mutationFn: askAIQuestion, retry: false });
  // Publication changes invalidate interpretation history, including saved retries.
  useEffect(() => {
    // eslint-disable-next-line react/set-state-in-effect -- external publication invalidates local conversation evidence.
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
    if (!question || question.length > 1000 || sendingRef.current) return;
    const userMessageId = addUserMessage
      ? nextMessageId.current++
      : retryAttempt?.userMessageId;
    const assistantMessageId = addUserMessage
      ? nextMessageId.current++
      : retryAttempt?.assistantMessageId;
    if (userMessageId === undefined || assistantMessageId === undefined) return;
    sendingRef.current = true;
    const retryRequest = retryAttempt ?? {
      question,
      context,
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

    try {
      const response = await mutation.mutateAsync({
        contract_version: "v1",
        question,
        context: context.slice(-3),
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
      const assistantMessage: ChatMessage = {
        id: assistantMessageId,
        role: "assistant",
        content: safeError.message,
        error: safeError,
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
                  message.role === "assistant" && Boolean(message.response),
              }))
            : current,
          userMessageId,
          assistantMessage,
          retryAttempt !== undefined,
        ),
      );
    } finally {
      sendingRef.current = false;
      requestAnimationFrame(() => composerRef.current?.focus());
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
    if (mutation.isPending) return;
    setMessages([]);
    setDraft("");
    if (composerRef.current) composerRef.current.style.height = "";
    mutation.reset();
  }

  return (
    <section
      aria-labelledby="assistant-heading"
      className="assistant-workspace mx-auto h-full min-h-0 w-full rounded-[20px] border border-divider bg-surface"
    >
      <header className="assistant-toolbar flex min-h-12 shrink-0 items-center justify-between gap-3 border-b border-divider px-4 py-3">
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
        {hasMessages && (
          <Button
            variant="ghost"
            size="sm"
            onClick={startNewConversation}
            disabled={mutation.isPending}
            leftIcon={<Plus aria-hidden="true" className="size-4" />}
          >
            <span className="hidden sm:inline">Nova conversa</span>
            <span className="sm:hidden">Nova</span>
          </Button>
        )}
      </header>

      <AssistantIdentity pending={mutation.isPending} />
      <div className="assistant-conversation flex min-h-0 min-w-0 flex-1 flex-col gap-3 p-3 lg:p-5">
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
            <div className="m-auto flex w-full max-w-[680px] flex-col gap-5 py-5">
              <div className="space-y-3 text-center">
                <h1
                  id="assistant-heading"
                  className="font-heading text-[30px] leading-[38px] font-semibold lg:text-[36px] lg:leading-[44px] lg:tracking-[-0.64px]"
                >
                  O que você quer investigar?
                </h1>
                <p className="mx-auto max-w-[560px] text-base leading-[22px] text-muted">
                  Explore consumo, receita e continuidade. Cada resposta informa
                  a fonte, o período, o recorte e o fundamento disponível.
                </p>
              </div>
              <section aria-label="Perguntas comuns">
                <h2 className="mb-2 text-sm font-semibold text-muted">
                  Perguntas comuns
                </h2>
                <div className="grid gap-2 sm:grid-cols-2">
                  {SUGGESTIONS.map((suggestion) => (
                    <button
                      key={suggestion}
                      type="button"
                      onClick={() => void send(suggestion, [], true)}
                      disabled={mutation.isPending}
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
              <p className="flex items-start justify-center gap-2 text-center text-sm leading-5 text-muted">
                <Info aria-hidden="true" className="mt-0.5 size-3.5 shrink-0" />
                Informe o período e o local para uma resposta mais precisa. A
                disponibilidade dos dados é conferida a cada pergunta. A
                conversa fica apenas nesta tela e não é salva.
              </p>
            </div>
          ) : (
            <>
              <h1 id="assistant-heading" className="sr-only">
                Conversa com o Assistente Grid 360
              </h1>
              {messages.map((message) => (
                <div
                  key={message.id}
                  id={`assistant-message-${message.id}`}
                  tabIndex={-1}
                  className="outline-none focus-visible:ring-2 focus-visible:ring-brand"
                >
                  <MessageCard
                    message={message}
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
              {mutation.isPending && <ProcessingIndicator />}
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
              disabled={mutation.isPending}
              className="max-h-36 min-h-12 flex-1 resize-none overflow-y-auto bg-transparent px-2 py-2 text-base leading-6 text-content outline-none placeholder:text-muted disabled:opacity-60"
            />
            <Button
              type="submit"
              variant="primary"
              size="md"
              aria-label="Enviar pergunta"
              title="Enviar pergunta"
              disabled={!draft.trim() || mutation.isPending}
              isLoading={mutation.isPending}
              loadingLabel={null}
              className="size-12 rounded-xl !p-0"
            >
              {!mutation.isPending && (
                <Send aria-hidden="true" className="size-6" />
              )}
            </Button>
          </div>
          <div className="mt-2 flex flex-wrap items-center justify-between gap-x-3 gap-y-1 px-1 text-xs leading-4 text-muted">
            <span>Enter envia · Shift + Enter quebra linha</span>
            <span className="inline-flex items-center gap-1.5">
              {draft.length}/1000
              {hasMessages && !mutation.isPending && (
                <>
                  <span aria-hidden="true">·</span>
                  <Check aria-hidden="true" className="size-3.5" />
                  conversa temporária
                </>
              )}
            </span>
          </div>
        </form>
      </div>
      <aside
        aria-label="Perguntas desta conversa"
        className="assistant-question-index min-h-0 overflow-y-auto border-l border-divider p-4"
      >
        <p className="flex items-center gap-2 text-sm font-semibold uppercase tracking-wider text-muted">
          <MessageCircle aria-hidden="true" className="size-3.5" /> Suas
          perguntas{" "}
          <span className="ml-auto">
            {messages.filter((message) => message.role === "user").length}
          </span>
        </p>
        <p className="mt-2 text-sm leading-5 text-muted">
          Nesta conversa · histórico temporário
        </p>
        <ol className="mt-4 space-y-2">
          {messages
            .filter((message) => message.role === "user")
            .map((message, index) => (
              <li key={message.id}>
                <button
                  type="button"
                  className="w-full rounded-xl border border-divider bg-canvas/50 p-3 text-left text-sm leading-5 text-content hover:bg-surface-hover focus-visible:outline-2 focus-visible:outline-brand"
                  onClick={() => {
                    const target = document.getElementById(
                      `assistant-message-${message.id}`,
                    );
                    target?.scrollIntoView({ block: "nearest" });
                    target?.focus({ preventScroll: true });
                  }}
                >
                  <span className="mr-2 text-brand">
                    {String(index + 1).padStart(2, "0")}
                  </span>
                  {message.content}
                </button>
              </li>
            ))}
        </ol>
        {!hasMessages && (
          <p className="mt-6 text-sm leading-5 text-muted">
            Suas perguntas aparecerão aqui para você voltar a elas durante a
            conversa.
          </p>
        )}
      </aside>
    </section>
  );
}
