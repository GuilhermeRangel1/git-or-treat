import { useId, useState } from "react";
import { BarChart3, Table as TableIcon } from "lucide-react";
import type { MonthlyDataPoint } from "../../shared/analytics/types";
import Button from "../../shared/ui/Button";

interface PanoramaSeriesChartProps {
  data: MonthlyDataPoint[];
  partialPeriod?: string;
}

export default function PanoramaSeriesChart({
  data,
  partialPeriod,
}: PanoramaSeriesChartProps) {
  const [viewMode, setViewMode] = useState<"financeiro" | "fisico">(
    "financeiro",
  );
  const [showTable, setShowTable] = useState(false);
  const [hoveredIndex, setHoveredIndex] = useState<number | null>(null);
  const titleId = useId();

  if (!data || data.length === 0) return null;

  // Determina valores máximos para dimensionamento das barras
  const maxFinanceiro = Math.max(
    ...data.flatMap((d) => [d.receitaFaturada, d.receitaPaga]),
    1,
  );
  const maxFisico = Math.max(
    ...data.flatMap((d) => [d.energiaConsumidaKwh, d.energiaFaturadaKwh]),
    1,
  );

  const isFinanceiro = viewMode === "financeiro";
  const maxValue = isFinanceiro ? maxFinanceiro : maxFisico;

  const formatCurrency = (val: number) =>
    new Intl.NumberFormat("pt-BR", {
      style: "currency",
      currency: "BRL",
      maximumFractionDigits: 0,
    }).format(val);

  const formatEnergy = (val: number) =>
    `${(val / 1000).toLocaleString("pt-BR", { maximumFractionDigits: 1 })} MWh`;

  const formatAxis = (value: number) =>
    (value / 1000).toLocaleString("pt-BR", { maximumFractionDigits: 1 });
  const chartWidth = Math.max(640, data.length * 112 + 80);
  const plotHeight = 200;
  const plotTop = 36;
  const step = (chartWidth - 80) / data.length;
  const active = hoveredIndex == null ? null : data[hoveredIndex];

  return (
    <section
      aria-labelledby={titleId}
      className="rounded-xl border border-border bg-surface p-5 sm:p-6 shadow-sm"
    >
      {/* Topo do Gráfico */}
      <div className="flex flex-wrap items-center justify-between gap-4 pb-4 border-b border-[var(--line-subtle)]">
        <div>
          <h2
            id={titleId}
            className="font-heading text-lg font-semibold text-content"
          >
            Evolução Histórica das Competências
          </h2>
          <p className="text-xs text-muted mt-0.5">
            {isFinanceiro
              ? "Comparativo mensal entre Receita Faturada e Receita Arrecadada / Paga"
              : "Comparativo mensal entre Energia Consumida e Energia Faturada"}
          </p>
        </div>

        {/* Controles de alternância */}
        <div className="flex flex-wrap items-center gap-2">
          <div className="inline-flex rounded-lg border border-control p-0.5 bg-[var(--bg-surface-hover)]">
            <button
              type="button"
              onClick={() => setViewMode("financeiro")}
              aria-pressed={isFinanceiro}
              className={`px-3 py-1.5 text-xs font-medium rounded-md transition-colors cursor-pointer ${
                isFinanceiro
                  ? "bg-surface text-content shadow-xs font-semibold"
                  : "text-muted hover:text-content"
              }`}
            >
              Financeiro (R$)
            </button>
            <button
              type="button"
              onClick={() => setViewMode("fisico")}
              aria-pressed={!isFinanceiro}
              className={`px-3 py-1.5 text-xs font-medium rounded-md transition-colors cursor-pointer ${
                !isFinanceiro
                  ? "bg-surface text-content shadow-xs font-semibold"
                  : "text-muted hover:text-content"
              }`}
            >
              Físico (Energia)
            </button>
          </div>

          <Button
            variant="outline"
            size="sm"
            onClick={() => setShowTable((prev) => !prev)}
            leftIcon={
              showTable ? (
                <BarChart3 className="size-3.5" />
              ) : (
                <TableIcon className="size-3.5" />
              )
            }
          >
            {showTable ? "Ver Gráfico" : "Ver Tabela"}
          </Button>
        </div>
      </div>

      {/* Legenda Explicativa */}
      <div className="mt-4 flex flex-wrap items-center gap-5 text-xs font-mono">
        <div className="flex items-center gap-2">
          <span className="size-3 rounded-sm bg-[var(--accent-goiaba)] shrink-0" />
          <span className="text-content font-medium">
            {isFinanceiro ? "Receita Faturada (R$)" : "Energia Faturada (kWh)"}
          </span>
        </div>
        <div className="flex items-center gap-2">
          <span className="size-3 rounded-sm bg-[var(--accent-pistache)] shrink-0" />
          <span className="text-content font-medium">
            {isFinanceiro
              ? "Receita Arrecadada / Paga (R$)"
              : "Energia Consumida (kWh)"}
          </span>
        </div>
        <span className="text-muted ml-auto hidden sm:inline">
          Diferenças exigem análise; não comprovam perdas ou inadimplência
        </span>
      </div>

      {partialPeriod && (
        <p className="mt-2 text-xs text-muted">
          * Competência parcial: valores ainda não consolidados.
        </p>
      )}

      {/* Visualização em Gráfico de Barras SVG Responsivo */}
      {!showTable ? (
        <div className="mt-4">
          <p className="text-xs text-muted">
            Escala vertical: {isFinanceiro ? "R$ mil" : "MWh"}. Valores nas
            barras na mesma unidade; passe o mouse ou use Tab para o valor
            completo.
          </p>
          <div
            role="status"
            aria-live="polite"
            className="my-2 min-h-16 rounded-lg bg-[var(--bg-surface-hover)] p-3 text-xs text-content"
          >
            {active ? (
              <>
                <strong>
                  {active.label}
                  {active.competencia === partialPeriod ? " · parcial" : ""}
                </strong>
                <div>
                  Faturado:{" "}
                  {isFinanceiro
                    ? formatCurrency(active.receitaFaturada)
                    : formatEnergy(active.energiaFaturadaKwh)}
                </div>
                <div>
                  {isFinanceiro ? "Pago: " : "Consumido: "}
                  {isFinanceiro
                    ? formatCurrency(active.receitaPaga)
                    : formatEnergy(active.energiaConsumidaKwh)}
                </div>
              </>
            ) : (
              "Selecione uma competência para consultar os valores completos."
            )}
          </div>
          <div
            className="overflow-x-auto"
            role="region"
            aria-label="Série histórica com rolagem horizontal"
            tabIndex={0}
          >
            <svg
              viewBox={`0 0 ${chartWidth} 280`}
              style={{ minWidth: chartWidth }}
              className="h-[280px] w-full"
              aria-label={`Gráfico de colunas históricas de ${isFinanceiro ? "receita" : "energia"}`}
            >
              {[0, 1, 2, 3, 4].map((tick) => {
                const y = plotTop + plotHeight - (tick * plotHeight) / 4;
                return (
                  <g key={tick}>
                    <line
                      x1={64}
                      x2={chartWidth - 8}
                      y1={y}
                      y2={y}
                      stroke="var(--line)"
                    />
                    <text
                      x={56}
                      y={y + 4}
                      textAnchor="end"
                      fill="var(--text-secondary)"
                      fontSize={11}
                    >
                      {formatAxis((maxValue * tick) / 4)}
                    </text>
                  </g>
                );
              })}
              {data.map((item, idx) => {
                const val1 = isFinanceiro
                  ? item.receitaFaturada
                  : item.energiaFaturadaKwh;
                const val2 = isFinanceiro
                  ? item.receitaPaga
                  : item.energiaConsumidaKwh;
                const x = 80 + idx * step;
                return (
                  <g
                    key={item.competencia}
                    tabIndex={0}
                    role="img"
                    aria-label={`${item.label}: faturado ${isFinanceiro ? formatCurrency(val1) : formatEnergy(val1)}, ${isFinanceiro ? "pago" : "consumido"} ${isFinanceiro ? formatCurrency(val2) : formatEnergy(val2)}`}
                    onMouseEnter={() => setHoveredIndex(idx)}
                    onMouseLeave={() => setHoveredIndex(null)}
                    onFocus={() => setHoveredIndex(idx)}
                    onBlur={() => setHoveredIndex(null)}
                    className="focus-visible:outline-2 focus-visible:outline-brand"
                  >
                    {[val1, val2].map((value, series) => {
                      const height = (value / maxValue) * plotHeight;
                      const barX = x + series * 40;
                      return (
                        <g key={series}>
                          <rect
                            x={barX}
                            y={plotTop + plotHeight - height}
                            width={30}
                            height={height}
                            rx={2}
                            fill={
                              series === 0
                                ? "var(--accent-goiaba)"
                                : "var(--accent-pistache)"
                            }
                          />
                          <text
                            x={barX + 15}
                            y={plotTop + plotHeight - height - 7}
                            textAnchor="middle"
                            fontSize={11}
                            fill="var(--text-primary)"
                          >
                            {formatAxis(value)}
                          </text>
                        </g>
                      );
                    })}
                    <text
                      x={x + 35}
                      y={260}
                      textAnchor="middle"
                      fontSize={11}
                      fill="var(--text-secondary)"
                    >
                      {item.label}
                      {item.competencia === partialPeriod ? "*" : ""}
                    </text>
                  </g>
                );
              })}
            </svg>
          </div>
        </div>
      ) : (
        /* Visualização em Tabela Acessível */
        <div className="mt-6 overflow-x-auto">
          <table className="w-full text-left text-xs font-mono">
            <thead className="bg-[var(--bg-surface-hover)] text-muted uppercase tracking-wider border-b border-border">
              <tr>
                <th className="py-2.5 px-3">Competência</th>
                <th className="py-2.5 px-3 text-right">
                  {isFinanceiro ? "Faturado (R$)" : "Energia Faturada (kWh)"}
                </th>
                <th className="py-2.5 px-3 text-right">
                  {isFinanceiro
                    ? "Arrecadado / Pago (R$)"
                    : "Energia Consumida (kWh)"}
                </th>
                <th className="py-2.5 px-3 text-right">Diferença</th>
                <th className="py-2.5 px-3 text-right">UCs Ativas</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[var(--line-subtle)] text-content">
              {data.map((item) => {
                const val1 = isFinanceiro
                  ? item.receitaFaturada
                  : item.energiaFaturadaKwh;
                const val2 = isFinanceiro
                  ? item.receitaPaga
                  : item.energiaConsumidaKwh;
                const diff = val1 - val2;

                return (
                  <tr
                    key={item.competencia}
                    className="hover:bg-[var(--bg-surface-hover)]"
                  >
                    <td className="py-2 px-3 font-semibold">
                      {item.label}
                      {item.competencia === partialPeriod ? " · parcial" : ""}
                    </td>
                    <td className="py-2 px-3 text-right">
                      {isFinanceiro
                        ? formatCurrency(val1)
                        : `${val1.toLocaleString("pt-BR")} kWh`}
                    </td>
                    <td className="py-2 px-3 text-right">
                      {isFinanceiro
                        ? formatCurrency(val2)
                        : `${val2.toLocaleString("pt-BR")} kWh`}
                    </td>
                    <td className="py-2 px-3 text-right font-medium text-brand">
                      {isFinanceiro
                        ? formatCurrency(diff)
                        : `${diff.toLocaleString("pt-BR")} kWh`}
                    </td>
                    <td className="py-2 px-3 text-right text-muted">
                      {item.ucsAtivas.toLocaleString("pt-BR")}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
