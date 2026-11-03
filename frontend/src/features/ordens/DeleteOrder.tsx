import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "@/shared/api/client";
import Button from "@/shared/ui/Button";
import type { Order } from "@/shared/api/orders";
import { orderErrorMessage } from "./order-actions";

export default function DeleteOrder({
  order,
  onDeleted,
}: {
  order: Order;
  onDeleted: () => void;
}) {
  const [confirm, setConfirm] = useState(false);
  const [code, setCode] = useState("");
  const client = useQueryClient();
  const mutation = useMutation({
    mutationFn: () =>
      apiClient(`/api/v1/inspections/orders/${order.id}`, {
        method: "DELETE",
        body: JSON.stringify({
          version: order.version,
          confirmed_order_id: order.id,
        }),
      }),
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: ["orders"] });
      onDeleted();
    },
  });
  return (
    <div className="space-y-3 border-t border-border pt-4">
      {confirm ? (
        <>
          <p className="text-sm">
            Excluir a ordem {order.id}? Ela sairá do portal e não poderá mais
            receber alterações. O histórico será preservado para auditoria.
          </p>
          <label className="block text-sm">
            Digite {order.id} para confirmar
            <input
              className="mt-2 block min-h-11 w-full rounded-lg border border-control bg-canvas px-3"
              value={code}
              disabled={mutation.isPending}
              onChange={(event) => setCode(event.target.value)}
              inputMode="numeric"
            />
          </label>
          <div className="flex gap-2">
            <Button
              variant="ghost"
              disabled={mutation.isPending}
              onClick={() => setConfirm(false)}
            >
              Voltar
            </Button>
            <Button
              variant="danger"
              disabled={code !== String(order.id)}
              isLoading={mutation.isPending}
              onClick={() => mutation.mutate()}
            >
              Confirmar exclusão
            </Button>
          </div>
        </>
      ) : (
        <Button variant="danger" onClick={() => setConfirm(true)}>
          Excluir ordem
        </Button>
      )}
      {mutation.isError ? (
        <p role="alert" className="text-sm">
          {orderErrorMessage(mutation.error)} Atualize a ordem antes de tentar
          novamente.
        </p>
      ) : null}
    </div>
  );
}
