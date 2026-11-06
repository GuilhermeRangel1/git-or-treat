import type { RevenueEnvelope, RevenueWindowItem } from "./contract";
import type { RevenueGroupBy } from "./revenue-filters";
import {
  effectLabels,
  money,
  signedMoney,
  percentage,
  windowLabel,
} from "./revenue-presentation";
import { signedValueTone } from "@/shared/ui/signedValue";
import Button from "@/shared/ui/Button";

export default function RevenueInvestigation({
  envelope,
  groupBy,
  onGroupByChange,
  onExplore,
  onViewDiagnosis,
  metric = "volume",
  onMetricChange,
}: {
  envelope: RevenueEnvelope;
  groupBy: RevenueGroupBy;
  onGroupByChange: (value: RevenueGroupBy) => void;
  onExplore: (item: RevenueWindowItem) => void;
  onViewDiagnosis: () => void;
  metric?: string;
  onMetricChange?: (value: string) => void;
}) {
  const items = envelope.data.window_breakdown ?? [];
  const value = (item: RevenueWindowItem) =>
    item.decomposition.status === "unavailable"
      ? null
      : metric === "receita"
        ? item.decomposition.total_change_brl
        : (item.decomposition.components[metric] ?? null);
  const sorted = [...items].sort(
    (a, b) =>
      (value(a) ?? Infinity) - (value(b) ?? Infinity) ||
      a.label.localeCompare(b.label),
  );
  const maximum = Math.max(
    1,
    ...items.map((item) => Math.abs(value(item) ?? 0)),
  );
  const knownValues = items
    .map(value)
    .filter((item): item is number => item !== null);
  const hasDecrease = knownValues.some((item) => item < 0);
  const allZero =
    knownValues.length > 0 && knownValues.every((item) => item === 0);
  const title =
    !items.length || !knownValues.length
      ? "Contribuição dos recortes"
      : hasDecrease
        ? "Onde está a queda?"
        : "Como os recortes contribuíram?";
  return (
    <section
      className="grid min-w-0 gap-5 rounded-xl bg-surface p-5 sm:p-6"
      aria-labelledby="investigation-title"
    >
      <div>
        <p className="text-xs font-medium uppercase tracking-wide text-brand">
          Localize a redução
        </p>
        <h2
          id="investigation-title"
          tabIndex={-1}
          className="mt-2 font-heading text-xl font-semibold text-content"
        >
          {title}
        </h2>
        <p className="mt-2 text-sm text-muted">
          {windowLabel(envelope.data.window_decomposition?.windows ?? [])}. Os
          valores seguem a decomposição publicada.
        </p>
      </div>
      <div className="flex flex-wrap gap-4">
        <label className="grid gap-1 text-sm text-muted">
          Investigar por
          <select
            className="min-h-11 rounded-lg border border-control bg-surface px-3 py-2 text-content focus-visible:outline-2 focus-visible:outline-brand"
            value={groupBy}
            onChange={(e) => onGroupByChange(e.target.value as RevenueGroupBy)}
          >
            <option value="municipio">Município</option>
            <option value="bairro">Bairro</option>
            <option value="classe">Classe</option>
          </select>
        </label>
        <label className="grid gap-1 text-sm text-muted">
          Comparar impacto na receita
          <select
            className="min-h-11 rounded-lg border border-control bg-surface px-3 py-2 text-content focus-visible:outline-2 focus-visible:outline-brand"
            value={metric}
            onChange={(e) => onMetricChange?.(e.target.value)}
          >
            <option value="volume">Efeito-volume (R$)</option>
            <option value="preco">Efeito-preço (R$)</option>
            <option value="receita">Variação da receita (R$)</option>
          </select>
        </label>
      </div>
      {!items.length ? (
        <p role="status" className="text-sm text-muted">
          Não há decomposição publicada por recorte para esta consulta.
        </p>
      ) : (
        <>
          {!hasDecrease ? (
            <p role="status" className="text-sm text-muted">
              {knownValues.length
                ? allZero
                  ? "Os recortes disponíveis não apresentam variação nesta métrica."
                  : "Nenhum recorte com valor disponível apresenta redução nesta métrica."
                : "Não há valores disponíveis para avaliar redução nesta métrica."}
            </p>
          ) : null}
          <p className="text-sm text-muted">
            Valores em reais, do menor para o maior. O efeito-volume mostra o
            impacto da quantidade de energia na receita.
          </p>
          <p className="text-xs text-muted">
            {items.length} recortes · até 10 menores contribuições no gráfico.
            Todos os recortes estão na tabela abaixo.
          </p>
          <ol className="grid gap-3">
            {sorted.slice(0, 10).map((item) => (
              <li key={item.key}>
                <button
                  type="button"
                  aria-label={
                    groupBy === "classe"
                      ? `Selecionar classe ${item.label}`
                      : `Explorar ${item.label}`
                  }
                  onClick={() => onExplore(item)}
                  className="grid w-full gap-2 rounded-lg border border-border p-3 text-left hover:bg-surface-hover focus-visible:outline-2 focus-visible:outline-brand"
                >
                  <span className="flex flex-wrap justify-between gap-2 text-sm">
                    <span className="font-medium text-content">
                      {item.label}
                      {groupBy !== "classe" ? (
                        <span aria-hidden="true"> →</span>
                      ) : null}
                    </span>
                    <span
                      className={`font-semibold ${signedValueTone(value(item))}`}
                    >
                      {signedMoney(value(item))}
                    </span>
                  </span>
                  <span
                    className="relative block h-3 overflow-hidden rounded bg-canvas"
                    aria-hidden="true"
                  >
                    <span className="absolute inset-y-0 left-1/2 border-l border-border" />
                    <span
                      className={`absolute inset-y-0 ${value(item) !== null && value(item)! < 0 ? "bg-danger" : "bg-success"}`}
                      style={{
                        width: `${(Math.abs(value(item) ?? 0) / maximum) * 50}%`,
                        left:
                          value(item) !== null && value(item)! < 0
                            ? `${50 - (Math.abs(value(item)!) / maximum) * 50}%`
                            : "50%",
                      }}
                    />
                  </span>
                  {item.decomposition.status === "partial" ? (
                    <span className="text-xs text-muted">
                      Parcelas conhecidas · base parcial
                    </span>
                  ) : null}
                </button>
              </li>
            ))}
          </ol>
          <details className="min-w-0 max-w-full rounded-lg border border-border p-3">
            <summary className="cursor-pointer text-sm font-medium text-brand">
              Ver tabela · todos os valores
            </summary>
            <div className="mt-3 w-full min-w-0 max-w-full overflow-x-auto">
              <table className="w-full min-w-[760px] table-fixed text-left text-sm">
                <caption className="sr-only">
                  Recortes das janelas publicadas em reais
                </caption>
                <thead>
                  <tr>
                    <th className="w-[24%] p-2 text-xs font-medium text-muted">
                      Recorte
                    </th>
                    <th className="w-[18%] p-2 text-right text-xs font-medium text-muted">
                      Variação da receita
                    </th>
                    <th className="w-[16%] p-2 text-right text-xs font-medium text-muted">
                      Efeito-preço
                    </th>
                    <th className="w-[16%] p-2 text-right text-xs font-medium text-muted">
                      Efeito-volume
                    </th>
                    <th className="w-[13%] p-2 text-xs font-medium text-muted">
                      Base
                    </th>
                    <th className="w-[13%] p-2 text-xs font-medium text-muted">
                      Detalhes
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {sorted.map((item) => (
                    <tr key={item.key} className="border-t border-border">
                      <th className="p-2">
                        <button
                          className="text-left text-brand underline"
                          aria-label={
                            groupBy === "classe"
                              ? `Selecionar classe ${item.label}`
                              : `Explorar ${item.label}`
                          }
                          onClick={() => onExplore(item)}
                        >
                          {groupBy === "classe" ? (
                            `Selecionar classe ${item.label}`
                          ) : (
                            <>
                              {item.label}
                              <span aria-hidden="true"> →</span>
                            </>
                          )}
                        </button>
                      </th>
                      <td
                        className={`p-2 text-right font-semibold ${signedValueTone(item.decomposition.change_percent ?? null)}`}
                      >
                        <span
                          aria-label={`Variação da receita: ${percentage(item.decomposition.change_percent)}`}
                        >
                          {percentage(item.decomposition.change_percent)}
                        </span>
                      </td>
                      <td className="p-2 text-right whitespace-nowrap">
                        {signedMoney(item.decomposition.components.preco)}
                      </td>
                      <td className="p-2 text-right whitespace-nowrap">
                        {signedMoney(item.decomposition.components.volume)}
                      </td>
                      <td className="p-2">
                        {item.decomposition.status === "available"
                          ? "Completa"
                          : "Insuficiente ou parcial"}
                      </td>
                      <td className="p-2">
                        <details>
                          <summary className="cursor-pointer whitespace-nowrap text-brand underline">
                            Ver valores
                          </summary>
                          <div className="min-w-64 pt-2">
                            <dl className="grid gap-1 text-xs">
                              <div className="flex justify-between gap-3">
                                <dt>Faturamento no período inicial</dt>
                                <dd>
                                  {money(item.decomposition.initial_amount_brl)}
                                </dd>
                              </div>
                              <div className="flex justify-between gap-3">
                                <dt>Faturamento no período final</dt>
                                <dd>
                                  {money(item.decomposition.final_amount_brl)}
                                </dd>
                              </div>
                              <div className="flex justify-between gap-3">
                                <dt>Variação da receita</dt>
                                <dd>
                                  {signedMoney(
                                    item.decomposition.total_change_brl,
                                  )}
                                </dd>
                              </div>
                            </dl>
                            <details className="mt-2">
                              <summary className="cursor-pointer text-brand">
                                Demais parcelas e fundamento
                              </summary>
                              <dl className="pt-1 text-xs">
                                {Object.entries(effectLabels).map(
                                  ([key, label]) => (
                                    <div
                                      key={key}
                                      className="flex justify-between gap-3 py-1"
                                    >
                                      <dt>{label}</dt>
                                      <dd>
                                        {signedMoney(
                                          item.decomposition.components[key],
                                        )}
                                      </dd>
                                    </div>
                                  ),
                                )}
                              </dl>
                              <p className="mt-2 text-xs">
                                Resíduo:{" "}
                                {money(item.decomposition.residual_brl)}
                              </p>
                              {item.decomposition.limitations.map((note) => (
                                <p
                                  key={note}
                                  className="mt-2 text-xs text-muted"
                                >
                                  {note}
                                </p>
                              ))}
                            </details>
                          </div>
                        </details>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </details>
        </>
      )}
      <div className="border-t border-border pt-4">
        <Button type="button" variant="outline" onClick={onViewDiagnosis}>
          Ver diagnóstico deste recorte
        </Button>
      </div>
    </section>
  );
}
