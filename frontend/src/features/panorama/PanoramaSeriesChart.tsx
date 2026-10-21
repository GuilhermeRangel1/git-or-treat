import { useId, useState } from "react";
import { BarChart3, Table as TableIcon } from "lucide-react";
import type { MonthlyDataPoint } from "../../shared/analytics/types";
import Button from "../../shared/ui/Button";

interface PanoramaSeriesChartProps {
  data: MonthlyDataPoint[];
}

export default function PanoramaSeriesChart({
  data,
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

  return (
    <section
      aria-labelledby={titleId}
      className="mt-8 rounded-xl border border-border bg-surface p-5 sm:p-6 shadow-sm"
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
        <div className="flex items-center gap-2">
          <div className="inline-flex rounded-lg border border-control p-0.5 bg-[var(--bg-surface-hover)]">
            <button
              type="button"
              onClick={() => setViewMode("financeiro")}
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
          Diferenças sinalizam inadimplência ou perdas técnicas/comerciais
        </span>
      </div>

      {/* Visualização em Gráfico de Barras SVG Responsivo */}
      {!showTable ? (
        <div className="mt-6 relative">
          <div
            className="flex items-end justify-between gap-2 sm:gap-4 h-64 pt-8 pb-6 border-b border-border overflow-x-auto"
            role="img"
            aria-label={`Gráfico de colunas históricas de ${isFinanceiro ? "receita" : "energia"}`}
          >
            {data.map((item, idx) => {
              const val1 = isFinanceiro
                ? item.receitaFaturada
                : item.energiaFaturadaKwh;
              const val2 = isFinanceiro
                ? item.receitaPaga
                : item.energiaConsumidaKwh;

              const height1Pct = Math.max((val1 / maxValue) * 100, 2);
              const height2Pct = Math.max((val2 / maxValue) * 100, 2);

              const isHovered = hoveredIndex === idx;

              return (
                <div
                  key={item.competencia}
                  onMouseEnter={() => setHoveredIndex(idx)}
                  onMouseLeave={() => setHoveredIndex(null)}
                  className="flex-1 min-w-[32px] sm:min-w-[44px] flex flex-col items-center justify-end h-full group relative cursor-pointer"
                >
                  {/* Tooltip flutuante no hover */}
                  {isHovered && (
                    <div className="absolute -top-16 z-20 whitespace-nowrap rounded-lg border border-border bg-[var(--bg-surface)] p-2 text-xs shadow-md font-mono text-content">
                      <div className="font-semibold text-brand">
                        {item.label}
                      </div>
                      <div>
                        {isFinanceiro ? "Fat: " : "Fat: "}
                        {isFinanceiro
                          ? formatCurrency(val1)
                          : formatEnergy(val1)}
                      </div>
                      <div>
                        {isFinanceiro ? "Pago: " : "Cons: "}
                        {isFinanceiro
                          ? formatCurrency(val2)
                          : formatEnergy(val2)}
                      </div>
                    </div>
                  )}

                  {/* Par de Barras */}
                  <div className="flex items-end gap-1 w-full justify-center h-full">
                    <div
                      style={{ height: `${height1Pct}%` }}
                      className="w-1/2 max-w-[16px] rounded-t-sm bg-[var(--accent-goiaba)] transition-all group-hover:brightness-110"
                    />
                    <div
                      style={{ height: `${height2Pct}%` }}
                      className="w-1/2 max-w-[16px] rounded-t-sm bg-[var(--accent-pistache)] transition-all group-hover:brightness-110"
                    />
                  </div>

                  {/* Rótulo da Competência */}
                  <span className="mt-2 text-[11px] font-mono text-muted group-hover:text-content">
                    {item.label}
                  </span>
                </div>
              );
            })}
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
                    <td className="py-2 px-3 font-semibold">{item.label}</td>
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
