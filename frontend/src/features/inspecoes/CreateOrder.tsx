import { useState } from "react";
import { Link } from "react-router-dom";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { createQueueOrder } from "@/shared/api/orders";
import Button from "@/shared/ui/Button";

export default function CreateOrder({
  uc,
  sourceVersion,
  ruleVersion,
  disabled,
}: {
  uc: string;
  sourceVersion: string;
  ruleVersion: string;
  disabled: boolean;
}) {
  const [key] = useState(() => crypto.randomUUID());
  const cache = useQueryClient();
  const mutation = useMutation({
    mutationFn: () =>
      createQueueOrder(
        uc,
        { source_version: sourceVersion, rule_version: ruleVersion },
        key,
      ),
    onSuccess: () => {
      void cache.invalidateQueries({ queryKey: ["orders"] });
    },
  });
  return (
    <section
      className="space-y-3 rounded-xl border border-border bg-surface p-5"
      aria-label="Criar ordem de inspeção"
    >
      <p className="text-sm text-muted">
        A ordem preservará a UC, o motivo e as evidências desta suspeita.
        Prioridade operacional inicial: média.
      </p>
      <Button
        disabled={disabled || mutation.isSuccess}
        isLoading={mutation.isPending}
        onClick={() => mutation.mutate()}
      >
        Criar ordem de inspeção
      </Button>
      {mutation.isError && (
        <p role="alert">
          {mutation.error.message} A criação não foi confirmada. Tente novamente
          para consultar ou concluir o mesmo envio.
        </p>
      )}
      {mutation.isSuccess && (
        <p role="status">
          Ordem {mutation.data.id} confirmada pelo servidor.{" "}
          <Link
            className="underline"
            to={`/ordens?uc_id=${encodeURIComponent(uc)}`}
          >
            Acompanhar ordem
          </Link>
        </p>
      )}
    </section>
  );
}
