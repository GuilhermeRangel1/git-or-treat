import { useState } from "react";
import { Link } from "react-router-dom";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { ApiError } from "@/shared/api/client";
import { createQueueOrder } from "@/shared/api/orders";
import Button from "@/shared/ui/Button";

export default function CreateOrder({
  uc,
  sourceVersion,
  ruleVersion,
  disabled,
  onRefresh,
}: {
  uc: string;
  sourceVersion: string;
  ruleVersion: string;
  disabled: boolean;
  onRefresh: () => void;
}) {
  const [intent] = useState(() => ({
    key: crypto.randomUUID(),
    uc,
    sourceVersion,
    ruleVersion,
  }));
  const cache = useQueryClient();
  const mutation = useMutation({
    mutationFn: () =>
      createQueueOrder(
        intent.uc,
        {
          source_version: intent.sourceVersion,
          rule_version: intent.ruleVersion,
        },
        intent.key,
      ),
    onSuccess: () => {
      void cache.invalidateQueries({ queryKey: ["orders"] });
    },
  });
  const errorCode =
    mutation.error instanceof ApiError &&
    mutation.error.data !== null &&
    typeof mutation.error.data === "object" &&
    "error" in mutation.error.data &&
    mutation.error.data.error !== null &&
    typeof mutation.error.data.error === "object" &&
    "code" in mutation.error.data.error &&
    typeof mutation.error.data.error.code === "string"
      ? mutation.error.data.error.code
      : null;
  const activeOrderId =
    mutation.error instanceof ApiError &&
    mutation.error.data !== null &&
    typeof mutation.error.data === "object" &&
    "error" in mutation.error.data &&
    mutation.error.data.error !== null &&
    typeof mutation.error.data.error === "object" &&
    "order_id" in mutation.error.data.error &&
    Number.isSafeInteger(mutation.error.data.error.order_id) &&
    Number(mutation.error.data.error.order_id) > 0
      ? Number(mutation.error.data.error.order_id)
      : null;
  const networkFailure =
    mutation.error instanceof ApiError && mutation.error.kind === "network";
  const conflictMessage =
    errorCode === "stale_suspicion"
      ? "A suspeita mudou desde a consulta. Atualize os dados antes de criar a ordem."
      : errorCode === "active_order_exists"
        ? "Já existe uma ordem ativa para esta UC. Acompanhe a ordem informada pelo servidor."
        : null;
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
        disabled={disabled || mutation.isSuccess || mutation.isError}
        isLoading={mutation.isPending}
        onClick={() => mutation.mutate()}
      >
        Criar ordem de inspeção
      </Button>
      {mutation.isError && (
        <div role="alert" className="space-y-3 text-sm">
          <p>
            {conflictMessage ?? mutation.error.message} A criação não foi
            confirmada.
          </p>
          {networkFailure ? (
            <Button
              variant="outline"
              disabled={disabled || mutation.isPending}
              onClick={() => mutation.mutate()}
            >
              Reenviar mesma criação
            </Button>
          ) : null}
          {errorCode === "stale_suspicion" ? (
            <Button variant="outline" disabled={disabled} onClick={onRefresh}>
              Atualizar dados da suspeita
            </Button>
          ) : null}
          {errorCode === "active_order_exists" && activeOrderId !== null ? (
            <Link
              className="inline-flex min-h-11 items-center underline underline-offset-4"
              to={`/ordens?uc_id=${encodeURIComponent(uc)}&order_id=${activeOrderId}`}
            >
              Acompanhar OS-{String(activeOrderId).padStart(6, "0")}
            </Link>
          ) : null}
        </div>
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
