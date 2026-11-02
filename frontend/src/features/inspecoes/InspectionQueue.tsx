import {
  ArrowRight,
  ArrowUpRight,
  ChevronLeft,
  ChevronRight,
  Search,
} from "lucide-react";
import { Link } from "react-router-dom";
import type { GoldInspectionItem, QueueEnvelope, QueueItem } from "./contract";
import { energy, formatNumber } from "./format";
import {
  inspectionAction,
  inspectionControl,
  inspectionPrimary,
} from "./inspection-ui";

function evidenceUrl(params: URLSearchParams, uc: string) {
  const next = new URLSearchParams(params);
  next.set("uc", uc);
  return `?${next}`;
}

function EvidenceLink({
  item,
  params,
}: {
  item: Pick<QueueItem, "uc_id">;
  params: URLSearchParams;
}) {
  return (
    <Link
      className="inline-flex min-h-11 items-center gap-1 px-1 text-sm font-medium text-content underline decoration-border underline-offset-4 hover:decoration-content focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand"
      to={evidenceUrl(params, item.uc_id)}
      aria-label={`Ver evidência de ${item.uc_id}`}
    >
      Ver evidência <ArrowRight size={14} aria-hidden="true" />
    </Link>
  );
}

function ItemCard({
  item,
  params,
  hideEstimate,
}: {
  item: QueueItem;
  params: URLSearchParams;
  hideEstimate: boolean;
}) {
  return (
    <article
      aria-label={`Suspeita ${item.uc_id}`}
      className="rounded-lg border border-border bg-surface p-4"
    >
      <p className="text-xs text-muted">UC / prioridade</p>
      <h3 className="mt-1 font-heading text-lg leading-[26px] font-semibold">
        {item.uc_id} /{" "}
        <span
          aria-label={
            item.priority_label ??
            `Prioridade ${formatNumber(item.priority ?? 0)} em 1`
          }
        >
          {item.priority_label ?? formatNumber(item.priority ?? 0)}
        </span>
      </h3>
      <div className="mt-4 grid grid-cols-2 gap-3 text-sm">
        <div>
          <p className="text-xs text-muted">Motivo da suspeita</p>
          <p className="mt-1 leading-5">{item.reason}</p>
        </div>
        <div>
          <p className="text-xs text-muted">Indicador usado</p>
          <p className="mt-1 leading-5">
            {item.signals.length
              ? item.signals.map((signal) => signal.label).join(" · ")
              : "Sem indicador informado"}
          </p>
        </div>
      </div>
      <div className="mt-4 grid gap-2">
        {!hideEstimate && (
          <div>
            <p className="text-xs text-muted">Energia estimada</p>
            <p className="mt-1 text-sm font-medium">
              {energy(item.potential_recoverable_energy_kwh)}
            </p>
            <p className="mt-1 text-xs text-muted">
              {item.potential_recoverable_energy_kwh === null
                ? "Insumos comparáveis indisponíveis"
                : "Projeção hipotética em kWh"}
            </p>
          </div>
        )}
        <EvidenceLink item={item} params={params} />
      </div>
    </article>
  );
}

function goldEvidence(item: GoldInspectionItem) {
  const evidence = item.evidence;
  const text = (value: string | null) => value ?? "indisponível";
  return [
    evidence.inspections_performed === null
      ? "Inspeções realizadas: indisponível"
      : `Inspeções realizadas: ${formatNumber(evidence.inspections_performed)}`,
    evidence.confirmed_irregular_inspections === null
      ? "Irregularidades confirmadas: indisponível"
      : `Irregularidades confirmadas: ${formatNumber(evidence.confirmed_irregular_inspections)}`,
    evidence.historical_average_kwh_per_reading === null
      ? "Média histórica: indisponível"
      : `Média histórica: ${formatNumber(evidence.historical_average_kwh_per_reading)} kWh/leitura`,
    `Geração distribuída: ${text(evidence.distributed_generation_present)}`,
    `Situação cadastral: ${text(evidence.cadastral_status)}`,
    evidence.call_center_contacts === null
      ? "Contatos ao atendimento: indisponível"
      : `Contatos ao atendimento: ${formatNumber(evidence.call_center_contacts)}`,
    evidence.interruptions === null
      ? "Interrupções: indisponível"
      : `Interrupções: ${formatNumber(evidence.interruptions)}`,
  ];
}

function GoldItemCard({
  item,
  params,
}: {
  item: GoldInspectionItem;
  params: URLSearchParams;
}) {
  const evidence = goldEvidence(item);
  return (
    <article
      aria-label={`UC ${item.uc_id}`}
      className="rounded-lg border border-border bg-surface p-4"
    >
      <p className="text-xs text-muted">UC / categoria</p>
      <p className="mt-1 text-xs text-muted">
        Posição oficial na fila: {item.queue_position}
      </p>
      <h3 className="mt-1 font-heading text-lg leading-[26px] font-semibold">
        {item.uc_id} / {item.category ?? "Sem categoria"}
      </h3>
      <div className="mt-4 grid gap-3 text-sm">
        <div>
          <p className="text-xs text-muted">Motivo registrado</p>
          <p className="mt-1 leading-5">{item.reason ?? "Não informado"}</p>
        </div>
        <div>
          <p className="text-xs text-muted">Evidências publicadas</p>
          <p className="mt-1 leading-5">
            {evidence.join(" · ") || "Sem evidências disponíveis"}
          </p>
        </div>
      </div>
      <div className="mt-4 grid gap-2">
        <EvidenceLink item={item} params={params} />
      </div>
    </article>
  );
}

export default function InspectionQueue({
  result,
  params,
  onChange,
}: {
  result: QueueEnvelope;
  params: URLSearchParams;
  onChange: (next: URLSearchParams) => void;
}) {
  const { items } = result.data;
  const page = result.pagination;
  const gold = result.metadata.contract_version === "2.0.0";
  const legacyGold = result.metadata.source.kind === "gold_csv";
  const field =
    params.get("order_by") ?? (gold ? "queue_position" : "priority");
  const direction = params.get("direction") ?? (gold ? "asc" : "desc");
  const sortDescription = `${gold ? (field === "category" ? "Categoria" : field === "uc_id" ? "Número da UC" : "Posição oficial da fila") : field === "priority" ? "Prioridade demonstrativa" : field === "uc_id" ? "Número da UC" : "Energia estimada"} ${direction === "desc" ? "decrescente" : "crescente"}`;

  function goTo(number: number) {
    const next = new URLSearchParams(params);
    next.set("page", String(number));
    onChange(next);
  }

  function updateQueueOption(key: string, value: string) {
    const next = new URLSearchParams(params);
    next.set(key, value);
    next.set("page", "1");
    onChange(next);
  }

  return (
    <section
      aria-label="Fila de inspeção"
      className="min-w-0 space-y-5 md:space-y-6"
    >
      <h2 className="sr-only">
        {gold ? "Fila de triagem" : "Fila priorizada"}
      </h2>
      <div
        aria-label="Controles da fila"
        className="grid gap-3 rounded-xl bg-surface p-4 sm:grid-cols-2 lg:grid-cols-3"
      >
        <label className="space-y-2 text-sm">
          <span>Ordenar por</span>
          <select
            aria-label="Ordenar por"
            className={inspectionControl}
            value={field}
            onChange={(event) =>
              updateQueueOption("order_by", event.target.value)
            }
          >
            {gold ? (
              <>
                <option value="queue_position">Posição oficial da fila</option>
                <option value="uc_id">Número da UC</option>
                <option value="category">Categoria</option>
              </>
            ) : (
              <>
                <option value="priority">Prioridade demonstrativa</option>
                <option
                  value="potential_recoverable_energy_kwh"
                  disabled={legacyGold}
                >
                  Energia estimada{legacyGold ? " (indisponível)" : ""}
                </option>
                <option value="uc_id">Número da UC</option>
              </>
            )}
          </select>
        </label>
        <label className="space-y-2 text-sm">
          <span>Direção</span>
          <select
            aria-label="Direção da ordenação"
            className={inspectionControl}
            value={direction}
            onChange={(event) =>
              updateQueueOption("direction", event.target.value)
            }
          >
            <option value="desc">Decrescente</option>
            <option value="asc">Crescente</option>
          </select>
        </label>
        <label className="space-y-2 text-sm">
          <span>UCs por página</span>
          <select
            aria-label="UCs por página"
            className={inspectionControl}
            value={params.get("page_size") ?? String(page.page_size)}
            onChange={(event) =>
              updateQueueOption("page_size", event.target.value)
            }
          >
            {Array.from(
              new Set([
                1,
                10,
                20,
                50,
                Number(params.get("page_size") ?? page.page_size),
              ]),
            )
              .sort((left, right) => left - right)
              .map((size) => (
                <option key={size} value={size}>
                  {size}
                </option>
              ))}
          </select>
        </label>
      </div>
      {items.length === 0 ? (
        <div className="flex flex-col items-center gap-3 px-2 py-10 text-center">
          <Search size={28} className="text-muted" aria-hidden="true" />
          <h3 className="font-heading text-lg font-semibold">
            {page.total === 0
              ? "Nenhuma UC nesta fila"
              : "Página sem resultados"}
          </h3>
          <p className="max-w-md text-sm text-muted">
            {page.total === 0
              ? gold
                ? "Nenhuma UC neste recorte da publicação atual. Isso não comprova ausência de perdas."
                : "Nenhuma suspeita neste recorte. Isso não comprova ausência de perdas."
              : "Esta página não contém UCs. Volte à primeira página."}
          </p>
          <button
            className={inspectionAction}
            onClick={() =>
              page.total === 0 ? onChange(new URLSearchParams()) : goTo(1)
            }
          >
            {page.total === 0 ? "Limpar filtros" : "Primeira página"}
          </button>
        </div>
      ) : (
        <>
          {gold ? (
            <>
              <div className="hidden overflow-x-auto rounded-xl bg-surface p-4 md:block">
                <table className="w-full table-fixed text-left">
                  <caption className="caption-top pb-4 text-left text-sm font-normal text-muted">
                    <span>
                      Energia recuperável individual indisponível. Consulte o
                      detalhe para conhecer a limitação de cada UC.
                    </span>
                    <span className="sr-only">
                      Categorias, motivos, evidências e acesso ao detalhe
                    </span>
                  </caption>
                  <colgroup>
                    <col className="w-[21%]" />
                    <col className="w-[25%]" />
                    <col className="w-[38%]" />
                    <col className="w-[16%]" />
                  </colgroup>
                  <thead className="font-mono text-xs leading-[18px] text-muted">
                    <tr className="h-11">
                      {[
                        "Posição / UC / categoria",
                        "Motivo",
                        "Evidências publicadas",
                        "Ação",
                      ].map((label) => (
                        <th
                          scope="col"
                          className="pr-2 text-left font-normal"
                          key={label}
                        >
                          {label}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody className="text-sm leading-[22px]">
                    {(items as GoldInspectionItem[]).map((item) => (
                      <tr
                        key={item.uc_id}
                        className="h-14 border-t border-border/60 align-middle transition-colors hover:bg-surface-hover"
                      >
                        <th
                          scope="row"
                          className="break-words py-3 pr-2 text-left font-medium"
                        >
                          <p className="mb-1 text-xs text-muted">
                            Posição oficial na fila: {item.queue_position}
                          </p>
                          <p>{item.uc_id}</p>
                          <p>{item.category ?? "Sem categoria"}</p>
                        </th>
                        <td className="py-3 pr-2">
                          {item.reason ?? "Não informado"}
                        </td>
                        <td className="py-3 pr-2 text-muted">
                          {goldEvidence(item).join(" · ") ||
                            "Sem evidências disponíveis"}
                        </td>
                        <td className="py-1">
                          <EvidenceLink item={item} params={params} />
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <div className="space-y-3 md:hidden">
                <p className="px-1 text-sm text-muted">
                  Estimativa individual indisponível. Consulte o detalhe da UC
                  para conhecer os dados e limites disponíveis.
                </p>
                {(items as GoldInspectionItem[]).map((item) => (
                  <GoldItemCard key={item.uc_id} item={item} params={params} />
                ))}
              </div>
              <p className="text-xs leading-5 text-muted">
                Ordenação por{" "}
                {field === "category"
                  ? "texto da categoria"
                  : field === "queue_position"
                    ? "posição oficial da fila"
                    : "UC"}{" "}
                {direction === "desc" ? "decrescente" : "crescente"}. Ela não
                define prioridade de despacho.
              </p>
            </>
          ) : (
            <div className="hidden overflow-x-auto rounded-xl bg-surface p-4 md:block">
              <table className="w-full table-fixed text-left text-sm">
                <caption className="sr-only">
                  Suspeitas com prioridade, motivo, indicadores usados, energia
                  estimada e acesso às evidências
                </caption>
                <colgroup>
                  <col className="w-[15%]" />
                  <col className="w-[25%]" />
                  <col className="w-[17%]" />
                  {!legacyGold && <col className="w-[19%]" />}
                  <col className="w-[24%]" />
                </colgroup>
                <thead className="font-mono text-xs leading-[18px] text-muted [&_th]:font-normal">
                  <tr>
                    {[
                      "UC / prioridade",
                      "Motivo da suspeita",
                      "Indicador usado",
                      ...(!legacyGold ? ["Energia estimada"] : []),
                      "Ação",
                    ].map((label) => (
                      <th
                        scope="col"
                        className="px-3 pb-3 text-left font-normal"
                        key={label}
                      >
                        {label}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {(items as QueueItem[]).map((item) => (
                    <tr
                      key={item.uc_id}
                      className="border-t border-border/60 align-middle transition-colors hover:bg-surface-hover"
                    >
                      <th
                        scope="row"
                        className="break-words px-3 py-3 text-left font-normal"
                      >
                        <p className="font-sans leading-[22px]">
                          {item.uc_id} /{" "}
                          {item.priority_label ??
                            formatNumber(item.priority ?? 0)}
                        </p>
                      </th>
                      <td className="px-3 py-3 leading-5">{item.reason}</td>
                      <td className="px-3 py-3 text-sm leading-5 text-muted">
                        {item.signals.length
                          ? item.signals
                              .map((signal) => signal.label)
                              .join(" · ")
                          : "Sem indicador informado"}
                      </td>
                      {!legacyGold && (
                        <td className="px-3 py-3">
                          <p className="font-medium">
                            {energy(item.potential_recoverable_energy_kwh)}
                          </p>
                          <p className="mt-1 text-xs leading-4 text-muted">
                            {item.potential_recoverable_energy_kwh === null
                              ? "Insumos indisponíveis"
                              : "Projeção hipotética"}
                          </p>
                        </td>
                      )}
                      <td className="px-3 py-3">
                        <EvidenceLink item={item} params={params} />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          {!gold ? (
            <div className="space-y-3 md:hidden">
              {(items as QueueItem[]).map((item) => (
                <ItemCard
                  key={item.uc_id}
                  item={item}
                  params={params}
                  hideEstimate={legacyGold}
                />
              ))}
            </div>
          ) : null}
          <div className="flex flex-col gap-3">
            <Link
              className={`${inspectionPrimary} w-full sm:w-fit`}
              to={evidenceUrl(params, items[0].uc_id)}
              aria-label={`Investigar ${items[0].uc_id}`}
            >
              Investigar {items[0].uc_id}
              <ArrowUpRight size={16} aria-hidden="true" />
            </Link>
            <p className="text-xs leading-5 text-muted">
              Ordenação: {sortDescription}.
              {gold
                ? " Categoria textual não equivale a prioridade de despacho."
                : " Empates seguem energia disponível e número da UC; indisponibilidade permanece explícita."}
            </p>
          </div>
        </>
      )}
      {page.total > 0 ? (
        <nav
          aria-label="Paginação da fila"
          className="flex flex-wrap items-center justify-between gap-3"
        >
          <p className="text-xs text-muted">
            Página {page.page} de {page.total_pages} · {page.total} UC(s) no
            recorte
          </p>
          <div className="flex gap-2">
            <button
              className={inspectionAction}
              disabled={page.page <= 1}
              onClick={() => goTo(page.page - 1)}
            >
              <ChevronLeft size={15} aria-hidden="true" />
              Anterior
            </button>
            <button
              className={inspectionAction}
              disabled={page.page >= page.total_pages}
              onClick={() => goTo(page.page + 1)}
            >
              Próxima
              <ChevronRight size={15} aria-hidden="true" />
            </button>
          </div>
        </nav>
      ) : null}
    </section>
  );
}
