import { ArrowRight } from "lucide-react";
import type { MouseEvent } from "react";
import type { Order } from "@/shared/api/orders";
import { formatOrderCode, orderStatusLabel } from "./ordens-query";

type OrdersTableProps = {
  orders: Order[];
  onSelect: (order: Order, trigger: HTMLButtonElement) => void;
};

function ActionButton({
  order,
  onSelect,
}: {
  order: Order;
  onSelect: OrdersTableProps["onSelect"];
}) {
  return (
    <button
      type="button"
      className="inline-flex min-h-11 items-center gap-1 rounded-md px-2 text-sm font-medium text-content underline decoration-border underline-offset-4 hover:decoration-content focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand"
      onClick={(event: MouseEvent<HTMLButtonElement>) =>
        onSelect(order, event.currentTarget)
      }
      aria-label={`Abrir ações da ordem ${formatOrderCode(order.id)} da UC ${order.uc_id}`}
    >
      Abrir ações <ArrowRight size={15} aria-hidden="true" />
    </button>
  );
}

export default function OrdersTable({ orders, onSelect }: OrdersTableProps) {
  return (
    <section aria-label="Ordens encontradas">
      <div className="hidden overflow-x-auto rounded-xl bg-surface p-4 md:block">
        <table className="w-full table-fixed text-left">
          <colgroup>
            <col className="w-[16.3%]" />
            <col className="w-[27.4%]" />
            <col className="w-[18.5%]" />
            <col className="w-[20.6%]" />
            <col className="w-[17.2%]" />
          </colgroup>
          <thead className="font-mono text-xs leading-[18px] text-muted">
            <tr className="h-11">
              <th scope="col" className="pr-3 font-normal">
                Ordem
              </th>
              <th scope="col" className="pr-3 font-normal">
                Unidade consumidora
              </th>
              <th scope="col" className="pr-3 font-normal">
                Estado
              </th>
              <th scope="col" className="pr-3 font-normal">
                Resultado
              </th>
              <th scope="col" className="font-normal">
                Ação
              </th>
            </tr>
          </thead>
          <tbody className="text-sm leading-[22px]">
            {orders.map((order) => (
              <tr key={order.id} className="h-14 align-middle">
                <th scope="row" className="break-all py-3 pr-3 font-medium">
                  {formatOrderCode(order.id)}
                </th>
                <td className="break-words py-3 pr-3">{order.uc_id}</td>
                <td className="py-3 pr-3">
                  <span>{orderStatusLabel(order.status)}</span>
                </td>
                <td className="break-words py-3 pr-3">
                  {order.result?.trim() || "Não registrado"}
                </td>
                <td className="py-1">
                  <ActionButton order={order} onSelect={onSelect} />
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
              <p className="break-words text-sm leading-[22px]">
                {order.result?.trim() || "Não registrado"}
              </p>
            </div>
            <ActionButton order={order} onSelect={onSelect} />
          </li>
        ))}
      </ul>
    </section>
  );
}
