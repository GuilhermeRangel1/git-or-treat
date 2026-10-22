import { Link, useSearchParams } from "react-router-dom";
import { ApiError } from "@/shared/api/client";
import { filterLabels, queueQuery } from "./queue-query";
import { useInspectionQueue, useSuspicion } from "./useInspectionQueue";
import SuspicionDetail from "./SuspicionDetail";
import { energy, formatNumber } from "./format";
import type { Metadata } from "./contract";

const control =
  "min-h-11 w-full rounded-lg border border-control bg-surface px-3 text-sm text-content focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand";
const action =
  "inline-flex min-h-11 items-center justify-center rounded-lg border border-control px-4 text-sm font-medium text-content hover:bg-surface-hover focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand disabled:opacity-50";

function Provenance({ metadata }: { metadata: Metadata }) {
  return (
    <aside
      className="space-y-2 rounded-xl border border-border bg-surface p-4 text-sm text-muted"
      aria-label="Contexto da evidência"
    >
      <p className="font-semibold text-content">
        {metadata.source.is_demo
          ? "Demonstração com dados sintéticos"
          : "Fonte analítica"}{" "}
        · {metadata.source.version}
      </p>
      <p>
        Janela da evidência: {metadata.period.start} a {metadata.period.end} ·
        Energia em kWh · Atualizado em{" "}
        {new Date(metadata.source.updated_at).toLocaleString("pt-BR")}
      </p>
      <p>
        Origem: {metadata.source.kind}. Estimativa é uma projeção mensal
        hipotética; suspeita não confirma irregularidade.
      </p>
      <details>
        <summary className="cursor-pointer text-content">
          Limitações da fonte ({metadata.limitations.length})
        </summary>
        <ul className="mt-2 list-disc space-y-2 pl-5">
          {metadata.limitations.map((text) => (
            <li key={text}>{text}</li>
          ))}
        </ul>
      </details>
    </aside>
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
  const selected = Object.keys(filterLabels).filter((key) => params.has(key));
  const page = queue.data?.pagination;

  return (
    <div className="mt-7 space-y-5">
      {parsed?.detail && (
        <Link className={action} to={`?${back}`}>
          Voltar à fila
        </Link>
      )}
      {invalid ? (
        <div
          role="alert"
          className="rounded-xl border border-border bg-surface p-5"
        >
          <p>{invalid}</p>
          <button className={`${action} mt-3`} onClick={() => setParams({})}>
            Limpar filtros
          </button>
        </div>
      ) : null}
      {!invalid && !parsed?.detail && (
        <>
          <form
            key={parsed?.request}
            className="grid gap-4 rounded-2xl border border-border bg-surface p-5 sm:grid-cols-2 lg:grid-cols-4"
            aria-label="Filtros da fila"
            onSubmit={(event) => {
              event.preventDefault();
              const fields = new FormData(event.currentTarget),
                next = new URLSearchParams();
              for (const [key, value] of fields.entries())
                if (typeof value === "string" && value) next.set(key, value);
              next.set("page", "1");
              setParams(next);
            }}
          >
            {Object.entries(filterLabels).map(([key, label]) => (
              <label key={key} className="space-y-2 text-sm">
                <span>{label}</span>
                <select
                  name={key}
                  className={control}
                  defaultValue={params.get(key) ?? ""}
                >
                  <option value="">Todos</option>
                  {Array.from(
                    new Set([
                      ...(queue.data?.data.filter_options[key] ?? []),
                      ...(params.get(key) ? [params.get(key)!] : []),
                    ]),
                  ).map((value) => (
                    <option key={value}>{value}</option>
                  ))}
                </select>
              </label>
            ))}
            <label className="space-y-2 text-sm">
              <span>Ordenar por</span>
              <select
                className={control}
                name="order_by"
                defaultValue={params.get("order_by") ?? "priority"}
              >
                <option value="priority">Prioridade</option>
                <option value="potential_recoverable_energy_kwh">
                  Energia estimada
                </option>
                <option value="uc_id">Número da UC</option>
              </select>
            </label>
            <label className="space-y-2 text-sm">
              <span>Direção</span>
              <select
                className={control}
                name="direction"
                defaultValue={params.get("direction") ?? "desc"}
              >
                <option value="desc">Decrescente</option>
                <option value="asc">Crescente</option>
              </select>
            </label>
            <label className="space-y-2 text-sm">
              <span>UCs por página</span>
              <select
                className={control}
                name="page_size"
                defaultValue={params.get("page_size") ?? "10"}
              >
                {Array.from(
                  new Set([
                    1,
                    10,
                    20,
                    50,
                    Number(params.get("page_size") ?? 10),
                  ]),
                )
                  .sort((a, b) => a - b)
                  .map((size) => (
                    <option key={size}>{size}</option>
                  ))}
              </select>
            </label>
            <div className="flex items-end gap-2">
              <button className={`${action} bg-selected`} type="submit">
                Aplicar
              </button>
              <button
                className={action}
                type="button"
                onClick={() => setParams({})}
              >
                Limpar
              </button>
            </div>
          </form>
          <p className="text-sm text-muted">
            Recorte aplicado:{" "}
            {selected.length
              ? selected
                  .map((key) => `${filterLabels[key]}: ${params.get(key)}`)
                  .join(" · ")
              : "Todos os municípios, bairros, classes e alimentadores"}
            .
          </p>
        </>
      )}
      {!invalid && active.isPending && (
        <p role="status">
          Carregando{" "}
          {parsed?.detail ? "evidências da suspeita" : "fila de inspeção"}…
        </p>
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
            className={`${action} mt-3`}
            onClick={() => void active.refetch()}
          >
            Tentar novamente
          </button>
        </div>
      )}
      {!invalid && active.isFetching && !active.isPending && (
        <p role="status">
          Atualizando evidências; exibindo a última consulta válida.
        </p>
      )}
      {!invalid && active.data && (
        <>
          {metadata && <Provenance metadata={metadata} />}
          {parsed?.detail && detail.data ? (
            <SuspicionDetail data={detail.data.data} />
          ) : (
            queue.data && (
              <section
                className="overflow-hidden rounded-2xl border border-border bg-surface"
                aria-label="Fila de inspeção"
              >
                <div className="border-b border-border p-5">
                  <h2 className="font-heading text-lg font-semibold">
                    UCs para investigar
                  </h2>
                  <p className="mt-1 text-sm text-muted">
                    {page?.total} suspeita(s) no recorte · Pontuação de 0 a 1,
                    sem confirmação de irregularidade.
                  </p>
                </div>
                {queue.data.data.items.length === 0 ? (
                  <div className="space-y-3 p-6">
                    <p>
                      {page?.total === 0
                        ? "Nenhuma suspeita neste recorte. Isso não comprova ausência de perdas."
                        : "Esta página não contém UCs. Volte à primeira página."}
                    </p>
                    <button
                      className={action}
                      onClick={() => {
                        const next = new URLSearchParams(params);
                        next.set("page", "1");
                        setParams(next);
                      }}
                    >
                      Primeira página
                    </button>
                  </div>
                ) : (
                  <div className="overflow-x-auto">
                    <table className="w-full text-left text-sm">
                      <caption className="sr-only">
                        Suspeitas com prioridade, motivo, estimativa e acesso às
                        evidências
                      </caption>
                      <thead className="bg-canvas text-muted">
                        <tr>
                          {[
                            "UC / território",
                            "Prioridade",
                            "Motivo da suspeita",
                            "Energia potencial",
                            "Evidências",
                          ].map((label) => (
                            <th
                              className="px-5 py-4 font-medium"
                              key={label}
                              scope="col"
                            >
                              {label}
                            </th>
                          ))}
                        </tr>
                      </thead>
                      <tbody>
                        {queue.data.data.items.map((item) => {
                          const next = new URLSearchParams(params);
                          next.set("uc", item.uc_id);
                          return (
                            <tr
                              key={item.uc_id}
                              className="border-t border-border"
                            >
                              <th scope="row" className="px-5 py-4 font-normal">
                                <strong className="font-mono">
                                  {item.uc_id}
                                </strong>
                                <span className="mt-1 block text-xs text-muted">
                                  {item.municipality} · {item.neighborhood}
                                  <br />
                                  {item.class_name} · {item.feeder_id}
                                </span>
                              </th>
                              <td className="px-5 py-4">
                                <span className="rounded-full bg-selected px-3 py-1 font-mono font-semibold">
                                  {formatNumber(item.priority)}
                                </span>
                              </td>
                              <td className="min-w-48 px-5 py-4">
                                {item.reason}
                              </td>
                              <td className="px-5 py-4 font-medium">
                                {energy(item.potential_recoverable_energy_kwh)}
                              </td>
                              <td className="px-5 py-4">
                                <Link
                                  className={`${action} whitespace-nowrap`}
                                  to={`?${next}`}
                                  aria-label={`Ver evidências de ${item.uc_id}`}
                                >
                                  Ver evidências
                                </Link>
                              </td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  </div>
                )}
                {page && page.total > 0 && (
                  <nav
                    aria-label="Paginação da fila"
                    className="flex flex-wrap items-center justify-between gap-3 border-t border-border p-5"
                  >
                    <span className="text-sm text-muted">
                      Página {page.page} de {page.total_pages}
                    </span>
                    <div className="flex gap-2">
                      {[
                        ["Anterior", page.page - 1, page.page <= 1],
                        [
                          "Próxima",
                          page.page + 1,
                          page.page >= page.total_pages,
                        ],
                      ].map(([label, number, disabled]) => (
                        <button
                          key={String(label)}
                          className={action}
                          disabled={Boolean(disabled)}
                          onClick={() => {
                            const next = new URLSearchParams(params);
                            next.set("page", String(number));
                            setParams(next);
                          }}
                        >
                          {label}
                        </button>
                      ))}
                    </div>
                  </nav>
                )}
              </section>
            )
          )}
        </>
      )}
    </div>
  );
}
