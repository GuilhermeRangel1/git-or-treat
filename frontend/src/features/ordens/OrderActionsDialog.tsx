import { useRef, useState, type RefObject } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Check, ClipboardCheck, X } from "lucide-react";
import {
  getOrderDetail,
  updateOrder,
  type Order,
  type OrderStatus,
} from "@/shared/api/orders";
import Button from "@/shared/ui/Button";
import Modal from "@/shared/ui/Modal";
import {
  allowedOrderStatuses,
  isOrderFinal,
  orderErrorMessage,
  orderStatusLabel,
} from "./order-actions";

type OrderActionsDialogProps = {
  order: Order | null;
  open: boolean;
  onClose: () => void;
  triggerRef: RefObject<HTMLButtonElement | null>;
  onSaved: (order: Order, message: string) => void;
};

const statusOptions: Record<OrderStatus, string> = {
  PENDENTE: "Pendente",
  EM_ANDAMENTO: "Em andamento",
  CONCLUIDA: "Concluída",
  CANCELADA: "Cancelada",
};

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
  });
  const current = detail.data;
  const [statusSelection, setStatusSelection] = useState<{
    base: OrderStatus;
    value: OrderStatus;
  } | null>(null);
  const [resultDraft, setResultDraft] = useState<string | undefined>(undefined);
  const statusDraft =
    current && statusSelection?.base === current.status
      ? statusSelection.value
      : (current?.status ?? order?.status ?? "PENDENTE");
  const resultValue = resultDraft ?? current?.result ?? "";
  const [validationError, setValidationError] = useState<string | null>(null);
  const [confirmCancellation, setConfirmCancellation] = useState(false);
  const resultRef = useRef<HTMLTextAreaElement>(null);

  const mutation = useMutation({
    mutationFn: ({
      payload,
    }: {
      payload: Parameters<typeof updateOrder>[1];
      message: string;
    }) => updateOrder(orderId as number, payload),
    onSuccess: (saved, variables) => {
      queryClient.setQueryData(["orders", "detail", saved.id], saved);
      void queryClient.invalidateQueries({ queryKey: ["orders"] });
      setValidationError(null);
      setConfirmCancellation(false);
      onSaved(saved, variables.message);
      onClose();
    },
    onError: async (error) => {
      const conflict =
        error !== null &&
        typeof error === "object" &&
        "status" in error &&
        error.status === 409;
      const refreshed = await detail.refetch();
      if (
        conflict ||
        (confirmCancellation &&
          refreshed.data &&
          isOrderFinal(refreshed.data.status))
      ) {
        setConfirmCancellation(false);
      }
    },
  });

  const finalOrder = current ? isOrderFinal(current.status) : true;
  const disabled =
    !current ||
    detail.isFetching ||
    detail.isError ||
    mutation.isPending ||
    finalOrder;
  const statusPending =
    mutation.isPending && Boolean(mutation.variables?.payload.status);
  const resultPending =
    mutation.isPending && mutation.variables?.payload.status === undefined;

  const validateResult = () => {
    if (resultValue.trim()) {
      setValidationError(null);
      return true;
    }
    setValidationError("Informe o resultado da inspeção.");
    resultRef.current?.focus();
    return false;
  };

  const saveStatus = () => {
    if (!current || disabled || statusDraft === current.status) return;
    const allowed = allowedOrderStatuses(current.status);
    if (!allowed.includes(statusDraft)) {
      setValidationError("Essa transição de estado não é permitida.");
      setStatusSelection(null);
      return;
    }
    if (statusDraft === "CONCLUIDA" && !validateResult()) return;
    mutation.mutate({
      payload: {
        status: statusDraft,
        ...(statusDraft === "CONCLUIDA" ? { result: resultValue.trim() } : {}),
      },
      message: `Estado atualizado para ${orderStatusLabel(statusDraft).toLowerCase()}.`,
    });
  };

  const saveResult = () => {
    if (!current || disabled || !validateResult()) return;
    mutation.mutate({
      payload: { result: resultValue.trim() },
      message: "Resultado de campo registrado.",
    });
  };

  const confirmCancel = () => {
    if (!current || disabled) return;
    if (finalOrder) return;
    mutation.mutate({
      payload: { status: "CANCELADA" },
      message: "Ordem cancelada.",
    });
  };

  const modalTitle = confirmCancellation
    ? `Cancelar a ordem ${current ? `#${current.id}` : ""}?`
    : `Ações da ordem ${current ? `#${current.id}` : ""}`;

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
      className={`grid gap-6 p-8 max-[639px]:gap-5 max-[639px]:p-6 ${
        confirmCancellation
          ? "[&_h2]:text-[20px] [&_h2]:leading-7"
          : "[&_h2]:text-[32px] [&_h2]:leading-10 max-[639px]:[&_h2]:text-[26px] max-[639px]:[&_h2]:leading-[34px]"
      }`}
    >
      {confirmCancellation ? (
        <section className="grid gap-4" aria-label="Confirmar cancelamento">
          <p className="text-sm leading-[22px] text-muted">
            A ordem será marcada como cancelada. Você pode voltar para manter a
            ordem sem gravar alterações.
          </p>
          {mutation.isError && (
            <p
              className="rounded-lg p-4 text-sm"
              role="alert"
              style={dangerNoticeStyle}
            >
              {orderErrorMessage(mutation.error)} A alteração não foi
              confirmada. Consulte o estado atual antes de reenviar.
            </p>
          )}
          <div className="flex flex-wrap gap-3 max-[639px]:flex-col">
            <Button
              variant="secondary"
              className="min-h-11 min-w-[180px] max-[639px]:w-full"
              disabled={disabled}
              onClick={() => setConfirmCancellation(false)}
            >
              Manter ordem
            </Button>
            <Button
              variant="danger"
              className="min-h-11 min-w-[180px] max-[639px]:w-full"
              leftIcon={<X size={18} aria-hidden="true" />}
              isLoading={mutation.isPending}
              loadingLabel="Cancelando…"
              disabled={disabled}
              onClick={confirmCancel}
            >
              Cancelar ordem
            </Button>
          </div>
        </section>
      ) : (
        <div className="grid gap-4">
          {detail.isPending && (
            <p role="status" className="text-sm text-muted">
              Consultando o estado atual da ordem…
            </p>
          )}
          {detail.isError && (
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
          )}
          {detail.isFetching && !detail.isPending && (
            <p role="status" className="text-xs text-muted">
              Atualizando o estado confirmado pelo servidor…
            </p>
          )}
          {current && (
            <>
              <p className="-mt-2 text-xs leading-[18px] text-muted">
                Atualizações confirmadas pela API · UC {current.uc_id}
              </p>
              {mutation.isError && (
                <p
                  className="rounded-lg p-4 text-sm"
                  role="alert"
                  style={dangerNoticeStyle}
                >
                  {orderErrorMessage(mutation.error)} A alteração não foi
                  confirmada. Consulte o estado atual antes de reenviar.
                </p>
              )}
              {validationError && (
                <div
                  className="rounded-lg p-4 text-sm"
                  role="alert"
                  style={dangerNoticeStyle}
                >
                  <strong className="block font-medium">
                    Resultado não informado
                  </strong>
                  <span>
                    Informe o resultado de campo antes de registrar ou concluir
                    a ordem.
                  </span>
                </div>
              )}
              <div className="grid gap-2">
                <label htmlFor="order-status" className="text-sm font-medium">
                  Estado da ordem
                </label>
                <select
                  id="order-status"
                  className={fieldClassName}
                  value={statusDraft}
                  disabled={disabled}
                  onChange={(event) => {
                    setStatusSelection({
                      base: current.status,
                      value: event.currentTarget.value as OrderStatus,
                    });
                    setValidationError(null);
                  }}
                >
                  {allowedOrderStatuses(current.status).map((status) => (
                    <option value={status} key={status}>
                      {statusOptions[status]}
                    </option>
                  ))}
                </select>
                <p className="text-xs leading-[18px] text-muted">
                  Estado atual confirmado: {orderStatusLabel(current.status)}.
                </p>
              </div>
              <Button
                variant="neutral"
                className="min-h-11 w-fit min-w-[180px] max-[639px]:w-full"
                leftIcon={<ClipboardCheck size={18} aria-hidden="true" />}
                disabled={disabled || statusDraft === current.status}
                isLoading={statusPending}
                loadingLabel="Atualizando…"
                onClick={saveStatus}
              >
                Atualizar estado
              </Button>
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
                  disabled={disabled}
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
                    Informe um resultado antes de continuar.
                  </p>
                ) : (
                  <p
                    id="order-result-help"
                    className="text-xs leading-[18px] text-muted"
                  >
                    Até 4.000 caracteres. Registrar resultado não conclui a
                    ordem.
                  </p>
                )}
              </div>
              <Button
                variant="secondary"
                className="min-h-11 w-fit min-w-[180px] max-[639px]:w-full"
                leftIcon={<Check size={18} aria-hidden="true" />}
                disabled={disabled}
                isLoading={resultPending}
                loadingLabel="Registrando…"
                onClick={saveResult}
              >
                Registrar resultado
              </Button>
              {!finalOrder && (
                <Button
                  variant="danger"
                  className="min-h-11 w-fit min-w-[180px] max-[639px]:w-full"
                  leftIcon={<X size={18} aria-hidden="true" />}
                  disabled={disabled}
                  onClick={() => {
                    setValidationError(null);
                    setConfirmCancellation(true);
                  }}
                >
                  Cancelar ordem…
                </Button>
              )}
              {finalOrder && (
                <p role="status" className="text-sm text-muted">
                  Esta ordem está encerrada e não pode ser reaberta.
                </p>
              )}
            </>
          )}
        </div>
      )}
    </Modal>
  );
}

const fieldClassName =
  "min-h-12 w-full max-w-[320px] rounded-lg border border-control bg-surface px-3 text-sm text-content focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand disabled:cursor-not-allowed disabled:opacity-60 max-[639px]:max-w-none";

const dangerNoticeStyle = {
  backgroundColor: "var(--action-danger-bg)",
  color: "var(--action-danger-text)",
};
