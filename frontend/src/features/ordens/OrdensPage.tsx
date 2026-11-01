import { useEffect, useRef, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, ArrowRight } from "lucide-react";
import { Link, useSearchParams } from "react-router-dom";
import type { Order } from "@/shared/api/orders";
import { getOrderDetail, searchOrders } from "@/shared/api/orders";
import Button from "@/shared/ui/Button";
import OrderActionsDialog from "./OrderActionsDialog";
import OrderFoundationsDialog from "./OrderFoundationsDialog";
import OrderFilters from "./OrderFilters";
import OrdersTable from "./OrdersTable";
import { formatOrderCode, parseOrdersQuery } from "./ordens-query";
import { useOrderAccess, useSession } from "@/shared/auth/useSession";

export default function OrdensPage() {
  const session = useSession();
  const access = useOrderAccess();
  const [params, setParams] = useSearchParams();
  const [selectedOrder, setSelectedOrder] = useState<Order | null>(null);
  const [actionsOpen, setActionsOpen] = useState(false);
  const [foundationsOpen, setFoundationsOpen] = useState(false);
  const [actionSession, setActionSession] = useState(0);
  const [savedFeedback, setSavedFeedback] = useState<string | null>(null);
  const actionTriggerRef = useRef<HTMLElement>(null);
  const backToQueueRef = useRef<HTMLAnchorElement>(null);
  const foundationsTriggerRef = useRef<HTMLButtonElement>(null);
  const deepLinkHandledRef = useRef<number | null>(null);
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
    enabled:
      parsed !== null && (!session.configured || access.data?.canRead === true),
    queryFn: ({ signal }) => searchOrders(request, signal),
  });
  const requestedOrder = useQuery({
    queryKey: ["orders", "detail", parsed?.orderId],
    enabled:
      parsed?.orderId !== null &&
      parsed?.orderId !== undefined &&
      (!session.configured || access.data?.canRead === true),
    queryFn: ({ signal }) => getOrderDetail(parsed!.orderId!, signal),
  });
  const visibleOrders = orders.data?.items ?? [];

  function openActions(order: Order, trigger?: HTMLButtonElement) {
    actionTriggerRef.current = trigger ?? null;
    setActionSession((session) => session + 1);
    setSelectedOrder(order);
    setSavedFeedback(null);
    setFoundationsOpen(false);
    setActionsOpen(true);
  }

  useEffect(() => {
    const orderId = parsed?.orderId ?? null;
    if (orderId === null) {
      deepLinkHandledRef.current = null;
      return;
    }
    if (
      !requestedOrder.data ||
      requestedOrder.data.id !== orderId ||
      deepLinkHandledRef.current === orderId
    ) {
      return;
    }
    deepLinkHandledRef.current = orderId;
    actionTriggerRef.current = backToQueueRef.current;
    setActionSession((session) => session + 1);
    setSelectedOrder(requestedOrder.data);
    setSavedFeedback(null);
    setFoundationsOpen(false);
    setActionsOpen(true);
  }, [parsed?.orderId, requestedOrder.data]);

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
          ref={backToQueueRef}
          className="inline-flex min-h-11 items-center gap-2 rounded-lg border border-control bg-surface px-4 text-sm font-medium text-content hover:bg-surface-hover focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand"
          to="/inspecoes"
        >
          <ArrowLeft size={16} aria-hidden="true" />
          Voltar à fila
        </Link>
      </nav>

      {session.configured && access.isPending ? (
        <p role="status" className="text-sm text-muted">
          Verificando permissao para consultar ordens...
        </p>
      ) : null}
      {session.configured && access.data && !access.data.canRead ? (
        <p
          role="alert"
          className="rounded-xl border border-border bg-surface p-5 text-sm"
        >
          Sua conta nao tem permissao para consultar ordens.
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

      {requestedOrder.isError ? (
        <div
          role="alert"
          className="rounded-xl border border-border bg-surface p-5"
        >
          <p>Não foi possível localizar a ordem solicitada pelo link.</p>
          <Button
            className="mt-3"
            variant="outline"
            onClick={() => void requestedOrder.refetch()}
          >
            Tentar novamente
          </Button>
        </div>
      ) : null}
      {requestedOrder.isPending && parsed?.orderId != null ? (
        <p role="status" className="text-sm text-muted">
          Consultando {formatOrderCode(parsed.orderId)}…
        </p>
      ) : null}

      {!invalid && parsed ? (
        <>
          <OrderFilters params={params} filters={parsed} onChange={setParams} />

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
                <OrdersTable
                  orders={visibleOrders}
                  onSelect={openActions}
                  onFoundations={openFoundations}
                />
              ) : orders.data.pagination.total > 0 ? (
                <div className="rounded-xl border border-border bg-surface p-6 text-sm text-muted">
                  Esta página não contém ordens. O total do recorte é{" "}
                  {orders.data.pagination.total}; volte a uma página anterior.
                </div>
              ) : (
                <div className="grid gap-3 rounded-xl border border-border bg-surface p-6 text-sm text-muted">
                  <p>
                    {parsed.ucId ||
                    parsed.status ||
                    parsed.priority ||
                    parsed.hasResult !== null
                      ? "Nenhuma ordem corresponde aos filtros aplicados."
                      : "Nenhuma ordem foi cadastrada ainda."}
                  </p>
                  <p>
                    Ordens são criadas a partir de uma suspeita selecionada na
                    fila de inspeção.
                  </p>
                  <div className="flex flex-wrap gap-3">
                    <Link
                      className="min-h-11 inline-flex items-center underline underline-offset-4"
                      to="/inspecoes"
                    >
                      Ir para a fila de inspeção
                    </Link>
                    {parsed.ucId ||
                    parsed.status ||
                    parsed.priority ||
                    parsed.hasResult !== null ? (
                      <Link
                        className="min-h-11 inline-flex items-center underline underline-offset-4"
                        to="/ordens"
                      >
                        Limpar recorte
                      </Link>
                    ) : null}
                  </div>
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
            </>
          ) : null}
        </>
      ) : null}

      {selectedOrder ? (
        <>
          <OrderActionsDialog
            key={`actions-${selectedOrder.id}-${actionSession}`}
            order={selectedOrder}
            canEdit={!session.configured || access.data?.canWrite === true}
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
