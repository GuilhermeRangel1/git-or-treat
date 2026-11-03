import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Check,
  ChevronLeft,
  ChevronRight,
  MessageSquare,
  MoreHorizontal,
  Pencil,
  Trash2,
  X,
} from "lucide-react";
import Button from "@/shared/ui/Button";
import {
  deleteConversation,
  listConversations,
  renameConversation,
  type ConversationSummary,
} from "./history";

export default function ConversationHistory({
  actor,
  activeId,
  onOpen,
  onDeleted,
}: {
  actor: string;
  activeId: string | null;
  onOpen: (id: string) => Promise<void>;
  onDeleted: (id: string) => void;
}) {
  const [offset, setOffset] = useState(0);
  const [editing, setEditing] = useState<ConversationSummary | null>(null);
  const [title, setTitle] = useState("");
  const [removing, setRemoving] = useState<ConversationSummary | null>(null);
  const [actionsFor, setActionsFor] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const client = useQueryClient();
  const query = useQuery({
    queryKey: ["ai-conversations", actor, offset],
    queryFn: ({ signal }) => listConversations(offset, signal),
    retry: false,
    staleTime: 0,
  });

  async function perform(action: () => Promise<void>) {
    setBusy(true);
    setError(null);
    try {
      await action();
      await client.invalidateQueries({ queryKey: ["ai-conversations", actor] });
    } catch {
      setError(
        "Não foi possível concluir. Atualize a lista e tente novamente.",
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <section
      aria-labelledby="assistant-conversations-heading"
      className="flex h-full min-h-0 flex-col overflow-hidden"
    >
      <div className="mb-3 flex items-center gap-2">
        <MessageSquare aria-hidden="true" className="size-4 text-muted" />
        <h2
          id="assistant-conversations-heading"
          className="text-sm font-semibold uppercase tracking-wider text-muted"
        >
          Conversas
        </h2>
      </div>
      {(error || query.isError) && (
        <div
          role="alert"
          className="mb-3 rounded-lg border border-divider p-2 text-sm"
        >
          <p>{error ?? "Não foi possível carregar as conversas."}</p>
          <Button
            variant="ghost"
            size="sm"
            className="mt-1 !px-1"
            onClick={() => void query.refetch()}
          >
            Atualizar lista
          </Button>
        </div>
      )}
      {query.isPending && (
        <p role="status" className="text-sm text-muted">
          Carregando conversas…
        </p>
      )}
      {query.data?.items.length === 0 && (
        <p className="rounded-xl border border-dashed border-divider p-3 text-sm leading-5 text-muted">
          Suas conversas aparecerão aqui depois da primeira pergunta.
        </p>
      )}

      <ul className="assistant-conversation-list min-h-0 space-y-3 overflow-y-auto overscroll-contain">
        {query.data?.items.map((row) => {
          const isEditing = editing?.id === row.id;
          const isRemoving = removing?.id === row.id;
          const titleInputId = `conversation-title-${row.id}`;

          return (
            <li
              key={row.id}
              className={`rounded-2xl border p-3 ${
                activeId === row.id
                  ? "border-brand/60 bg-brand/5"
                  : "border-divider bg-canvas/50"
              }`}
            >
              <div className="flex items-start gap-2">
                <Button
                  variant="ghost"
                  disabled={busy || isEditing || isRemoving}
                  aria-current={activeId === row.id ? "page" : undefined}
                  className="h-auto min-w-0 flex-1 justify-start !whitespace-normal !rounded-lg !px-2.5 !py-2 text-left text-sm leading-5"
                  onClick={() => void perform(() => onOpen(row.id))}
                >
                  <span className="line-clamp-3 break-words">{row.title}</span>
                </Button>
                {!isEditing && !isRemoving && (
                  <Button
                    variant="ghost"
                    size="sm"
                    className="!size-8 !p-0"
                    disabled={busy}
                    aria-label={`Opções da conversa ${row.title}`}
                    aria-expanded={actionsFor === row.id}
                    title="Opções da conversa"
                    onClick={() =>
                      setActionsFor((current) =>
                        current === row.id ? null : row.id,
                      )
                    }
                  >
                    <MoreHorizontal aria-hidden="true" className="size-4" />
                  </Button>
                )}
              </div>
              <p className="mt-1 px-2 pb-1.5 text-xs leading-4 text-muted">
                {new Date(row.updated_at).toLocaleDateString("pt-BR", {
                  day: "2-digit",
                  month: "short",
                })}{" "}
                · {row.message_count} mensagens
              </p>

              {isEditing ? (
                <form
                  className="space-y-2 border-t border-divider px-2 pt-2"
                  aria-label={`Renomear conversa ${row.title}`}
                  onSubmit={(event) => {
                    event.preventDefault();
                    void perform(async () => {
                      await renameConversation(row, title);
                      setEditing(null);
                    });
                  }}
                >
                  <label htmlFor={titleInputId} className="sr-only">
                    Nome da conversa
                  </label>
                  <input
                    id={titleInputId}
                    className="w-full rounded-lg border border-divider bg-surface px-2 py-1.5 text-sm text-content"
                    value={title}
                    maxLength={120}
                    required
                    autoFocus
                    onChange={(event) => setTitle(event.target.value)}
                  />
                  <div className="flex gap-1">
                    <Button
                      type="submit"
                      variant="ghost"
                      size="sm"
                      disabled={busy || !title.trim()}
                      leftIcon={
                        <Check aria-hidden="true" className="size-3.5" />
                      }
                    >
                      Salvar
                    </Button>
                    <Button
                      type="button"
                      variant="ghost"
                      size="sm"
                      disabled={busy}
                      leftIcon={<X aria-hidden="true" className="size-3.5" />}
                      onClick={() => setEditing(null)}
                    >
                      Cancelar
                    </Button>
                  </div>
                </form>
              ) : isRemoving ? (
                <div
                  role="group"
                  aria-label={`Confirmar exclusão da conversa ${row.title}`}
                  className="space-y-2 border-t border-divider px-2 pt-2"
                >
                  <p className="text-xs leading-4 text-content">
                    Apagar esta conversa e suas mensagens? Esta ação não pode
                    ser desfeita.
                  </p>
                  <div className="flex flex-wrap gap-1">
                    <Button
                      variant="danger"
                      size="sm"
                      disabled={busy}
                      onClick={() =>
                        void perform(async () => {
                          await deleteConversation(row.id);
                          onDeleted(row.id);
                          setRemoving(null);
                        })
                      }
                    >
                      Confirmar
                    </Button>
                    <Button
                      variant="ghost"
                      size="sm"
                      disabled={busy}
                      onClick={() => setRemoving(null)}
                    >
                      Cancelar
                    </Button>
                  </div>
                </div>
              ) : (
                actionsFor === row.id && (
                  <div
                    id={`conversation-actions-${row.id}`}
                    role="group"
                    aria-label={`Ações da conversa ${row.title}`}
                    className="mt-2 grid grid-cols-2 gap-2 border-t border-divider px-2 pt-2"
                  >
                    <Button
                      variant="ghost"
                      size="sm"
                      className="!h-9 !w-full !px-2 text-xs"
                      disabled={busy}
                      aria-label={`Renomear ${row.title}`}
                      leftIcon={
                        <Pencil aria-hidden="true" className="size-3.5" />
                      }
                      onClick={() => {
                        setEditing(row);
                        setTitle(row.title);
                        setRemoving(null);
                        setActionsFor(null);
                      }}
                    >
                      Renomear
                    </Button>
                    <Button
                      variant="ghost"
                      size="sm"
                      className="!h-9 !w-full !px-2 text-xs"
                      disabled={busy}
                      aria-label={`Excluir ${row.title}`}
                      leftIcon={
                        <Trash2 aria-hidden="true" className="size-3.5" />
                      }
                      onClick={() => {
                        setRemoving(row);
                        setEditing(null);
                        setActionsFor(null);
                      }}
                    >
                      Excluir
                    </Button>
                  </div>
                )
              )}
            </li>
          );
        })}
      </ul>

      {(offset > 0 || query.data?.hasMore) && (
        <div className="mt-2 flex justify-between gap-1 border-t border-divider pt-2">
          {offset > 0 ? (
            <Button
              variant="ghost"
              size="sm"
              className="!px-2 text-xs"
              disabled={busy}
              onClick={() => setOffset(Math.max(0, offset - 50))}
              leftIcon={<ChevronLeft aria-hidden="true" className="size-3.5" />}
            >
              Mais recentes
            </Button>
          ) : (
            <span />
          )}
          {query.data?.hasMore && (
            <Button
              variant="ghost"
              size="sm"
              className="!px-2 text-xs"
              disabled={busy}
              rightIcon={
                <ChevronRight aria-hidden="true" className="size-3.5" />
              }
              onClick={() => setOffset(offset + 50)}
            >
              Mais antigas
            </Button>
          )}
        </div>
      )}
    </section>
  );
}
