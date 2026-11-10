import { useId, useLayoutEffect, useRef, useState } from "react";
import {
  ArrowDown,
  ArrowRight,
  ArrowUp,
  ArrowUpDown,
  ArrowUpRight,
  Info,
  Search,
} from "lucide-react";
import { Link } from "react-router-dom";
import type {
  GoldInspectionItem,
  GoldQueueEnvelope,
  QueueEnvelope,
  QueueItem,
} from "./contract";
import { energy, formatNumber } from "./format";
import {
  inspectionAction,
  inspectionControl,
  inspectionPrimary,
} from "./inspection-ui";
import { DEFAULT_PAGE_SIZE } from "./queue-query";
import Pagination from "@/shared/ui/Pagination";

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
      <div className="mt-4 grid gap-3 text-sm">
        <div>
          <p className="text-xs text-muted">Motivo da suspeita</p>
          <p className="mt-1 leading-5">{item.reason}</p>
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

function GoldItemCard({
  item,
  params,
}: {
  item: GoldInspectionItem;
  params: URLSearchParams;
}) {
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
        <GoldRecoverySummary item={item} />
      </div>
      <div className="mt-4 grid gap-2">
        <EvidenceLink item={item} params={params} />
      </div>
    </article>
  );
}

function GoldRecoverySummary({ item }: { item: GoldInspectionItem }) {
  const evidence = item.evidence;
  return (
    <div aria-label="Energia a recuperar">
      <p className="text-xs text-muted">Energia a recuperar</p>
      {item.potential_recoverable_energy_kwh === null ? (
        <p className="mt-1 leading-5">
          Indisponível. {item.recovery_unavailable_reason}
        </p>
      ) : (
        <>
          <p className="mt-1 font-medium">
            {energy(item.potential_recoverable_energy_kwh)}
          </p>
          <p className="mt-1 text-xs leading-5 text-muted">
            Estimativa se a irregularidade se confirmar.
            {evidence.recovery_interval_lower_kwh !== null &&
            evidence.recovery_interval_upper_kwh !== null &&
            evidence.recovery_estimate_confidence_level !== null
              ? ` Faixa nominal de ${Math.round(evidence.recovery_estimate_confidence_level * 100)}%: ${energy(evidence.recovery_interval_lower_kwh)} a ${energy(evidence.recovery_interval_upper_kwh)}.`
              : ""}
          </p>
        </>
      )}
    </div>
  );
}

const ENERGY_FIELD = "potential_recoverable_energy_kwh";

// Na fila Gold, a posição 1 é a mais promissora: "mais relevante primeiro" é
// crescente nesse campo e decrescente em prioridade e energia.
function relevantDirection(column: string) {
  return column === "queue_position" ? "asc" : "desc";
}

// Textos do dicionário Gold (posicao_fila_inspecao) e da tela de fundamentos.
const PRIORITY_RULE_GOLD =
  "Posição única na fila, de 1 a N. Ordena pela categoria (ALTA - HISTORICO IRREGULAR, ALTA - CONSUMO ZERO, MEDIA - NUNCA INSPECIONADO, BAIXA e, por último, REVISAR - SEM HISTORICO DE CONSUMO), depois mais inspeções irregulares, depois maior média de consumo histórico (ausente por último) e, por fim, UC. É ordem de triagem, não estimativa de recuperação nem a prioridade escolhida para a ordem de serviço.";
const PRIORITY_RULE_DEMO =
  "Pontuação de priorização da fila; não é probabilidade de irregularidade. Soma dos pesos dos sinais presentes, limitada a 1 e arredondada a duas casas.";
const PRIORITY_RULE_PUBLISHED =
  "Categoria publicada na Gold. Não há score nem pesos fornecidos nesta versão.";

function PriorityInfo({ text }: { text: string }) {
  const [open, setOpen] = useState(false);
  const button = useRef<HTMLButtonElement>(null);
  const panel = useRef<HTMLDivElement>(null);
  const focusFromPointer = useRef(false);
  const panelId = useId();

  useLayoutEffect(() => {
    if (!open) return;
    // Posição fixa: os contêineres das tabelas cortam o que passa da borda.
    function place() {
      if (!button.current || !panel.current) return;
      const anchor = button.current.getBoundingClientRect();
      const box = panel.current.getBoundingClientRect();
      const fitsBelow = anchor.bottom + 6 + box.height <= innerHeight - 8;
      panel.current.style.left = `${Math.max(8, Math.min(anchor.left, innerWidth - box.width - 8))}px`;
      panel.current.style.top = `${fitsBelow ? anchor.bottom + 6 : Math.max(8, anchor.top - box.height - 6)}px`;
    }
    function closeOutside(event: PointerEvent) {
      const target = event.target as Node;
      if (!button.current?.contains(target) && !panel.current?.contains(target))
        setOpen(false);
    }
    function closeOnEscape(event: KeyboardEvent) {
      if (event.key === "Escape") setOpen(false);
    }
    place();
    window.addEventListener("scroll", place, true);
    window.addEventListener("resize", place);
    document.addEventListener("pointerdown", closeOutside);
    document.addEventListener("keydown", closeOnEscape);
    return () => {
      window.removeEventListener("scroll", place, true);
      window.removeEventListener("resize", place);
      document.removeEventListener("pointerdown", closeOutside);
      document.removeEventListener("keydown", closeOnEscape);
    };
  }, [open]);

  return (
    <>
      <button
        ref={button}
        type="button"
        aria-label="Como a prioridade é calculada"
        aria-expanded={open}
        aria-controls={panelId}
        aria-describedby={panelId}
        className="inline-flex size-8 shrink-0 items-center justify-center rounded-md hover:bg-surface-hover focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand"
        onPointerDown={() => {
          focusFromPointer.current = true;
        }}
        onClick={() => {
          focusFromPointer.current = false;
          setOpen((current) => !current);
        }}
        onFocus={() => {
          if (!focusFromPointer.current) setOpen(true);
        }}
        onBlur={(event) => {
          if (event.relatedTarget) setOpen(false);
        }}
      >
        <Info size={14} aria-hidden="true" />
      </button>
      <div
        ref={panel}
        id={panelId}
        role="tooltip"
        hidden={!open}
        className="fixed z-50 w-72 max-w-[calc(100vw-1rem)] rounded-lg border border-border bg-surface p-3 text-left text-sm leading-5 font-normal text-content shadow-md"
      >
        {text}
      </div>
    </>
  );
}

function QueueHeader({
  label,
  column,
  info,
  field,
  direction,
  onSort,
  className,
}: {
  label: string;
  column?: string;
  info?: string;
  field: string;
  direction: string;
  onSort: (column: string) => void;
  className: string;
}) {
  if (!column) {
    return (
      <th scope="col" className={className}>
        {label}
      </th>
    );
  }
  const active = field === column;
  const Icon = !active
    ? ArrowUpDown
    : direction === "asc"
      ? ArrowUp
      : ArrowDown;
  return (
    <th
      scope="col"
      className={className}
      aria-label={info ? label : undefined}
      aria-sort={
        !active ? "none" : direction === "asc" ? "ascending" : "descending"
      }
    >
      <span className="flex items-center gap-1">
        <button
          type="button"
          className="inline-flex min-h-11 min-w-0 items-center gap-1 text-left font-normal hover:underline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand"
          onClick={() => onSort(column)}
        >
          {label}
          <Icon
            size={14}
            aria-hidden="true"
            className={active ? "shrink-0" : "shrink-0 opacity-50"}
          />
        </button>
        {info ? <PriorityInfo text={info} /> : null}
      </span>
    </th>
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
  const pageSize = Number(params.get("page_size") ?? DEFAULT_PAGE_SIZE);
  const gold = result.metadata.contract_version === "2.0.0";
  const legacyGold = result.metadata.source.kind === "gold_csv";
  const field =
    params.get("order_by") ?? (gold ? "queue_position" : "priority");
  const direction =
    params.get("direction") ??
    (gold && field === "queue_position" ? "asc" : "desc");
  const priorityRule = gold
    ? PRIORITY_RULE_GOLD
    : result.metadata.source.is_demo
      ? PRIORITY_RULE_DEMO
      : PRIORITY_RULE_PUBLISHED;
  const sortLabels: Record<string, string> = gold
    ? {
        queue_position: "Posição oficial da fila",
        [ENERGY_FIELD]: "Energia recuperável estimada",
        uc_id: "Número da UC",
        category: "Categoria",
      }
    : {
        priority: "Prioridade demonstrativa",
        [ENERGY_FIELD]: "Energia estimada",
        uc_id: "Número da UC",
        category: "Categoria",
      };
  const sortColumns = gold
    ? ["queue_position", ENERGY_FIELD]
    : legacyGold
      ? ["priority"]
      : ["priority", ENERGY_FIELD];
  const sortChoices = sortColumns.flatMap((column) => {
    const first = relevantDirection(column);
    return [first, first === "asc" ? "desc" : "asc"].map((choice) => ({
      column,
      choice,
    }));
  });
  // Links com UC ou categoria não têm opção fixa: o controle mostra a ordem real.
  if (!sortColumns.includes(field))
    sortChoices.push({ column: field, choice: direction });

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

  function updateSort(column: string, nextDirection: string) {
    const next = new URLSearchParams(params);
    next.set("order_by", column);
    next.set("direction", nextDirection);
    next.set("page", "1");
    onChange(next);
  }

  function sortBy(column: string) {
    updateSort(
      column,
      column !== field
        ? relevantDirection(column)
        : direction === "asc"
          ? "desc"
          : "asc",
    );
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
        className="flex items-end gap-3 md:hidden"
      >
        <label className="min-w-0 flex-1 space-y-2 text-sm">
          <span>Ordenar por</span>
          <select
            aria-label="Ordenar por"
            className={inspectionControl}
            value={`${field}:${direction}`}
            onChange={(event) => {
              const [column, choice] = event.target.value.split(":");
              updateSort(column, choice);
            }}
          >
            {sortChoices.map(({ column, choice }) => (
              <option key={`${column}:${choice}`} value={`${column}:${choice}`}>
                {sortLabels[column] ?? column} (
                {choice === "asc" ? "crescente" : "decrescente"})
              </option>
            ))}
            {legacyGold && (
              <option value="" disabled>
                Energia estimada (indisponível)
              </option>
            )}
          </select>
        </label>
      </div>
      <div className="space-y-4 rounded-xl bg-surface p-4">
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
                <div className="hidden overflow-hidden rounded-xl bg-surface p-4 md:block">
                  <table className="w-full table-fixed text-left">
                    <caption className="caption-top pb-4 text-left text-sm font-normal text-muted">
                      <span>
                        Estimativas condicionais:{" "}
                        {result.data.summary.estimated_units} UCs disponíveis e{" "}
                        {result.data.summary.unavailable_estimate_units} sem
                        estimativa válida.
                      </span>
                      <span className="sr-only">
                        Categorias, motivos, energia a recuperar e acesso ao
                        detalhe
                      </span>
                    </caption>
                    <colgroup>
                      <col className="w-[26%]" />
                      <col className="w-[26%]" />
                      <col className="w-[32%]" />
                      <col className="w-[16%]" />
                    </colgroup>
                    <thead className="font-sans text-xs leading-[18px] text-muted">
                      <tr className="h-11">
                        {[
                          {
                            label: "Posição / UC / categoria",
                            column: "queue_position",
                            info: priorityRule,
                          },
                          { label: "Motivo" },
                          {
                            label: "Energia a recuperar",
                            column: ENERGY_FIELD,
                          },
                          { label: "Ação" },
                        ].map(({ label, column, info }) => (
                          <QueueHeader
                            key={label}
                            label={label}
                            column={column}
                            info={info}
                            field={field}
                            direction={direction}
                            onSort={sortBy}
                            className="pr-2 text-left font-normal"
                          />
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
                          <td className="break-words py-3 pr-2">
                            {item.reason ?? "Não informado"}
                          </td>
                          <td className="py-3 pr-2 text-sm">
                            <GoldRecoverySummary item={item} />
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
                    Estimativas condicionais:{" "}
                    {(result as GoldQueueEnvelope).data.summary.estimated_units}{" "}
                    UCs disponíveis e{" "}
                    {
                      (result as GoldQueueEnvelope).data.summary
                        .unavailable_estimate_units
                    }{" "}
                    sem estimativa válida.
                  </p>
                  {(items as GoldInspectionItem[]).map((item) => (
                    <GoldItemCard
                      key={item.uc_id}
                      item={item}
                      params={params}
                    />
                  ))}
                </div>
              </>
            ) : (
              <div className="hidden overflow-x-auto rounded-xl bg-surface p-4 md:block">
                <table className="w-full table-fixed text-left text-sm">
                  <caption className="sr-only">
                    Suspeitas com prioridade, motivo, energia estimada e acesso
                    ao detalhe
                  </caption>
                  <colgroup>
                    <col className={legacyGold ? "w-[25%]" : "w-[20%]"} />
                    <col className={legacyGold ? "w-[50%]" : "w-[36%]"} />
                    {!legacyGold && <col className="w-[22%]" />}
                    <col className={legacyGold ? "w-[25%]" : "w-[22%]"} />
                  </colgroup>
                  <thead className="font-sans text-xs leading-[18px] text-muted [&_th]:font-normal">
                    <tr>
                      {[
                        {
                          label: "UC / prioridade",
                          column: "priority",
                          info: priorityRule,
                        },
                        { label: "Motivo da suspeita" },
                        ...(!legacyGold
                          ? [
                              {
                                label: "Energia estimada",
                                column: ENERGY_FIELD,
                              },
                            ]
                          : []),
                        { label: "Ação" },
                      ].map(({ label, column, info }) => (
                        <QueueHeader
                          key={label}
                          label={label}
                          column={column}
                          info={info}
                          field={field}
                          direction={direction}
                          onSort={sortBy}
                          className="px-3 pb-3 text-left font-normal"
                        />
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
          </>
        )}
        {page.total > 0 ? (
          <Pagination
            label="Paginação da fila"
            page={page.page}
            totalPages={page.total_pages}
            pageSize={pageSize}
            onPageChange={goTo}
            onPageSizeChange={(size) =>
              updateQueueOption("page_size", String(size))
            }
          />
        ) : null}
      </div>
      {items.length > 0 && (
        <Link
          className={`${inspectionPrimary} w-full sm:w-fit`}
          to={evidenceUrl(params, items[0].uc_id)}
          aria-label={`Investigar ${items[0].uc_id}`}
        >
          Investigar {items[0].uc_id}
          <ArrowUpRight size={16} aria-hidden="true" />
        </Link>
      )}
    </section>
  );
}
