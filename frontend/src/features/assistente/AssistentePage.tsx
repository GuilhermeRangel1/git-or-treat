import { useMutation } from "@tanstack/react-query";
import {
  AlertCircle,
  Check,
  CircleHelp,
  Database,
  Info,
  LoaderCircle,
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
import Button from "@/shared/ui/Button";
import { AIChatApiError, askAIQuestion } from "./api";
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
};

const SUGGESTIONS = [
  "Qual é o indicador sintético de consumo no cenário de demonstração?",
  "Compare o indicador fictício de receita entre dois períodos de demonstração.",
  "Quantas interrupções existem no cenário de demonstração?",
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
  refused: { label: "Solicitação recusada", appearance: "text-danger" },
  no_evidence: {
    label: "Sem evidência para esse recorte",
    appearance: "text-muted",
  },
  recoverable_error: {
    label: "Erro recuperável",
    appearance: "text-danger",
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

function AnalysisContext({ response }: { response: AIQuestionResponse }) {
  const context = response.analysis_context;
  if (!context) return null;
  const details = [
    context.metric && `Métrica: ${context.metric}`,
    context.unit && `Unidade: ${context.unit}`,
    context.period && `Período: ${context.period}`,
    ...Object.entries(context.filters).map(
      ([key, value]) => `${key}: ${formatFilterValue(value)}`,
    ),
  ].filter(Boolean);
  if (details.length === 0) return null;
  return (
    <dl className="mt-3 flex flex-wrap gap-2" aria-label="Recorte analisado">
      {details.map((detail) => (
        <div
          key={detail}
          className="rounded-md border border-divider bg-surface px-2.5 py-1 text-xs text-muted"
        >
          {detail}
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
      <p className={`text-xs font-semibold ${state.appearance}`}>
        {state.label}
      </p>
      <p className="whitespace-pre-wrap text-sm leading-6 text-content">
        {responseContent(response)}
      </p>
      {answered && response.evidence.length > 0 && (
        <section
          aria-label="Fundamento da resposta"
          className="rounded-xl border border-divider bg-canvas/70 p-3"
        >
          <div className="flex items-center gap-2 text-xs font-semibold text-content">
            <Database aria-hidden="true" className="size-4" />
            Evidências
          </div>
          <ul className="mt-2 space-y-2">
            {response.evidence.map((item, index) => (
              <li
                key={`${item.source}-${index}`}
                className="flex flex-wrap items-start gap-x-2 gap-y-1 text-xs leading-5 text-muted"
              >
                <span className="font-mono text-content">{item.source}</span>
                <span>{item.description}</span>
                {item.is_demo && (
                  <span className="inline-flex items-center gap-1 rounded-full bg-[var(--status-warning)]/10 px-2 py-0.5 font-medium text-[var(--status-warning)]">
                    <Info aria-hidden="true" className="size-3" />
                    Demonstração sintética
                  </span>
                )}
              </li>
            ))}
          </ul>
        </section>
      )}
      <AnalysisContext response={response} />
      {response.limitations.length > 0 && (
        <ul
          aria-label="Limitações"
          className="space-y-1 text-xs leading-5 text-muted"
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
      <article className="ml-auto max-w-[min(85%,680px)] rounded-2xl rounded-br-sm bg-selected px-4 py-3 text-sm leading-6 text-content">
        <p className="whitespace-pre-wrap">{message.content}</p>
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
          <p className="text-sm leading-6 text-content">{message.content}</p>
          {message.error.correlationId && (
            <p className="mt-1 break-all font-mono text-[11px] text-muted">
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
      <div className="flex items-center gap-2 text-xs font-semibold text-content">
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
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [draft, setDraft] = useState("");
  const nextMessageId = useRef(0);
  const historyRef = useRef<HTMLDivElement>(null);
  const mutation = useMutation({ mutationFn: askAIQuestion, retry: false });
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
    if (!question || question.length > 1000 || mutation.isPending) return;
    const userMessageId = addUserMessage
      ? nextMessageId.current++
      : retryAttempt?.userMessageId;
    const assistantMessageId = addUserMessage
      ? nextMessageId.current++
      : retryAttempt?.assistantMessageId;
    if (userMessageId === undefined || assistantMessageId === undefined) return;
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
      setDraft("");
    }

    try {
      const response = await mutation.mutateAsync({
        contract_version: "v1",
        question,
        context: context.slice(-3),
      });
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
      setMessages((current) =>
        updateConversationInteraction(
          current,
          userMessageId,
          assistantMessage,
          retryAttempt !== undefined,
        ),
      );
    } catch (error) {
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
          current,
          userMessageId,
          assistantMessage,
          retryAttempt !== undefined,
        ),
      );
    }
  }

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    void send(draft, conversationContext, true);
  }

  function handleComposerKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      event.currentTarget.form?.requestSubmit();
    }
  }

  function startNewConversation() {
    if (mutation.isPending) return;
    setMessages([]);
    setDraft("");
    mutation.reset();
  }

  return (
    <section
      aria-labelledby="assistant-heading"
      className="mx-auto flex h-full min-h-0 w-full max-w-[960px] flex-col gap-3 rounded-[20px] border border-divider bg-surface p-3 lg:max-h-[800px] lg:gap-4 lg:p-6"
    >
      <header className="flex min-h-12 shrink-0 items-center justify-between gap-3 lg:-mr-0.5 [@media(max-height:480px)]:min-h-0">
        <div className="flex items-center gap-2.5">
          <span className="flex size-9 items-center justify-center rounded-full bg-brand/10 text-brand">
            <MessageCircle aria-hidden="true" className="size-4" />
          </span>
          <div>
            <p className="font-heading text-base leading-6 font-semibold lg:text-lg">
              Assistente Grid 360
            </p>
            <p className="text-xs text-muted">
              Perguntas sobre os cenários disponíveis
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
              <span className="mx-auto flex size-12 items-center justify-center rounded-2xl bg-brand/10 text-brand">
                <Sparkles aria-hidden="true" className="size-6" />
              </span>
              <h1
                id="assistant-heading"
                className="font-heading text-[26px] leading-[34px] font-semibold lg:text-[32px] lg:leading-10 lg:tracking-[-0.64px]"
              >
                O que você quer investigar?
              </h1>
              <p className="mx-auto max-w-[560px] text-sm leading-[22px] text-muted">
                Explore consumo, receita e continuidade. As respostas desta
                versão usam cenários artificiais e explicam o período, o recorte
                e o fundamento.
              </p>
            </div>
            <div className="grid gap-2 sm:grid-cols-2">
              {SUGGESTIONS.map((suggestion) => (
                <button
                  key={suggestion}
                  type="button"
                  onClick={() => void send(suggestion, [], true)}
                  disabled={mutation.isPending}
                  className="group flex min-h-16 items-start gap-3 rounded-xl border border-divider bg-canvas/50 p-3 text-left text-sm leading-5 text-content transition-colors hover:border-brand/50 hover:bg-surface-hover focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand disabled:opacity-60"
                >
                  <CircleHelp
                    aria-hidden="true"
                    className="mt-0.5 size-4 shrink-0 text-brand"
                  />
                  <span>{suggestion}</span>
                </button>
              ))}
            </div>
            <p className="flex items-start justify-center gap-2 text-center text-xs leading-5 text-muted">
              <Info aria-hidden="true" className="mt-0.5 size-3.5 shrink-0" />
              Os cenários são fictícios. A conversa fica apenas nesta tela e não
              é salva.
            </p>
          </div>
        ) : (
          <>
            <h1 id="assistant-heading" className="sr-only">
              Conversa com o Assistente Grid 360
            </h1>
            {messages.map((message) => (
              <MessageCard
                key={message.id}
                message={message}
                onRetry={(request) =>
                  void send(request.question, request.context, false, request)
                }
              />
            ))}
            {mutation.isPending && (
              <div
                role="status"
                className="flex w-fit items-center gap-2 rounded-xl border border-divider px-4 py-3 text-sm text-muted"
              >
                <LoaderCircle
                  aria-hidden="true"
                  className="size-4 animate-spin"
                />
                Analisando a pergunta e consultando evidências…
              </div>
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
            id="assistant-question"
            name="question"
            rows={2}
            maxLength={1000}
            placeholder="Pergunte sobre consumo, receita ou continuidade…"
            value={draft}
            onChange={(event) => setDraft(event.target.value)}
            onKeyDown={handleComposerKeyDown}
            disabled={mutation.isPending}
            className="max-h-36 min-h-12 flex-1 resize-y bg-transparent px-2 py-2 text-sm leading-5 text-content outline-none placeholder:text-muted disabled:opacity-60"
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
        <div className="mt-2 flex flex-wrap items-center justify-between gap-x-3 gap-y-1 px-1 text-[11px] leading-4 text-muted">
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
    </section>
  );
}
