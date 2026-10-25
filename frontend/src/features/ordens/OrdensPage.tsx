import { useRef, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, ArrowRight } from "lucide-react";
import { Link, useSearchParams } from "react-router-dom";
import type { Order } from "@/shared/api/orders";
import { searchOrders } from "@/shared/api/orders";
import Button from "@/shared/ui/Button";
import OrderActionsDialog from "./OrderActionsDialog";
import OrderFoundationsDialog from "./OrderFoundationsDialog";
import OrdersTable from "./OrdersTable";
import {
  formatOrderCode,
  formatOrderDate,
  orderPriorityLabel,
  orderStatusLabel,
  parseOrdersQuery,
} from "./ordens-query";

export default function OrdensPage() {
  const [params, setParams] = useSearchParams();
  const [selectedOrder, setSelectedOrder] = useState<Order | null>(null);
  const [actionsOpen, setActionsOpen] = useState(false);
  const [foundationsOpen, setFoundationsOpen] = useState(false);
  const [actionSession, setActionSession] = useState(0);
  const [savedFeedback, setSavedFeedback] = useState<string | null>(null);
  const actionTriggerRef = useRef<HTMLButtonElement>(null);
  const foundationsTriggerRef = useRef<HTMLButtonElement>(null);
  const queryClient = useQueryClient();

  let parsed: ReturnType<typeof parseOrdersQuery> | null = null;
  let invalid: string | null = null;
  try {
    parsed = parseOrdersQuery(params);
  } catch (error) {
    invalid = error instanceof Error ? error.message : "Filtros inválidos.";
  }

  const request = parsed?.request ?? "";
  const orders = useQuery({
    queryKey: ["orders", "list", request],
    enabled: parsed !== null,
    queryFn: ({ signal }) => searchOrders(request, signal),
  });
  const firstVisibleOrder = orders.data?.items[0] ?? null;
  const visibleOrders = orders.data?.items ?? [];
  const appliedFilters = parsed
    ? [
        parsed.ucId ? `UC ${parsed.ucId}` : null,
        parsed.status ? `Estado ${orderStatusLabel(parsed.status)}` : null,
        parsed.priority
          ? `Prioridade ${orderPriorityLabel(parsed.priority)}`
          : null,
        parsed.pageSize !== 20 ? `${parsed.pageSize} por página` : null,
      ].filter((value): value is string => value !== null)
    : [];
  const lastUpdated = visibleOrders.reduce<string | null>((latest, order) => {
    if (!Number.isFinite(new Date(order.updated_at).getTime())) return latest;
    if (
      !latest ||
      new Date(order.updated_at).getTime() > new Date(latest).getTime()
    ) {
      return order.updated_at;
    }
    return latest;
  }, null);

  function openActions(order: Order, trigger: HTMLButtonElement) {
    actionTriggerRef.current = trigger;
    setActionSession((session) => session + 1);
    setSelectedOrder(order);
    setSavedFeedback(null);
    setFoundationsOpen(false);
    setActionsOpen(true);
  }

  function openFoundations(order: Order, trigger: HTMLButtonElement) {
    foundationsTriggerRef.current = trigger;
    setSelectedOrder(order);
    setActionsOpen(false);
    setFoundationsOpen(true);
  }

  function changePage(page: number) {
    if (!parsed || page < 1) return;
    const next = new URLSearchParams(params);
    if (page === 1) next.delete("page");
    else next.set("page", String(page));
    setParams(next);
  }

  function handleSaved(order: Order, message: string) {
    setSelectedOrder(order);
    setSavedFeedback(message);
    void queryClient.invalidateQueries({ queryKey: ["orders"] });
  }

  return (
    <div className="mt-5 space-y-5 pb-6 lg:mt-6 lg:space-y-6">
      <nav aria-label="Navegação das ordens">
        <Link
          className="inline-flex min-h-11 items-center gap-2 rounded-lg border border-control bg-surface px-4 text-sm font-medium text-content hover:bg-surface-hover focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand"
          to="/inspecoes"
        >
          <ArrowLeft size={16} aria-hidden="true" />
          Voltar à fila
        </Link>
      </nav>

      <div>
        <p className="text-xs leading-[18px] text-muted">
          Ambiente demonstrativo · atualização das ordens neste recorte:{" "}
          {formatOrderDate(lastUpdated)}
        </p>
      </div>

      {appliedFilters.length > 0 ? (
        <p className="text-xs leading-[18px] text-muted">
          Recorte aplicado · {appliedFilters.join(" · ")}
        </p>
      ) : null}

      {invalid ? (
        <div
          role="alert"
          className="rounded-xl border border-border bg-surface p-5"
        >
          <p>{invalid}</p>
          <Button
            className="mt-3"
            variant="outline"
            onClick={() => setParams(new URLSearchParams())}
          >
            Limpar filtros
          </Button>
        </div>
      ) : null}

      {!invalid && parsed ? (
        <>
          {orders.isPending ? (
            <div
              role="status"
              className="rounded-xl border border-border bg-surface px-5 py-10 text-sm text-muted"
            >
              Consultando ordens…
            </div>
          ) : null}

          {orders.isError ? (
            <div
              role="alert"
              className="rounded-xl border border-border bg-surface p-5"
            >
              <p>
                {orders.data
                  ? "Não foi possível atualizar as ordens. A última consulta válida continua exibida e pode estar desatualizada."
                  : "Não foi possível consultar as ordens. Tente novamente."}
              </p>
              <Button
                className="mt-3"
                variant="outline"
                onClick={() => void orders.refetch()}
              >
                Tentar novamente
              </Button>
            </div>
          ) : null}

          {orders.isFetching && !orders.isPending ? (
            <p role="status" className="text-sm text-muted">
              Atualizando ordens; os dados visíveis correspondem à última
              consulta válida.
            </p>
          ) : null}

          {orders.data ? (
            <>
              {savedFeedback ? (
                <div
                  role="status"
                  className="space-y-1 rounded-lg bg-[var(--status-success-bg)] p-4 text-sm leading-5 text-[var(--status-success-text)]"
                >
                  <p className="font-medium">Ação concluída</p>
                  <p>{savedFeedback}</p>
                </div>
              ) : null}
              {visibleOrders.length > 0 ? (
                <OrdersTable orders={visibleOrders} onSelect={openActions} />
              ) : orders.data.pagination.total > 0 ? (
                <div className="rounded-xl border border-border bg-surface p-6 text-sm text-muted">
                  Esta página não contém ordens. O total do recorte é{" "}
                  {orders.data.pagination.total}; volte a uma página anterior.
                </div>
              ) : (
                <div className="rounded-xl border border-border bg-surface p-6 text-sm text-muted">
                  Nenhuma ordem encontrada para os filtros aplicados.
                </div>
              )}

              <p className="sr-only" aria-live="polite">
                {orders.data.pagination.total} ordem(ns) no recorte. Página{" "}
                {orders.data.pagination.page} de{" "}
                {orders.data.pagination.total_pages}.
              </p>
              {orders.data.pagination.total_pages > 1 ||
              orders.data.pagination.page > 1 ? (
                <nav
                  aria-label="Paginação das ordens"
                  className="flex flex-wrap items-center justify-between gap-3"
                >
                  <Button
                    variant="outline"
                    leftIcon={<ArrowLeft size={16} aria-hidden="true" />}
                    disabled={orders.data.pagination.page <= 1}
                    onClick={() => changePage(orders.data!.pagination.page - 1)}
                  >
                    Anterior
                  </Button>
                  <span className="text-sm text-muted">
                    {orders.data.pagination.total} ordem(ns) · página{" "}
                    {orders.data.pagination.page}
                    {orders.data.pagination.total_pages > 0
                      ? ` de ${orders.data.pagination.total_pages}`
                      : " · sem páginas com resultados"}
                  </span>
                  <Button
                    variant="outline"
                    rightIcon={<ArrowRight size={16} aria-hidden="true" />}
                    disabled={
                      orders.data.pagination.page >=
                      orders.data.pagination.total_pages
                    }
                    onClick={() => changePage(orders.data!.pagination.page + 1)}
                  >
                    Próxima
                  </Button>
                </nav>
              ) : null}
              <section
                aria-label="Informações sobre o acompanhamento das ordens"
                className="space-y-5 lg:space-y-6"
              >
                <aside className="flex flex-col gap-1 rounded-lg bg-[var(--status-info-bg)] p-4 text-sm text-[var(--status-info-text)]">
                  <p className="font-medium">Acompanhamento operacional</p>
                  <p className="leading-[22px]">
                    Mudanças confirmadas ficam registradas nesta lista. Uma
                    suspeita orienta a inspeção e não comprova irregularidade.
                  </p>
                </aside>
              </section>

              <footer className="flex flex-col gap-2 text-xs text-muted sm:flex-row sm:items-start sm:gap-4">
                <p className="w-full sm:max-w-[600px]">
                  Fonte: ordens registradas no portal. Evidências da fila são
                  sintéticas, sem consulta à Gold.
                </p>
                <Button
                  ref={foundationsTriggerRef}
                  variant="ghost"
                  className="min-h-11 w-full justify-center underline decoration-border underline-offset-4 sm:w-auto sm:justify-start"
                  rightIcon={<ArrowRight size={14} aria-hidden="true" />}
                  disabled={!firstVisibleOrder}
                  aria-label={
                    firstVisibleOrder
                      ? `Ver fundamentos da ordem ${formatOrderCode(firstVisibleOrder.id)} da UC ${firstVisibleOrder.uc_id}`
                      : "Ver fundamentos da ordem"
                  }
                  onClick={(event) => {
                    if (firstVisibleOrder)
                      openFoundations(firstVisibleOrder, event.currentTarget);
                  }}
                >
                  {firstVisibleOrder
                    ? `Ver fundamentos · ${formatOrderCode(firstVisibleOrder.id)}`
                    : "Ver fundamentos"}
                </Button>
              </footer>
            </>
          ) : null}
        </>
      ) : null}

      {selectedOrder ? (
        <>
          <OrderActionsDialog
            key={`actions-${selectedOrder.id}-${actionSession}`}
            order={selectedOrder}
            open={actionsOpen}
            onClose={() => setActionsOpen(false)}
            triggerRef={actionTriggerRef}
            onSaved={handleSaved}
          />
          <OrderFoundationsDialog
            key={`foundations-${selectedOrder.id}`}
            order={selectedOrder}
            open={foundationsOpen}
            onClose={() => setFoundationsOpen(false)}
            triggerRef={foundationsTriggerRef}
          />
        </>
      ) : null}
    </div>
  );
}
