import { ArrowLeft, Info, Clock3 } from "lucide-react";
import { Link, useSearchParams } from "react-router-dom";
import { ApiError } from "@/shared/api/client";
import { queueQuery } from "./queue-query";
import { useInspectionQueue, useSuspicion } from "./useInspectionQueue";
import SuspicionDetail from "./SuspicionDetail";
import InspectionFilters from "./InspectionFilters";
import InspectionQueue from "./InspectionQueue";
import QueueOverview from "./QueueOverview";
import { inspectionAction } from "./inspection-ui";
import type { Metadata } from "./contract";

function Provenance({ metadata }: { metadata: Metadata }) {
  return (
    <details className="text-xs text-muted" aria-label="Contexto da evidência">
      <summary className="w-fit cursor-pointer rounded py-2 underline decoration-border underline-offset-4 focus-visible:outline-2 focus-visible:outline-brand">
        Fonte, atualização e limitações
      </summary>
      <div className="mt-2 space-y-2 rounded-xl border border-border bg-surface p-4 leading-5">
        <p>
          {metadata.source.is_demo
            ? "Demonstração com dados sintéticos"
            : "Fonte analítica"}{" "}
          · {metadata.source.kind} · {metadata.source.version}
        </p>
        <p>
          Janela da evidência: {metadata.period.start} a {metadata.period.end} ·
          Energia em kWh · Atualizado em{" "}
          {new Date(metadata.source.updated_at).toLocaleString("pt-BR")}
        </p>
        <ul className="list-disc space-y-1 pl-4">
          {metadata.limitations.map((text) => (
            <li key={text}>{text}</li>
          ))}
        </ul>
      </div>
    </details>
  );
}

export default function InspecoesPage() {
  const [params, setParams] = useSearchParams();
  let parsed: ReturnType<typeof queueQuery> | null = null,
    invalid: string | null = null;
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

  return (
    <div className="space-y-5 pb-3">
      <header className="mb-6 flex w-full flex-col gap-2 lg:max-w-[810px]">
        <h1 className="font-heading text-[26px] leading-[34px] font-semibold lg:w-fit lg:text-[32px] lg:leading-10 lg:tracking-[-0.64px]">
          {parsed?.detail
            ? "Uma suspeita, com fundamento."
            : "Priorize a próxima inspeção."}
        </h1>
        <p className="text-sm leading-[22px] text-muted">
          {parsed?.detail
            ? `${parsed.detail} · Confira os sinais e os limites da evidência antes de encaminhar a inspeção.`
            : "Uma fila explicável para orientar a investigação de perdas. Suspeita não é fraude comprovada."}
        </p>
      </header>
      {parsed?.detail && (
        <Link className={inspectionAction} to={`?${back}`}>
          <ArrowLeft size={16} aria-hidden="true" />
          Voltar à fila
        </Link>
      )}
      {metadata && (
        <p className="flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-muted">
          <span className="rounded-md bg-selected px-2 py-1 font-mono">
            {metadata.source.is_demo ? "DADOS SINTÉTICOS" : "FONTE ANALÍTICA"}
          </span>
          <span className="inline-flex items-center gap-1.5">
            <Clock3 size={13} aria-hidden="true" />
            Atualização:{" "}
            {new Date(metadata.source.updated_at).toLocaleDateString("pt-BR")}
          </span>
        </p>
      )}
      {invalid && (
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
      )}
      {!invalid && !parsed?.detail && (
        <InspectionFilters
          params={params}
          request={parsed?.request ?? ""}
          options={queue.data?.data.filter_options ?? {}}
          metadata={metadata}
          onChange={setParams}
        />
      )}
      {!invalid && active.isPending && (
        <div
          role="status"
          className="rounded-xl border border-border bg-surface px-5 py-10 text-sm text-muted"
        >
          Carregando{" "}
          {parsed?.detail ? "evidências da suspeita" : "fila de inspeção"}…
        </div>
      )}
      {!invalid && active.isError && (
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
      )}
      {!invalid && active.isFetching && !active.isPending && (
        <p role="status" className="text-sm text-muted">
          Atualizando evidências; exibindo a última consulta válida.
        </p>
      )}
      {!invalid && active.data && (
        <>
          {parsed?.detail && detail.data ? (
            <SuspicionDetail data={detail.data.data} />
          ) : (
            queue.data && (
              <>
                <QueueOverview summary={queue.data.data.summary} />
                <InspectionQueue
                  result={queue.data}
                  params={params}
                  onChange={setParams}
                />
                <aside
                  className="flex gap-3 rounded-lg border border-border bg-selected/40 px-4 py-3 text-sm"
                  aria-label="Limites da priorização"
                >
                  <Info
                    size={18}
                    aria-hidden="true"
                    className="mt-0.5 shrink-0 text-brand"
                  />
                  <div>
                    <p className="font-medium">
                      Priorize a investigação, confira o fundamento.
                    </p>
                    <p className="mt-1 text-xs leading-5 text-muted">
                      Pontuações e estimativas são sintéticas. Suspeita não
                      confirma irregularidade; a inspeção precisa verificar o
                      contexto.
                    </p>
                  </div>
                </aside>
              </>
            )
          )}
          {metadata && <Provenance metadata={metadata} />}
        </>
      )}
    </div>
  );
}
