import { useRef, useState } from "react";
import { ArrowLeft, ArrowRight } from "lucide-react";
import { Link, useSearchParams } from "react-router-dom";
import { ApiError } from "@/shared/api/client";
import Modal from "@/shared/ui/Modal";
import { queueQuery } from "./queue-query";
import { useInspectionQueue, useSuspicion } from "./useInspectionQueue";
import SuspicionDetail from "./SuspicionDetail";
import InspectionFoundations from "./InspectionFoundations";
import CreateOrder from "./CreateOrder";
import InspectionFilters from "./InspectionFilters";
import InspectionQueue from "./InspectionQueue";
import { inspectionAction } from "./inspection-ui";
import type { Metadata } from "./contract";

function DemonstrationLine({ metadata }: { metadata: Metadata }) {
  return (
    <p className="text-xs leading-[18px] text-muted">
      {metadata.source.is_demo
        ? "Demonstração · dados sintéticos"
        : "Fonte analítica"}
      {" · atualização ilustrativa: "}
      {new Intl.DateTimeFormat("pt-BR", {
        day: "2-digit",
        month: "2-digit",
        year: "numeric",
        timeZone: "UTC",
      }).format(new Date(metadata.source.updated_at))}
      {metadata.status === "partial" ? " · cobertura parcial" : null}
    </p>
  );
}

function FoundationDialog({
  metadata,
  detail,
  open,
  onClose,
  triggerRef,
}: {
  metadata: Metadata;
  detail?: NonNullable<ReturnType<typeof useSuspicion>["data"]>["data"];
  open: boolean;
  onClose: () => void;
  triggerRef: React.RefObject<HTMLButtonElement | null>;
}) {
  return (
    <Modal
      open={open}
      onClose={onClose}
      triggerRef={triggerRef}
      title="Ver fundamentos"
      closeLabel="Fechar fundamentos"
      size="lg"
      header="sticky"
    >
      <InspectionFoundations metadata={metadata} detail={detail} />
    </Modal>
  );
}

export default function InspecoesPage() {
  const [params, setParams] = useSearchParams();
  const [foundationsOpen, setFoundationsOpen] = useState(false);
  const foundationsTriggerRef = useRef<HTMLButtonElement>(null);

  let parsed: ReturnType<typeof queueQuery> | null = null;
  let invalid: string | null = null;
  try {
    parsed = queueQuery(params);
  } catch (error) {
    invalid = error instanceof Error ? error.message : "Filtros inválidos.";
  }
  const queue = useInspectionQueue(
    parsed?.request ?? null,
    parsed?.detail ?? null,
  );
  const detail = useSuspicion(parsed?.detail ?? null, parsed !== null);
  const active = parsed?.detail ? detail : queue;
  const metadata = active.data?.metadata;
  const back = new URLSearchParams(params);
  back.delete("uc");

  function closeFoundations() {
    setFoundationsOpen(false);
  }

  return (
    <div className="space-y-5 pb-6 lg:space-y-6">
      <header className="flex w-full flex-col gap-2 lg:max-w-[810px]">
        <h1 className="font-heading text-[26px] leading-[34px] font-semibold lg:w-fit lg:text-[32px] lg:leading-10 lg:tracking-[-0.64px]">
          {parsed?.detail
            ? "Uma suspeita, com fundamento."
            : "Priorize a próxima inspeção."}
        </h1>
        <p className="text-sm leading-[22px] text-muted">
          {parsed?.detail
            ? `${parsed.detail} · Prioridade ${detail.data ? detail.data.data.priority.toLocaleString("pt-BR", { maximumFractionDigits: 2 }) : "consultando"} neste cenário demonstrativo.`
            : "Uma fila explicável para orientar a investigação de perdas. Suspeita não é fraude comprovada."}
        </p>
      </header>

      {metadata ? <DemonstrationLine metadata={metadata} /> : null}

      {invalid ? (
        <div
          role="alert"
          className="rounded-xl border border-border bg-surface p-5"
        >
          <p>{invalid}</p>
          <button
            className={`${inspectionAction} mt-3`}
            onClick={() => setParams({})}
          >
            Limpar filtros
          </button>
        </div>
      ) : null}

      {!invalid && !parsed?.detail ? (
        <InspectionFilters
          params={params}
          request={parsed?.request ?? ""}
          options={queue.data?.data.filter_options ?? {}}
          metadata={metadata}
          onChange={setParams}
        />
      ) : null}

      {!invalid && active.isPending ? (
        <div
          role="status"
          className="rounded-xl border border-border bg-surface px-5 py-10 text-sm text-muted"
        >
          Carregando{" "}
          {parsed?.detail ? "evidências da suspeita" : "fila de inspeção"}…
        </div>
      ) : null}
      {!invalid && active.isError ? (
        <div
          role="alert"
          className="rounded-xl border border-border bg-surface p-5"
        >
          <p>
            {active.data
              ? "Não foi possível atualizar as evidências. Exibindo a última consulta válida; ela pode estar desatualizada."
              : active.error instanceof ApiError && active.error.status === 404
                ? "Suspeita não encontrada para esta UC."
                : "Não foi possível consultar as evidências. Tente novamente."}
          </p>
          <button
            className={`${inspectionAction} mt-3`}
            onClick={() => void active.refetch()}
          >
            Tentar novamente
          </button>
        </div>
      ) : null}
      {!invalid && active.isFetching && !active.isPending ? (
        <p role="status" className="text-sm text-muted">
          Atualizando evidências; exibindo a última consulta válida.
        </p>
      ) : null}

      {!invalid && parsed?.detail && !active.data ? (
        <Link className={inspectionAction} to={`?${back}`}>
          <ArrowLeft size={16} aria-hidden="true" />
          Voltar à fila
        </Link>
      ) : null}

      {!invalid && active.data && metadata ? (
        <>
          {parsed?.detail && detail.data ? (
            <>
              <SuspicionDetail data={detail.data.data} metadata={metadata} />
              <CreateOrder
                key={`${detail.data.data.uc_id}:${detail.data.metadata.source.version}:${detail.data.data.rule_version}`}
                uc={detail.data.data.uc_id}
                sourceVersion={detail.data.metadata.source.version}
                ruleVersion={detail.data.data.rule_version}
                disabled={detail.isFetching || detail.isError}
                onRefresh={() => void detail.refetch()}
              />
              <Link className={inspectionAction} to={`?${back}`}>
                <ArrowLeft size={16} aria-hidden="true" />
                Voltar à fila
              </Link>
            </>
          ) : queue.data ? (
            <>
              <aside
                className="flex flex-col items-start justify-center gap-1 rounded-lg bg-[var(--status-info-bg)] p-4 text-sm text-[var(--status-info-text)]"
                aria-label="Prioridade demonstrativa"
              >
                <div>
                  <p className="text-sm font-semibold">
                    Prioridade demonstrativa
                  </p>
                  <p className="mt-1 text-sm leading-[22px]">
                    Motivos e estimativas são sintéticos. Critério final de
                    priorização e energia recuperável dependem de validação com
                    as fontes.
                  </p>
                </div>
              </aside>
              <InspectionQueue
                result={queue.data}
                params={params}
                onChange={setParams}
              />
            </>
          ) : null}

          <footer className="flex flex-col items-stretch gap-2 text-xs text-muted sm:flex-row sm:items-center sm:gap-4">
            <p className="w-full sm:max-w-[600px]">
              Fonte:{" "}
              {metadata.source.is_demo
                ? "cenário sintético"
                : metadata.source.kind}
              . Nenhuma consulta à Gold.
            </p>
            <button
              ref={foundationsTriggerRef}
              type="button"
              className="inline-flex min-h-11 w-full items-center justify-center px-1 text-sm font-medium text-content underline decoration-border underline-offset-4 hover:decoration-content focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand sm:w-auto sm:justify-start"
              onClick={() => setFoundationsOpen(true)}
            >
              <span className="mx-auto inline-flex items-center gap-1 sm:mx-0">
                Ver fundamentos <ArrowRight size={14} aria-hidden="true" />
              </span>
            </button>
          </footer>
          <FoundationDialog
            metadata={metadata}
            detail={
              parsed?.detail && detail.data ? detail.data.data : undefined
            }
            open={foundationsOpen}
            onClose={closeFoundations}
            triggerRef={foundationsTriggerRef}
          />
        </>
      ) : null}
    </div>
  );
}
