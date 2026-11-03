import { useRef, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { History } from "lucide-react";
import Button from "@/shared/ui/Button";
import Modal from "@/shared/ui/Modal";
import {
  deleteConversation,
  listConversations,
  renameConversation,
  type ConversationSummary,
} from "./history";

export default function ConversationHistory({
  actor,
  onOpen,
  onDeleted,
}: {
  actor: string;
  onOpen: (id: string) => Promise<void>;
  onDeleted: (id: string) => void;
}) {
  const [open, setOpen] = useState(false);
  const [offset, setOffset] = useState(0);
  const [editing, setEditing] = useState<ConversationSummary | null>(null);
  const [title, setTitle] = useState("");
  const [removing, setRemoving] = useState<ConversationSummary | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const trigger = useRef<HTMLButtonElement>(null);
  const client = useQueryClient();
  const query = useQuery({
    queryKey: ["ai-conversations", actor, offset],
    enabled: open,
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
    <>
      <Button
        ref={trigger}
        variant="ghost"
        size="sm"
        leftIcon={<History className="size-4" aria-hidden="true" />}
        onClick={() => setOpen(true)}
      >
        Conversas
      </Button>
      <Modal
        open={open}
        onClose={() => !busy && setOpen(false)}
        triggerRef={trigger}
        title="Suas conversas"
        description="Privadas e salvas por 30 dias após a última mensagem."
        closeLabel="Fechar conversas"
        size="sm"
        header="sticky"
      >
        <div className="space-y-4 p-5">
          {(error || query.isError) && (
            <p role="alert" className="text-brand">
              {error ?? "Não foi possível carregar suas conversas."}{" "}
              <Button variant="ghost" onClick={() => void query.refetch()}>
                Atualizar lista
              </Button>
            </p>
          )}
          {query.isPending && <p role="status">Carregando conversas…</p>}
          {query.data?.items.length === 0 && (
            <p>Nenhuma conversa salva. Envie uma pergunta para começar.</p>
          )}
          <ul className="space-y-3">
            {query.data?.items.map((row) => (
              <li key={row.id} className="rounded-xl border border-divider p-3">
                <Button
                  variant="ghost"
                  disabled={busy}
                  className="max-w-full break-words whitespace-normal text-left"
                  onClick={() =>
                    void perform(async () => {
                      await onOpen(row.id);
                      setOpen(false);
                    })
                  }
                >
                  {row.title}
                </Button>
                <p className="text-sm text-muted">
                  {new Date(row.updated_at).toLocaleString("pt-BR", {
                    dateStyle: "short",
                    timeStyle: "short",
                  })}{" "}
                  · {row.message_count} mensagens
                </p>
                <div className="flex gap-2">
                  <Button
                    variant="ghost"
                    size="sm"
                    disabled={busy}
                    onClick={() => {
                      setEditing(row);
                      setTitle(row.title);
                      setRemoving(null);
                    }}
                  >
                    Renomear
                  </Button>
                  <Button
                    variant="ghost"
                    size="sm"
                    disabled={busy}
                    onClick={() => {
                      setRemoving(row);
                      setEditing(null);
                    }}
                  >
                    Excluir
                  </Button>
                </div>
              </li>
            ))}
          </ul>
          {editing && (
            <form
              className="space-y-2"
              onSubmit={(event) => {
                event.preventDefault();
                void perform(async () => {
                  await renameConversation(editing, title);
                  setEditing(null);
                });
              }}
            >
              <label className="block" htmlFor="conversation-title">
                Nome da conversa
              </label>
              <input
                id="conversation-title"
                className="w-full rounded-lg border border-divider bg-surface p-2"
                value={title}
                maxLength={120}
                required
                onChange={(e) => setTitle(e.target.value)}
              />
              <Button type="submit" disabled={busy || !title.trim()}>
                Salvar nome
              </Button>
              <Button
                variant="ghost"
                type="button"
                onClick={() => setEditing(null)}
              >
                Cancelar
              </Button>
            </form>
          )}
          {removing && (
            <div
              role="group"
              aria-label="Confirmar exclusão"
              className="space-y-2 rounded-xl border border-divider p-3"
            >
              <p>
                Excluir esta conversa? As mensagens serão apagadas e não poderão
                ser recuperadas.
              </p>
              <Button
                disabled={busy}
                onClick={() =>
                  void perform(async () => {
                    await deleteConversation(removing.id);
                    onDeleted(removing.id);
                    setRemoving(null);
                  })
                }
              >
                Confirmar exclusão
              </Button>
              <Button
                variant="ghost"
                disabled={busy}
                onClick={() => setRemoving(null)}
              >
                Cancelar
              </Button>
            </div>
          )}
          <div className="flex gap-2">
            <Button
              variant="ghost"
              disabled={busy || offset === 0}
              onClick={() => setOffset(Math.max(0, offset - 50))}
            >
              Anteriores
            </Button>
            <Button
              variant="ghost"
              disabled={busy || !query.data?.hasMore}
              onClick={() => setOffset(offset + 50)}
            >
              Próximas
            </Button>
          </div>
        </div>
      </Modal>
    </>
  );
}
