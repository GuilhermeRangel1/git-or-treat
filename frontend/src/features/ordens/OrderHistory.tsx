import { useQuery } from "@tanstack/react-query";
import { getOrderHistory, type OrderStatus } from "@/shared/api/orders";
import Button from "@/shared/ui/Button";
import { orderErrorMessage, orderStatusLabel } from "./order-actions";

const actionLabels = {
  CRIACAO: "Ordem criada",
  ATUALIZACAO_STATUS: "Estado atualizado",
  REGISTRO_RESULTADO: "Resultado registrado",
  CANCELAMENTO: "Ordem cancelada",
} as const;

const dateFormatter = new Intl.DateTimeFormat("pt-BR", {
  dateStyle: "short",
  timeStyle: "short",
  timeZone: "America/Recife",
});

function statusText(status: OrderStatus | null) {
  return status ? orderStatusLabel(status) : "Não informado";
}

export default function OrderHistory({ orderId }: { orderId: number }) {
  const history = useQuery({
    queryKey: ["orders", "history", orderId],
    queryFn: ({ signal }) => getOrderHistory(orderId, signal),
    enabled: Number.isSafeInteger(orderId) && orderId > 0,
    retry: false,
    staleTime: 0,
  });

  return (
    <section
      className="grid min-w-0 gap-3 border-t border-border pt-5"
      aria-labelledby="order-history-title"
    >
      <h3 id="order-history-title" className="text-base font-semibold">
        Histórico da ordem
      </h3>
      {history.isPending ? (
        <p role="status" className="text-sm text-muted">
          Consultando histórico…
        </p>
      ) : null}
      {history.isError ? (
        <div
          className="grid gap-3 rounded-lg p-4 text-sm"
          role="alert"
          style={errorStyle}
        >
          <p>{orderErrorMessage(history.error)}</p>
          <Button
            variant="neutral"
            size="sm"
            disabled={history.isFetching}
            onClick={() => void history.refetch()}
          >
            Tentar novamente o histórico
          </Button>
        </div>
      ) : null}
      {history.isFetching && !history.isPending && !history.isError ? (
        <p role="status" className="text-xs text-muted">
          Atualizando histórico…
        </p>
      ) : null}
      {history.data?.length === 0 ? (
        <p className="text-sm text-muted">
          Nenhum evento registrado para esta ordem.
        </p>
      ) : null}
      {history.data && history.data.length > 0 ? (
        <ol className="grid min-w-0 gap-3" aria-label="Eventos do histórico">
          {history.data.map((event) => (
            <li
              key={event.id}
              className="grid min-w-0 gap-1 rounded-lg border border-border bg-canvas p-3 text-sm"
            >
              <div className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1">
                <strong className="font-medium">
                  {actionLabels[event.action]}
                </strong>
                <time
                  className="text-xs text-muted"
                  dateTime={event.created_at}
                >
                  {dateFormatter.format(new Date(event.created_at))}
                </time>
              </div>
              <p className="text-muted">
                Estado: {statusText(event.previous_status)} →{" "}
                {statusText(event.new_status)}
              </p>
              {event.details ? (
                <p className="min-w-0 whitespace-pre-wrap [overflow-wrap:anywhere]">
                  {event.details}
                </p>
              ) : null}
              {event.notes ? (
                <p className="min-w-0 whitespace-pre-wrap [overflow-wrap:anywhere]">
                  Observação: {event.notes}
                </p>
              ) : null}
              <p className="min-w-0 whitespace-pre-wrap text-xs text-muted [overflow-wrap:anywhere]">
                Ator: {event.actor?.trim() || "Não informado"} · Versão:{" "}
                {event.order_version ?? "Não informada"}
              </p>
            </li>
          ))}
        </ol>
      ) : null}
    </section>
  );
}

const errorStyle = {
  backgroundColor: "var(--action-danger-bg)",
  color: "var(--action-danger-text)",
};
