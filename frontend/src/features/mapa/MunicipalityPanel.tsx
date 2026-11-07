import { useState, type Ref } from "react";
import { ArrowUp, X } from "lucide-react";
import { useNavigate } from "react-router-dom";
import type { RevenueEnvelope } from "@/shared/analytics/revenueContract";
import type { TerritoryMunicipality } from "./municipalities";
import Button from "@/shared/ui/Button";
import { signedValueTone } from "@/shared/ui/signedValue";
import type { MapLayer, MapQuery } from "./map-state";
import {
  energyValue,
  formatCompetence,
  formatPeriod,
  moneyValue,
  neighborhoodLabel,
  signedEnergy,
  signedMoney,
} from "./map-format";
import PanelTabs from "./PanelTabs";
import { tabId, tabPanelId } from "./tab-ids";

const VISIBLE_NEIGHBORHOODS = 8;
const VISIBLE_MONTHS = 12;

type BreakdownRow = RevenueEnvelope["data"]["breakdown"]["items"][number];

function Kpi({
  label,
  initial,
  final,
  change,
  initialCaption,
  finalCaption,
  format,
  formatChange,
}: {
  label: string;
  initial: number | null;
  final: number | null;
  change: number | null;
  initialCaption: string;
  finalCaption: string;
  format: (value: number | null) => string;
  formatChange: (value: number | null) => string;
}) {
  const arrow = change === null || change === 0 ? "" : change > 0 ? "▲" : "▼";
  return (
    <div className="rounded-lg border border-border p-3">
      <h3 className="text-xs font-medium text-muted">{label}</h3>
      <p className="mt-1 text-xl font-semibold tabular-nums text-content">
        {format(final)}
      </p>
      <p className="text-xs text-muted">em {finalCaption}</p>
      <p
        className={`mt-2 text-sm font-semibold tabular-nums ${signedValueTone(change)}`}
      >
        {arrow ? (
          <span aria-hidden="true" className="mr-1 text-xs">
            {arrow}
          </span>
        ) : null}
        {formatChange(change)}
        <span className="sr-only"> de variação absoluta</span>
        <span className="ml-1 text-xs font-normal text-muted">
          desde {initialCaption}
        </span>
      </p>
      <p className="mt-1 text-xs text-muted">Inicial: {format(initial)}</p>
    </div>
  );
}

function ShowMore({
  expanded,
  total,
  collapsedLabel,
  onToggle,
}: {
  expanded: boolean;
  total: number;
  collapsedLabel: string;
  onToggle: () => void;
}) {
  return (
    <button
      type="button"
      aria-expanded={expanded}
      onClick={onToggle}
      className="mt-2 min-h-11 cursor-pointer rounded px-1 text-sm font-medium text-content underline underline-offset-4 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand"
    >
      {expanded ? "Mostrar menos" : `${collapsedLabel} (${total})`}
    </button>
  );
}

function changeOf(row: BreakdownRow) {
  return row.comparison.billed_amount_change_brl;
}

function Neighborhoods({
  envelope,
  municipalityName,
}: {
  envelope: RevenueEnvelope;
  municipalityName: string;
}) {
  const [expanded, setExpanded] = useState(false);
  const rows = envelope.data.breakdown.items;
  // Quem perdeu mais fica no topo: é a leitura que responde "onde caiu".
  const comparable = rows
    .filter(
      (row) =>
        row.comparison.initial.billed_amount !== null &&
        row.comparison.final.billed_amount !== null,
    )
    .sort((a, b) => (changeOf(a) ?? 0) - (changeOf(b) ?? 0));
  const visible = expanded
    ? comparable
    : comparable.slice(0, VISIBLE_NEIGHBORHOODS);
  return (
    <div className="min-w-0">
      <p className="mt-3 text-xs leading-5 text-muted">
        Faturamento por bairro, da maior queda para a maior alta.
      </p>
      {comparable.length === 0 ? (
        <p role="status" className="mt-2 text-sm text-muted">
          Nenhum bairro tem comparação nos dois extremos neste período.
        </p>
      ) : (
        <div className="mt-2 overflow-x-auto rounded-lg border border-border">
          <table className="w-full min-w-[430px] border-collapse text-left text-xs">
            <caption className="sr-only">
              Faturamento inicial, final e variação absoluta por bairro
            </caption>
            <thead className="bg-surface text-muted">
              <tr>
                <th className="px-3 py-2 font-medium">Bairro</th>
                <th className="px-3 py-2 text-right font-medium">Inicial</th>
                <th className="px-3 py-2 text-right font-medium">Final</th>
                <th className="px-3 py-2 text-right font-medium">Variação</th>
              </tr>
            </thead>
            <tbody>
              {visible.map((row) => (
                <tr key={row.key} className="border-t border-border">
                  <th
                    scope="row"
                    className="px-3 py-2 font-medium text-content"
                  >
                    {neighborhoodLabel(row.label, municipalityName)}
                  </th>
                  <td className="px-3 py-2 text-right tabular-nums text-content">
                    {moneyValue(row.comparison.initial.billed_amount)}
                  </td>
                  <td className="px-3 py-2 text-right tabular-nums text-content">
                    {moneyValue(row.comparison.final.billed_amount)}
                  </td>
                  <td
                    className={`px-3 py-2 text-right font-medium tabular-nums ${signedValueTone(changeOf(row))}`}
                  >
                    {signedMoney(changeOf(row))}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {comparable.length > VISIBLE_NEIGHBORHOODS ? (
        <ShowMore
          expanded={expanded}
          total={comparable.length}
          collapsedLabel="Mostrar todos"
          onToggle={() => setExpanded(!expanded)}
        />
      ) : null}
    </div>
  );
}

function MonthlySeries({ envelope }: { envelope: RevenueEnvelope }) {
  const [expanded, setExpanded] = useState(false);
  const series = envelope.data.series;
  // Por padrão, os meses mais recentes; a série completa fica a um clique.
  const visible = expanded ? series : series.slice(-VISIBLE_MONTHS);
  return (
    <div className="min-w-0">
      {series.length === 0 ? (
        <p role="status" className="mt-3 text-sm text-muted">
          Sem série mensal neste recorte.
        </p>
      ) : (
        <div className="mt-3 overflow-x-auto rounded-lg border border-border">
          <table className="w-full min-w-[380px] border-collapse text-left text-xs">
            <caption className="sr-only">
              Série mensal do município selecionado
            </caption>
            <thead className="bg-surface text-muted">
              <tr>
                <th className="px-3 py-2 font-medium">Competência</th>
                <th className="px-3 py-2 text-right font-medium">
                  Faturamento
                </th>
                <th className="px-3 py-2 text-right font-medium">
                  Consumo medido
                </th>
              </tr>
            </thead>
            <tbody>
              {visible.map((month) => (
                <tr key={month.competencia} className="border-t border-border">
                  <th
                    scope="row"
                    className="px-3 py-2 font-medium text-content"
                  >
                    {formatCompetence(month.competencia)}
                  </th>
                  <td className="px-3 py-2 text-right tabular-nums text-content">
                    {moneyValue(month.billed_amount)}
                  </td>
                  <td className="px-3 py-2 text-right tabular-nums text-content">
                    {energyValue(month.measured_energy_kwh)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {series.length > VISIBLE_MONTHS ? (
        <ShowMore
          expanded={expanded}
          total={series.length}
          collapsedLabel="Mostrar série completa"
          onToggle={() => setExpanded(!expanded)}
        />
      ) : null}
    </div>
  );
}

function Caveats({
  envelope,
  municipalityName,
}: {
  envelope: RevenueEnvelope;
  municipalityName: string;
}) {
  const rows = envelope.data.breakdown.items;
  const incomplete = rows.filter(
    (row) =>
      row.comparison.initial.billed_amount === null ||
      row.comparison.final.billed_amount === null,
  );
  const limitations = envelope.data.breakdown.reconciliation.limitations;
  const count = (incomplete.length ? 1 : 0) + limitations.length;
  if (count === 0) return null;
  return (
    <details className="mt-4 rounded-lg border border-border text-xs">
      <summary className="cursor-pointer px-3 py-2.5 text-sm font-medium text-content">
        Ressalvas ({count})
      </summary>
      <div className="grid gap-2 border-t border-border px-3 py-3 leading-5 text-muted">
        <p>
          Variações conhecidas não representam reconciliação completa quando há
          bairros sem comparação ou valor residual.
        </p>
        {incomplete.length ? (
          <div>
            <h4 className="font-semibold text-content">
              Sem comparação nos dois extremos ({incomplete.length})
            </h4>
            <ul className="mt-1 list-inside list-disc">
              {incomplete.map((row) => (
                <li key={row.key}>
                  {neighborhoodLabel(row.label, municipalityName)} · faturamento
                  indisponível em pelo menos um extremo
                </li>
              ))}
            </ul>
          </div>
        ) : null}
        {limitations.length ? (
          <ul className="list-inside list-disc">
            {limitations.map((limitation) => (
              <li key={limitation}>{limitation}</li>
            ))}
          </ul>
        ) : null}
      </div>
    </details>
  );
}

export default function MunicipalityPanel({
  municipality,
  item,
  detail,
  detailError,
  query,
  layer,
  revenueHref,
  onRetryDetail,
  onBackToMap,
  onClearSelection,
  ref,
}: {
  municipality: TerritoryMunicipality | null;
  item: RevenueEnvelope["data"]["breakdown"]["items"][number] | null;
  detail: RevenueEnvelope | undefined;
  detailError: boolean;
  query: MapQuery | null;
  layer: MapLayer;
  revenueHref: string | null;
  onRetryDetail: () => void;
  onBackToMap?: () => void;
  onClearSelection?: () => void;
  ref?: Ref<HTMLElement>;
}) {
  const navigate = useNavigate();
  const [tab, setTab] = useState("neighborhoods");
  // A instrução "clique em um município" já está na lista; sem seleção não há
  // o que detalhar e um cartão vazio só ocupava espaço.
  if (!municipality) return null;
  const row = item;
  const comparison = row?.comparison ?? detail?.data.comparison;
  const monthCaption = query
    ? formatPeriod(query.competencia_inicio, query.competencia_fim)
    : "período selecionado";
  const initialCaption = query
    ? formatCompetence(query.competencia_inicio)
    : "o início";
  const finalCaption = query
    ? formatCompetence(query.competencia_fim)
    : "o fim";
  const prefix = `mapa-${municipality.code}`;
  return (
    <section
      ref={ref}
      className="scroll-mt-4 min-w-0 rounded-xl border border-border bg-surface p-4 sm:p-5"
      aria-label={`Detalhe de ${municipality.name}`}
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-xs font-medium uppercase tracking-wide text-muted">
            Município selecionado
          </p>
          <h2 className="mt-1 font-heading text-xl font-semibold text-content">
            {municipality.name}
          </h2>
          <p className="mt-1 font-mono text-[11px] text-muted">
            IBGE {municipality.code} · {monthCaption}
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {onBackToMap ? (
            <Button
              variant="ghost"
              size="sm"
              leftIcon={<ArrowUp aria-hidden="true" className="size-4" />}
              onClick={onBackToMap}
            >
              Voltar ao mapa
            </Button>
          ) : null}
          {onClearSelection ? (
            <Button
              variant="ghost"
              size="sm"
              leftIcon={<X aria-hidden="true" className="size-4" />}
              onClick={onClearSelection}
            >
              Limpar seleção
            </Button>
          ) : null}
          {revenueHref ? (
            <Button variant="primary" onClick={() => navigate(revenueHref)}>
              Investigar na Receita
            </Button>
          ) : (
            <span className="text-xs text-muted">
              Detalhe não disponível nesta publicação
            </span>
          )}
        </div>
      </div>
      {!row && !detail ? (
        <p
          role="status"
          className="mt-4 rounded-lg border border-control/50 p-3 text-sm text-muted"
        >
          Este município oficial não tem linha analítica correspondente nesta
          publicação. A ausência não representa faturamento ou consumo zero.
        </p>
      ) : null}
      {comparison ? (
        <div className="mt-4 grid gap-3 sm:grid-cols-2">
          <Kpi
            label="Faturamento · R$"
            initial={comparison.initial.billed_amount}
            final={comparison.final.billed_amount}
            change={comparison.billed_amount_change_brl}
            initialCaption={initialCaption}
            finalCaption={finalCaption}
            format={moneyValue}
            formatChange={signedMoney}
          />
          <Kpi
            label="Consumo medido · kWh"
            initial={comparison.initial.measured_energy_kwh}
            final={comparison.final.measured_energy_kwh}
            change={comparison.measured_energy_change_kwh}
            initialCaption={initialCaption}
            finalCaption={finalCaption}
            format={energyValue}
            formatChange={signedEnergy}
          />
        </div>
      ) : null}
      {detail &&
      detail.data.coverage.measured_energy_kwh.status === "partial" ? (
        <p className="mt-3 rounded-lg bg-[var(--status-warning-bg)] p-3 text-xs text-content">
          A cobertura do consumo medido é parcial no período. Os valores
          observados permanecem visíveis e não são tratados como zero.
        </p>
      ) : null}
      {detail ? (
        <div className="mt-5">
          <PanelTabs
            prefix={prefix}
            label={`Detalhes de ${municipality.name}`}
            active={tab}
            onChange={setTab}
            tabs={[
              { id: "neighborhoods", label: "Bairros" },
              { id: "series", label: "Série mensal" },
            ]}
          />
          <div
            role="tabpanel"
            id={tabPanelId(prefix, tab)}
            aria-labelledby={tabId(prefix, tab)}
          >
            {tab === "neighborhoods" ? (
              <Neighborhoods
                key={municipality.code}
                envelope={detail}
                municipalityName={municipality.name}
              />
            ) : (
              <MonthlySeries key={municipality.code} envelope={detail} />
            )}
          </div>
          <Caveats envelope={detail} municipalityName={municipality.name} />
        </div>
      ) : null}
      {detailError ? (
        <div
          role="alert"
          className="mt-3 flex flex-wrap items-center justify-between gap-2 text-xs text-danger"
        >
          <span>Não foi possível carregar a série e os bairros.</span>
          <Button variant="outline" size="sm" onClick={onRetryDetail}>
            Tentar novamente
          </Button>
        </div>
      ) : null}
      {layer.endsWith("change") ? (
        <p className="sr-only">
          A camada selecionada mostra a variação absoluta entre as duas
          competências.
        </p>
      ) : null}
    </section>
  );
}
