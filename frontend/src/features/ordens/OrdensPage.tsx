import { Link, useSearchParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { searchOrders, orderStatuses } from "@/shared/api/orders";
import Button from "@/shared/ui/Button";

export default function OrdensPage() {
  const [params, setParams] = useSearchParams();
  const query = params.toString();
  const orders = useQuery({
    queryKey: ["orders", query],
    queryFn: ({ signal }) => searchOrders(query, signal),
  });
  const update = (key: string, value: string) => {
    const next = new URLSearchParams(params);
    if (value) next.set(key, value);
    else next.delete(key);
    if (key !== "page") next.delete("page");
    setParams(next);
  };
  return (
    <div className="space-y-5">
      <p className="text-sm text-muted">
        Ordens persistidas no banco operacional. As evidências da fila atual são
        sintéticas.
      </p>
      <div className="flex flex-wrap gap-4">
        <label>
          UC
          <input
            className="ml-2 rounded border border-control bg-surface p-2"
            maxLength={50}
            value={params.get("uc_id") ?? ""}
            onChange={(e) => update("uc_id", e.target.value)}
          />
        </label>
        <label>
          Estado
          <select
            className="ml-2 rounded border border-control bg-surface p-2"
            value={params.get("status") ?? ""}
            onChange={(e) => update("status", e.target.value)}
          >
            <option value="">Todos</option>
            {orderStatuses.map((s) => (
              <option key={s}>{s}</option>
            ))}
          </select>
        </label>
        <Button onClick={() => void orders.refetch()}>Atualizar ordens</Button>
        <Link className="self-center underline" to="/inspecoes">
          Voltar à fila
        </Link>
      </div>
      {orders.isPending && <p role="status">Consultando ordens…</p>}
      {orders.isError && (
        <p role="alert">
          Não foi possível consultar as ordens. {orders.error.message}
          {orders.data &&
            " Exibindo a última consulta válida; ela pode estar desatualizada."}
        </p>
      )}
      {orders.isFetching && !orders.isPending && (
        <p role="status">Atualizando a consulta…</p>
      )}
      {orders.data && (
        <>
          <p>
            {orders.data.pagination.total} ordem(ns) · página{" "}
            {orders.data.pagination.page}
          </p>
          {orders.data.items.length === 0 && (
            <p>Nenhuma ordem neste recorte.</p>
          )}
          <ul className="space-y-3">
            {orders.data.items.map((order) => (
              <li
                key={order.id}
                className="space-y-2 rounded-xl border border-border bg-surface p-4"
              >
                <h2 className="font-semibold">
                  Ordem {order.id} · {order.uc_id}
                </h2>
                <p>
                  Estado: {order.status} · Prioridade: {order.priority}
                </p>
                <p>{order.reason}</p>
                <p>Resultado: {order.result ?? "Não registrado"}</p>
                <p className="break-all text-xs text-muted">
                  Criada em {new Date(order.created_at).toLocaleString("pt-BR")}{" "}
                  · Referência:{" "}
                  {order.suspicion_reference ??
                    "Ordem anterior sem referência da fila"}
                </p>
              </li>
            ))}
          </ul>
          <div className="flex gap-3">
            <Button
              disabled={orders.data.pagination.page <= 1}
              onClick={() =>
                update("page", String(orders.data.pagination.page - 1))
              }
            >
              Anterior
            </Button>
            <Button
              disabled={
                orders.data.pagination.page >=
                orders.data.pagination.total_pages
              }
              onClick={() =>
                update("page", String(orders.data.pagination.page + 1))
              }
            >
              Próxima
            </Button>
          </div>
        </>
      )}
    </div>
  );
}
