import { useEffect, useRef, useState, type RefObject } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Check, ClipboardCheck, X } from "lucide-react";
import {
  cancelOrder,
  getOrderDetail,
  registerOrderResult,
  updateOrder,
  type Order,
  type OrderDetail,
} from "@/shared/api/orders";
import Button from "@/shared/ui/Button";
import Modal from "@/shared/ui/Modal";
import {
  isOrderFinal,
  orderErrorMessage,
  orderStatusLabel,
} from "./order-actions";
import { formatOrderCode } from "./ordens-query";
import OrderHistory from "./OrderHistory";

type OrderActionsDialogProps = {
  order: Order | null;
  open: boolean;
  onClose: () => void;
  triggerRef: RefObject<HTMLElement | null>;
  onSaved: (order: Order, message: string) => void;
};

type MutationVariables =
  | { orderId: number; kind: "start"; version: number }
  | { orderId: number; kind: "result"; version: number; result: string }
  | { orderId: number; kind: "cancel"; version: number; reason: string };

export default function OrderActionsDialog({
  order,
  open,
  onClose,
  triggerRef,
  onSaved,
}: OrderActionsDialogProps) {
  const queryClient = useQueryClient();
  const orderId = order?.id;
  const detail = useQuery({
    queryKey: ["orders", "detail", orderId],
    queryFn: ({ signal }) => getOrderDetail(orderId as number, signal),
    enabled: open && orderId !== undefined,
    staleTime: 0,
  });
  const current = detail.data;
  const [resultDraft, setResultDraft] = useState<string | undefined>(undefined);
  const [cancelReason, setCancelReason] = useState("");
  const [validationError, setValidationError] = useState<string | null>(null);
  const [confirmCancellation, setConfirmCancellation] = useState(false);
  const resultRef = useRef<HTMLTextAreaElement>(null);
  const submittingRef = useRef(false);
  const mountedRef = useRef(false);
  const activeOrderIdRef = useRef(orderId);
  const openRef = useRef(open);

  useEffect(() => {
    mountedRef.current = true;
    activeOrderIdRef.current = orderId;
    openRef.current = open;
    return () => {
      mountedRef.current = false;
    };
  }, [open, orderId]);

  const mutation = useMutation({
    mutationFn: async (variables: MutationVariables): Promise<OrderDetail> => {
      switch (variables.kind) {
        case "start":
          return updateOrder(variables.orderId, {
            version: variables.version,
            status: "EM_ANDAMENTO",
          });
        case "result":
          return registerOrderResult(variables.orderId, {
            version: variables.version,
            result: variables.result,
          });
        case "cancel":
          return cancelOrder(variables.orderId, {
            confirmed_order_id: variables.orderId,
            version: variables.version,
            ...(variables.reason ? { reason: variables.reason } : {}),
          });
      }
    },
    onSuccess: (saved, variables) => {
      const latest = queryClient.setQueryData<OrderDetail>(
        ["orders", "detail", saved.id],
        (cached) => (cached && cached.version > saved.version ? cached : saved),
      );
      void queryClient.invalidateQueries({ queryKey: ["orders", "list"] });
      void queryClient.invalidateQueries({
        queryKey: ["orders", "history", saved.id],
      });
      if (
        !latest ||
        latest.version > saved.version ||
        !mountedRef.current ||
        !openRef.current ||
        activeOrderIdRef.current !== variables.orderId
      ) {
        return;
      }
      setValidationError(null);
      setConfirmCancellation(false);
      setResultDraft(undefined);
      setCancelReason("");
      const message =
        variables.kind === "start"
          ? "Ordem iniciada."
          : variables.kind === "result"
            ? "Resultado registrado e ordem concluída."
            : "Ordem cancelada.";
      onSaved(saved, message);
      onClose();
    },
    onError: async (error, variables) => {
      const conflict =
        error !== null &&
        typeof error === "object" &&
        "status" in error &&
        error.status === 409;
      let refreshed: OrderDetail | undefined;
      try {
        refreshed = await queryClient.fetchQuery({
          queryKey: ["orders", "detail", variables.orderId],
          queryFn: ({ signal }) => getOrderDetail(variables.orderId, signal),
          staleTime: 0,
        });
      } catch {
        // Keep the write error visible; the failed reconciliation never retries it.
      }
      if (conflict) {
        if (
          mountedRef.current &&
          openRef.current &&
          activeOrderIdRef.current === variables.orderId
        ) {
          setConfirmCancellation(false);
        }
        void queryClient.invalidateQueries({ queryKey: ["orders", "list"] });
        void queryClient.invalidateQueries({
          queryKey: ["orders", "history", variables.orderId],
        });
      } else if (
        mountedRef.current &&
        openRef.current &&
        activeOrderIdRef.current === variables.orderId &&
        confirmCancellation &&
        refreshed &&
        isOrderFinal(refreshed.status)
      ) {
        setConfirmCancellation(false);
      }
    },
    onSettled: () => {
      submittingRef.current = false;
    },
  });

  const finalOrder = current ? isOrderFinal(current.status) : true;
  const locked =
    !current ||
    detail.isFetching ||
    detail.isError ||
    mutation.isPending ||
    finalOrder;
  const resultValue = resultDraft ?? current?.result ?? "";
  const isPending = current?.status === "PENDENTE";
  const isRunning = current?.status === "EM_ANDAMENTO";
  const orderCode = current ? formatOrderCode(current.id) : "";

  function submit(variables: MutationVariables) {
    if (submittingRef.current || locked || !current) return;
    submittingRef.current = true;
    mutation.mutate(variables);
  }

  function saveResult() {
    if (!current || locked) return;
    const result = resultValue.trim();
    if (!result) {
      setValidationError("Informe o resultado da inspeção.");
      resultRef.current?.focus();
      return;
    }
    if (result.length > 4000) {
      setValidationError("O resultado deve ter até 4.000 caracteres.");
      resultRef.current?.focus();
      return;
    }
    setValidationError(null);
    submit({
      orderId: current.id,
      kind: "result",
      version: current.version,
      result,
    });
  }

  function confirmCancel() {
    if (!current || locked || isOrderFinal(current.status)) return;
    submit({
      orderId: current.id,
      kind: "cancel",
      version: current.version,
      reason: cancelReason.trim(),
    });
  }

  const modalTitle = confirmCancellation
    ? `Cancelar ${orderCode}?`
    : `Ações da ordem ${current ? `#${current.id}` : ""}`;
  const resultPending =
    mutation.isPending && mutation.variables?.kind === "result";

  return (
    <Modal
      open={open && Boolean(order)}
      onClose={() => {
        setConfirmCancellation(false);
        onClose();
      }}
      triggerRef={triggerRef}
      title={modalTitle}
      closeLabel="Fechar ações da ordem"
      size={confirmCancellation ? "xs" : "sm"}
      header="inline"
      className={`grid min-w-0 gap-6 p-8 max-[639px]:gap-5 max-[639px]:p-6 ${
        confirmCancellation
          ? "[&_h2]:text-[20px] [&_h2]:leading-7"
          : "[&_h2]:text-[32px] [&_h2]:leading-10 max-[639px]:[&_h2]:text-[26px] max-[639px]:[&_h2]:leading-[34px]"
      }`}
    >
      {confirmCancellation ? (
        <section className="grid gap-4" aria-label="Confirmar cancelamento">
          <p className="text-sm leading-[22px] text-muted">
            Confirme o cancelamento de <strong>{orderCode}</strong>, UC{" "}
            <strong>{current?.uc_id}</strong>. Você pode voltar para manter a
            ordem sem gravar alterações.
          </p>
          {mutation.isError ? <MutationError error={mutation.error} /> : null}
          {mutation.isPending ? (
            <p role="status" className="text-sm text-muted">
              Enviando para confirmação do servidor. Fechar esta janela não
              cancela a gravação.
            </p>
          ) : null}
          <div className="grid gap-2">
            <label
              htmlFor="order-cancellation-reason"
              className="text-sm font-medium"
            >
              Motivo do cancelamento (opcional)
            </label>
            <textarea
              id="order-cancellation-reason"
              className={`${fieldClassName} min-h-[80px] resize-y py-3`}
              value={cancelReason}
              maxLength={4000}
              disabled={!current || detail.isFetching || mutation.isPending}
              onChange={(event) => setCancelReason(event.currentTarget.value)}
            />
          </div>
          <div className="flex flex-wrap gap-3 max-[639px]:flex-col">
            <Button
              variant="secondary"
              className="min-h-11 min-w-[180px] max-[639px]:w-full"
              disabled={mutation.isPending}
              onClick={() => setConfirmCancellation(false)}
            >
              Manter ordem
            </Button>
            <Button
              variant="danger"
              className="min-h-11 min-w-[180px] max-[639px]:w-full"
              leftIcon={<X size={18} aria-hidden="true" />}
              isLoading={
                mutation.isPending && mutation.variables?.kind === "cancel"
              }
              loadingLabel="Cancelando…"
              disabled={locked}
              onClick={confirmCancel}
            >
              Confirmar cancelamento
            </Button>
          </div>
        </section>
      ) : (
        <div className="grid min-w-0 gap-4">
          {detail.isPending ? (
            <p role="status" className="text-sm text-muted">
              Consultando o estado atual da ordem…
            </p>
          ) : null}
          {detail.isError ? (
            <div
              className="grid gap-3 rounded-lg p-4 text-sm"
              role="alert"
              style={dangerNoticeStyle}
            >
              <p>{orderErrorMessage(detail.error)}</p>
              <Button
                variant="neutral"
                size="sm"
                disabled={detail.isFetching}
                onClick={() => void detail.refetch()}
              >
                Tentar novamente
              </Button>
            </div>
          ) : null}
          {detail.isFetching && !detail.isPending ? (
            <p role="status" className="text-xs text-muted">
              Atualizando o estado confirmado pelo servidor…
            </p>
          ) : null}
          {current ? (
            <>
              <p className="-mt-2 text-xs leading-[18px] text-muted">
                {orderCode} · UC {current.uc_id} · Estado confirmado:{" "}
                {orderStatusLabel(current.status)}
              </p>
              {mutation.isError ? (
                <MutationError error={mutation.error} />
              ) : null}
              {mutation.isPending ? (
                <p role="status" className="text-sm text-muted">
                  Enviando para confirmação do servidor. Fechar esta janela não
                  cancela a gravação.
                </p>
              ) : null}
              {validationError ? (
                <div
                  className="rounded-lg p-4 text-sm"
                  role="alert"
                  style={dangerNoticeStyle}
                >
                  <strong className="block font-medium">
                    Resultado não informado
                  </strong>
                  <span>{validationError}</span>
                </div>
              ) : null}

              {isPending ? (
                <Button
                  variant="neutral"
                  className="min-h-11 w-fit min-w-[180px] max-[639px]:w-full"
                  leftIcon={<ClipboardCheck size={18} aria-hidden="true" />}
                  isLoading={
                    mutation.isPending && mutation.variables?.kind === "start"
                  }
                  loadingLabel="Iniciando…"
                  disabled={locked}
                  onClick={() =>
                    submit({
                      orderId: current.id,
                      kind: "start",
                      version: current.version,
                    })
                  }
                >
                  Iniciar ordem
                </Button>
              ) : null}

              <div className="grid gap-2">
                <label htmlFor="order-result" className="text-sm font-medium">
                  Resultado de campo
                </label>
                <textarea
                  id="order-result"
                  ref={resultRef}
                  className={`${fieldClassName} min-h-[96px] resize-y py-3`}
                  value={resultValue}
                  maxLength={4000}
                  disabled={
                    !isRunning ||
                    detail.isFetching ||
                    mutation.isPending ||
                    finalOrder
                  }
                  aria-invalid={Boolean(validationError)}
                  aria-describedby={
                    validationError ? "order-result-error" : "order-result-help"
                  }
                  onChange={(event) => {
                    setResultDraft(event.currentTarget.value);
                    if (event.currentTarget.value.trim())
                      setValidationError(null);
                  }}
                />
                {validationError ? (
                  <p
                    className="text-sm"
                    id="order-result-error"
                    style={{ color: "var(--action-danger-text)" }}
                  >
                    {validationError}
                  </p>
                ) : (
                  <p
                    id="order-result-help"
                    className="text-xs leading-[18px] text-muted"
                  >
                    Até 4.000 caracteres. Registrar o resultado conclui a ordem.
                  </p>
                )}
              </div>
              {isRunning ? (
                <Button
                  variant="secondary"
                  className="min-h-11 w-fit min-w-[220px] max-[639px]:w-full"
                  leftIcon={<Check size={18} aria-hidden="true" />}
                  isLoading={resultPending}
                  loadingLabel="Concluindo…"
                  disabled={locked}
                  onClick={saveResult}
                >
                  Registrar resultado e concluir
                </Button>
              ) : null}

              {!finalOrder ? (
                <Button
                  variant="danger"
                  className="min-h-11 w-fit min-w-[180px] max-[639px]:w-full"
                  leftIcon={<X size={18} aria-hidden="true" />}
                  disabled={locked}
                  onClick={() => {
                    setValidationError(null);
                    setConfirmCancellation(true);
                  }}
                >
                  Cancelar ordem…
                </Button>
              ) : (
                <p role="status" className="text-sm text-muted">
                  Esta ordem está encerrada e disponível somente para consulta.
                </p>
              )}
              <OrderHistory orderId={current.id} />
            </>
          ) : null}
        </div>
      )}
    </Modal>
  );
}

function MutationError({ error }: { error: unknown }) {
  return (
    <p
      className="rounded-lg p-4 text-sm"
      role="alert"
      style={dangerNoticeStyle}
    >
      {orderErrorMessage(error)} A alteração não foi confirmada. Consulte o
      estado atual antes de iniciar outra ação.
    </p>
  );
}

const fieldClassName =
  "min-h-12 w-full max-w-[320px] rounded-lg border border-control bg-surface px-3 text-sm text-content focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand disabled:cursor-not-allowed disabled:opacity-60 max-[639px]:max-w-none";

const dangerNoticeStyle = {
  backgroundColor: "var(--action-danger-bg)",
  color: "var(--action-danger-text)",
};
