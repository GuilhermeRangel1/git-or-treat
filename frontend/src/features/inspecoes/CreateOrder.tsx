import { useState } from "react";
import { Link } from "react-router-dom";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { ApiError } from "@/shared/api/client";
import { createQueueOrder } from "@/shared/api/orders";
import Button from "@/shared/ui/Button";

export default function CreateOrder({
  uc,
  sourceVersion,
  sourceFingerprint,
  requireSourceFingerprint = false,
  ruleVersion,
  disabled,
  onRefresh,
}: {
  uc: string;
  sourceVersion?: string;
  sourceFingerprint?: string;
  requireSourceFingerprint?: boolean;
  ruleVersion?: string;
  disabled: boolean;
  onRefresh: () => void;
}) {
  type OrderIntent = {
    key: string;
    uc: string;
    sourceVersion: string;
    sourceFingerprint?: string;
    ruleVersion: string;
  };
  const [intent, setIntent] = useState<OrderIntent | null>(null);
  const cache = useQueryClient();
  const mutation = useMutation({
    mutationFn: (request: OrderIntent) =>
      createQueueOrder(
        request.uc,
        {
          source_version: request.sourceVersion,
          ...(request.sourceFingerprint
            ? { source_fingerprint: request.sourceFingerprint }
            : {}),
          rule_version: request.ruleVersion,
        },
        request.key,
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
  const staleError = ["stale_suspicion", "stale_batch", "stale_rule"].includes(
    errorCode ?? "",
  );
  const evidenceReady = Boolean(
    sourceVersion &&
    ruleVersion &&
    (!requireSourceFingerprint || sourceFingerprint),
  );
  const evidenceChanged = Boolean(
    intent &&
    (intent.sourceVersion !== sourceVersion ||
      intent.sourceFingerprint !== sourceFingerprint ||
      intent.ruleVersion !== ruleVersion),
  );
  const makeIntent = (): OrderIntent | null =>
    sourceVersion &&
    ruleVersion &&
    (!requireSourceFingerprint || sourceFingerprint)
      ? {
          key: crypto.randomUUID(),
          uc,
          sourceVersion,
          sourceFingerprint,
          ruleVersion,
        }
      : null;
  const createFromCurrentEvidence = () => {
    const nextIntent = makeIntent();
    if (!nextIntent) return;
    setIntent(nextIntent);
    mutation.mutate(nextIntent);
  };
  const confirmWithCurrentEvidence = () => {
    const nextIntent = makeIntent();
    if (!nextIntent) return;
    setIntent(nextIntent);
    mutation.mutate(nextIntent);
  };
  const networkFailure =
    mutation.error instanceof ApiError && mutation.error.kind === "network";
  const authorizationFailure =
    mutation.error instanceof ApiError && mutation.error.status === 401;
  const conflictMessage = staleError
    ? "A suspeita mudou desde a consulta. Atualize os dados antes de criar a ordem."
    : errorCode === "active_order_exists"
      ? "Já existe uma ordem ativa para esta UC. Acompanhe a ordem informada pelo servidor."
      : null;
  if (!evidenceReady) return null;
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
        onClick={
          intent ? () => mutation.mutate(intent) : createFromCurrentEvidence
        }
      >
        Criar ordem de inspeção
      </Button>
      {mutation.isError && (
        <div role="alert" className="space-y-3 text-sm">
          <p>
            {conflictMessage ?? mutation.error.message} A criação não foi
            confirmada.
          </p>
          {networkFailure || authorizationFailure ? (
            <Button
              variant="outline"
              disabled={disabled || mutation.isPending}
              onClick={() => {
                if (intent) mutation.mutate(intent);
              }}
            >
              {authorizationFailure
                ? "Repetir mesma criação"
                : "Reenviar mesma criação"}
            </Button>
          ) : null}
          {staleError && evidenceChanged ? (
            <Button
              variant="outline"
              disabled={disabled || mutation.isPending}
              onClick={confirmWithCurrentEvidence}
            >
              Confirmar com evidência atual
            </Button>
          ) : staleError ? (
            <Button
              variant="outline"
              disabled={disabled || mutation.isPending}
              onClick={onRefresh}
            >
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
