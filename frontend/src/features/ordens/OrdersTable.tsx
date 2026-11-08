import { Check, ClipboardCheck, FileSearch, History } from "lucide-react";
import type { MouseEvent } from "react";
import type { Order, OrderStatus } from "@/shared/api/orders";
import Button from "@/shared/ui/Button";
import { isOrderFinal } from "./order-actions";
import { formatOrderCode, orderStatusLabel } from "./ordens-query";

type OrdersTableProps = {
  orders: Order[];
  onSelect: (order: Order, trigger: HTMLButtonElement) => void;
  onFoundations: (order: Order, trigger: HTMLButtonElement) => void;
};

const rowActionClass =
  "inline-flex min-h-11 items-center gap-1 rounded-md py-2 pl-0 pr-2 text-sm font-medium text-content underline decoration-border underline-offset-4 hover:decoration-content focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand";

function orderAction(status: OrderStatus) {
  if (isOrderFinal(status)) return { label: "Ver histórico", Icon: History };
  return status === "PENDENTE"
    ? { label: "Iniciar ordem", Icon: ClipboardCheck }
    : { label: "Registrar resultado", Icon: Check };
}

function OrderActionsButton({
  order,
  onSelect,
}: {
  order: Order;
  onSelect: OrdersTableProps["onSelect"];
}) {
  const { label, Icon } = orderAction(order.status);
  return (
    <Button
      variant="secondary"
      size="sm"
      className="min-h-11 w-full whitespace-nowrap text-sm! md:min-h-9 md:w-44"
      leftIcon={<Icon size={16} aria-hidden="true" />}
      onClick={(event: MouseEvent<HTMLButtonElement>) =>
        onSelect(order, event.currentTarget)
      }
      aria-label={`${label} ${formatOrderCode(order.id)}`}
    >
      {label}
    </Button>
  );
}

function FoundationsButton({
  order,
  onFoundations,
}: {
  order: Order;
  onFoundations: OrdersTableProps["onFoundations"];
}) {
  return (
    <button
      type="button"
      className={rowActionClass}
      onClick={(event: MouseEvent<HTMLButtonElement>) =>
        onFoundations(order, event.currentTarget)
      }
      aria-label={`Ver fundamentos da ordem ${formatOrderCode(order.id)} da UC ${order.uc_id}`}
    >
      Ver fundamentos <FileSearch size={15} aria-hidden="true" />
    </button>
  );
}

export default function OrdersTable({
  orders,
  onSelect,
  onFoundations,
}: OrdersTableProps) {
  return (
    <section aria-label="Ordens encontradas">
      <div className="hidden overflow-x-auto rounded-xl bg-surface p-4 md:block">
        {/* Grid para dividir a sobra por igual entre as colunas; os roles preservam a semântica que display: grid/contents pode remover. */}
        <table
          role="table"
          className="grid w-full auto-rows-[minmax(3.5rem,auto)] grid-cols-[auto_auto_auto_fit-content(16rem)_auto_auto] grid-rows-[2.75rem] items-center justify-between gap-x-4 text-left"
        >
          <thead
            role="rowgroup"
            className="contents font-sans text-xs leading-[18px] text-muted"
          >
            <tr role="row" className="contents">
              <th scope="col" role="columnheader" className="font-normal">
                Ordem
              </th>
              <th scope="col" role="columnheader" className="font-normal">
                Unidade consumidora
              </th>
              <th scope="col" role="columnheader" className="font-normal">
                Estado
              </th>
              <th scope="col" role="columnheader" className="font-normal">
                Resultado
              </th>
              <th scope="col" role="columnheader" className="font-normal">
                Ações
              </th>
              <th scope="col" role="columnheader" className="font-normal">
                Fundamentos
              </th>
            </tr>
          </thead>
          <tbody role="rowgroup" className="contents text-sm leading-[22px]">
            {orders.map((order) => (
              <tr key={order.id} role="row" className="contents">
                <th
                  scope="row"
                  role="rowheader"
                  className="whitespace-nowrap py-3 font-medium"
                >
                  {formatOrderCode(order.id)}
                </th>
                <td role="cell" className="break-words py-3">
                  {order.uc_id}
                </td>
                <td role="cell" className="py-3">
                  <span>{orderStatusLabel(order.status)}</span>
                </td>
                <td role="cell" className="break-words py-3">
                  {order.result?.trim() ? (
                    <span
                      className="line-clamp-2 [overflow-wrap:anywhere]"
                      title={order.result.trim()}
                    >
                      {order.result.trim()}
                    </span>
                  ) : (
                    "Não registrado"
                  )}
                </td>
                <td role="cell" className="py-1">
                  <OrderActionsButton order={order} onSelect={onSelect} />
                </td>
                <td role="cell" className="py-1">
                  <FoundationsButton
                    order={order}
                    onFoundations={onFoundations}
                  />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <ul className="space-y-3 md:hidden">
        {orders.map((order) => (
          <li
            key={order.id}
            className="flex flex-col gap-3 rounded-xl border border-divider bg-surface p-4"
          >
            <div>
              <p className="text-sm leading-5 text-muted">Ordem</p>
              <h2 className="font-heading text-lg leading-[26px] font-semibold">
                {formatOrderCode(order.id)}
              </h2>
            </div>
            <dl className="grid grid-cols-2 gap-3 text-sm">
              <div className="min-w-0">
                <dt className="text-muted">Unidade consumidora</dt>
                <dd className="break-words leading-[22px]">{order.uc_id}</dd>
              </div>
              <div className="min-w-0">
                <dt className="text-muted">Estado</dt>
                <dd className="leading-[22px]">
                  {orderStatusLabel(order.status)}
                </dd>
              </div>
            </dl>
            <div className="min-h-11">
              <p className="text-sm leading-5 text-muted">Resultado</p>
              <p
                className="line-clamp-2 text-sm leading-[22px] [overflow-wrap:anywhere]"
                title={order.result?.trim() || undefined}
              >
                {order.result?.trim() || "Não registrado"}
              </p>
            </div>
            <div className="grid justify-items-start gap-1">
              <OrderActionsButton order={order} onSelect={onSelect} />
              <FoundationsButton order={order} onFoundations={onFoundations} />
            </div>
          </li>
        ))}
      </ul>
    </section>
  );
}
