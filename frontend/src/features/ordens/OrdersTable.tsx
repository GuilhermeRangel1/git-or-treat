import { ArrowRight, FileSearch } from "lucide-react";
import type { MouseEvent } from "react";
import type { Order } from "@/shared/api/orders";
import { formatOrderCode, orderStatusLabel } from "./ordens-query";

type OrdersTableProps = {
  orders: Order[];
  onSelect: (order: Order, trigger: HTMLButtonElement) => void;
  onFoundations: (order: Order, trigger: HTMLButtonElement) => void;
};

const rowActionClass =
  "inline-flex min-h-11 items-center gap-1 rounded-md py-2 pl-0 pr-2 text-sm font-medium text-content underline decoration-border underline-offset-4 hover:decoration-content focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand";

function OrderActionsButton({
  order,
  onSelect,
}: {
  order: Order;
  onSelect: OrdersTableProps["onSelect"];
}) {
  return (
    <button
      type="button"
      className={rowActionClass}
      onClick={(event: MouseEvent<HTMLButtonElement>) =>
        onSelect(order, event.currentTarget)
      }
      aria-label={`Ações da ordem ${formatOrderCode(order.id)} da UC ${order.uc_id}`}
    >
      Ações <ArrowRight size={15} aria-hidden="true" />
    </button>
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
        <table className="w-full table-fixed text-left">
          <colgroup>
            <col className="w-[13%]" />
            <col className="w-[21%]" />
            <col className="w-[14%]" />
            <col className="w-[18%]" />
            <col className="w-[14%]" />
            <col className="w-[20%]" />
          </colgroup>
          <thead className="font-mono text-xs leading-[18px] text-muted">
            <tr className="h-11">
              <th scope="col" className="pr-2 font-normal">
                Ordem
              </th>
              <th scope="col" className="pr-2 font-normal">
                Unidade consumidora
              </th>
              <th scope="col" className="pr-2 font-normal">
                Estado
              </th>
              <th scope="col" className="pr-2 font-normal">
                Resultado
              </th>
              <th scope="col" className="pr-2 font-normal">
                Ações
              </th>
              <th scope="col" className="font-normal">
                Fundamentos
              </th>
            </tr>
          </thead>
          <tbody className="text-sm leading-[22px]">
            {orders.map((order) => (
              <tr key={order.id} className="h-14 align-middle">
                <th scope="row" className="break-all py-3 pr-2 font-medium">
                  {formatOrderCode(order.id)}
                </th>
                <td className="break-words py-3 pr-2">{order.uc_id}</td>
                <td className="py-3 pr-2">
                  <span>{orderStatusLabel(order.status)}</span>
                </td>
                <td className="break-words py-3 pr-2">
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
                <td className="align-top py-1 pr-2">
                  <OrderActionsButton order={order} onSelect={onSelect} />
                </td>
                <td className="align-top py-1">
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
