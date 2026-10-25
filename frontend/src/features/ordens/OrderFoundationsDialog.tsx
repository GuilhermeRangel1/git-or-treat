import type { RefObject } from "react";
import { useQuery } from "@tanstack/react-query";
import { getOrderDetail, type Order } from "@/shared/api/orders";
import Button from "@/shared/ui/Button";
import Modal from "@/shared/ui/Modal";
import { orderErrorMessage, readOrderFoundation } from "./order-actions";

type OrderFoundationsDialogProps = {
  order: Order | null;
  open: boolean;
  onClose: () => void;
  triggerRef: RefObject<HTMLButtonElement | null>;
};

export default function OrderFoundationsDialog({
  order,
  open,
  onClose,
  triggerRef,
}: OrderFoundationsDialogProps) {
  const orderId = order?.id;
  const detail = useQuery({
    queryKey: ["orders", "detail", orderId],
    queryFn: ({ signal }) => getOrderDetail(orderId as number, signal),
    enabled: open && orderId !== undefined,
  });
  const current = detail.data;
  const foundation = current ? readOrderFoundation(current) : null;

  return (
    <Modal
      open={open && Boolean(order)}
      onClose={onClose}
      triggerRef={triggerRef}
      title={`Fundamentos da ordem ${order ? `#${order.id}` : ""}`}
      closeLabel="Fechar fundamentos da ordem"
      size="sm"
      header="inline"
      className="grid gap-6 p-8 max-[639px]:gap-5 max-[639px]:p-6 [&_h2]:text-[32px] [&_h2]:leading-10 max-[639px]:[&_h2]:text-[26px] max-[639px]:[&_h2]:leading-[34px]"
    >
      <div className="grid gap-5">
        {detail.isPending && (
          <p role="status" className="text-sm text-muted">
            Consultando fundamentos preservados…
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
            Atualizando os dados do servidor…
          </p>
        )}
        {current && foundation && (
          <>
            <div className="grid gap-4">
              <Detail label="Unidade consumidora" value={current.uc_id} />
              <Detail label="Motivo registrado" value={current.reason} />
              <Detail
                label="Referência da suspeita"
                value={
                  current.suspicion_reference ?? "Não preservada nesta ordem."
                }
                mono
              />
              <Detail
                label="Criada em"
                value={formatTimestamp(current.created_at)}
              />
            </div>

            {!foundation.available ? (
              <p className="rounded-lg border border-border bg-surface p-4 text-sm text-muted">
                A ordem não possui snapshot de fundamentos disponível.
              </p>
            ) : !foundation.supported ? (
              <p className="rounded-lg border border-border bg-surface p-4 text-sm text-muted">
                O formato deste snapshot ainda não pode ser interpretado. Os
                dados originais foram preservados sem adaptação.
              </p>
            ) : (
              <section
                className="grid gap-4 rounded-xl border border-border bg-surface p-4"
                aria-label="Evidências da suspeita"
              >
                <h3 className="font-heading text-lg font-semibold">
                  Evidências preservadas
                </h3>
                {foundation.legacy && (
                  <p className="rounded-md border border-border px-3 py-2 text-sm text-muted">
                    Snapshot legado sem versão de esquema explícita; campos
                    reconhecidos são apresentados quando válidos.
                  </p>
                )}
                {foundation.source ? (
                  <Detail
                    label="Fonte"
                    value={`${foundation.source.kind} · ${foundation.source.version}${foundation.source.isDemo ? " · demonstração sintética" : ""}`}
                  />
                ) : (
                  <Detail label="Fonte" value="Não disponível no snapshot." />
                )}
                {foundation.source?.updatedAt && (
                  <Detail
                    label="Atualizada em"
                    value={formatTimestamp(foundation.source.updatedAt)}
                  />
                )}
                {foundation.period ? (
                  <Detail
                    label="Período da análise"
                    value={`${formatDate(foundation.period.start)} a ${formatDate(foundation.period.end)}`}
                  />
                ) : (
                  <Detail
                    label="Período da análise"
                    value="Não disponível no snapshot."
                  />
                )}
                <Detail
                  label="Energia potencialmente recuperável"
                  value={
                    foundation.estimateUnavailable
                      ? "Não disponível; ausência de estimativa não é zero."
                      : `${formatNumber(foundation.estimateKwh!)} kWh`
                  }
                />
                {foundation.estimateEvidence && (
                  <Detail
                    label="Base da estimativa"
                    value={foundation.estimateEvidence}
                  />
                )}
                <div className="grid gap-2">
                  <h4 className="text-sm font-medium">Sinais validados</h4>
                  {foundation.signals.length > 0 ? (
                    <ul className="grid gap-2">
                      {foundation.signals.map((signal, index) => (
                        <li
                          className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1 border-b border-border pb-2 text-sm last:border-0"
                          key={`${signal.id ?? signal.label}-${index}`}
                        >
                          <span>{signal.label}</span>
                          {signal.weight !== undefined && (
                            <span className="text-xs text-muted">
                              Peso {formatNumber(signal.weight)}
                            </span>
                          )}
                        </li>
                      ))}
                    </ul>
                  ) : (
                    <p className="text-sm text-muted">
                      Nenhum sinal estruturado válido foi preservado.
                    </p>
                  )}
                </div>
                {foundation.limitations.length > 0 && (
                  <div className="grid gap-2">
                    <h4 className="text-sm font-medium">Limites registrados</h4>
                    <ul className="grid list-disc gap-1 pl-5 text-sm text-muted">
                      {foundation.limitations.map((limitation, index) => (
                        <li key={`${limitation}-${index}`}>{limitation}</li>
                      ))}
                    </ul>
                  </div>
                )}
              </section>
            )}
          </>
        )}
      </div>
    </Modal>
  );
}

function Detail({
  label,
  value,
  mono = false,
}: {
  label: string;
  value: string;
  mono?: boolean;
}) {
  return (
    <dl className="grid min-w-0 gap-1">
      <dt className="text-sm font-medium">{label}</dt>
      <dd
        className={`break-words text-sm leading-[22px] text-muted ${mono ? "font-mono text-xs" : ""}`}
      >
        {value}
      </dd>
    </dl>
  );
}

function formatDate(value: string) {
  const competence = /^(\d{4})-(0[1-9]|1[0-2])$/.exec(value);
  if (!competence) return "Período não disponível.";
  const month = new Intl.DateTimeFormat("pt-BR", {
    month: "short",
    timeZone: "UTC",
  })
    .format(new Date(`${value}-01T00:00:00Z`))
    .replace(/\.$/, "")
    .toLocaleLowerCase("pt-BR");
  return `${month}/${competence[1]}`;
}

function formatTimestamp(value: string) {
  const date = new Date(value);
  return Number.isFinite(date.getTime())
    ? new Intl.DateTimeFormat("pt-BR", {
        dateStyle: "short",
        timeStyle: "short",
      }).format(date)
    : "Data não disponível.";
}

function formatNumber(value: number) {
  return new Intl.NumberFormat("pt-BR", { maximumFractionDigits: 2 }).format(
    value,
  );
}

const dangerNoticeStyle = {
  backgroundColor: "var(--action-danger-bg)",
  color: "var(--action-danger-text)",
};
