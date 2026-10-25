import { useState } from "react";
import { HelpCircle, Minus, TrendingDown, TrendingUp } from "lucide-react";
import type { KpiMetric } from "../analytics/types";
import Badge from "./Badge";

interface MetricCardProps {
  metric: KpiMetric;
  comparacaoLabel?: string;
  loteVersao?: string;
  comparisonUnavailable?: string;
  compact?: boolean;
}

export default function MetricCard({
  metric,
  comparacaoLabel = "vs. período anterior",
  loteVersao = "panorama-sintetico-2024.04-v1",
  comparisonUnavailable,
  compact = false,
}: MetricCardProps) {
  const [showDetails, setShowDetails] = useState(false);

  // Formatação de valor principal
  const formatValue = (val: number, unidade: string) => {
    if (unidade === "R$") {
      return new Intl.NumberFormat("pt-BR", {
        style: "currency",
        currency: "BRL",
        maximumFractionDigits: 2,
      }).format(val);
    }
    if (unidade === "R$/kWh") {
      return `R$ ${val.toFixed(2).replace(".", ",")} / kWh`;
    }
    if (unidade === "kWh") {
      if (Math.abs(val) >= 1000000) {
        return `${(val / 1000000).toLocaleString("pt-BR", { maximumFractionDigits: 2 })} GWh`;
      }
      return `${val.toLocaleString("pt-BR", { maximumFractionDigits: 0 })} kWh`;
    }
    if (unidade === "UCs") {
      return `${val.toLocaleString("pt-BR")} UCs`;
    }
    if (unidade.includes("horas") || unidade.includes("interrupções")) {
      return `${val.toFixed(2).replace(".", ",")} ${unidade}`;
    }
    return `${val.toLocaleString("pt-BR")} ${unidade}`;
  };

  // Formatação de valor de variação absoluta
  const formatDiff = (diff: number, unidade: string) => {
    const sinal = diff > 0 ? "+" : "";
    if (unidade === "R$") {
      return `${sinal}${new Intl.NumberFormat("pt-BR", {
        style: "currency",
        currency: "BRL",
      }).format(diff)}`;
    }
    if (unidade === "R$/kWh") {
      return `${sinal}R$ ${diff.toFixed(2).replace(".", ",")}/kWh`;
    }
    if (unidade === "kWh") {
      return `${sinal}${diff.toLocaleString("pt-BR")} kWh`;
    }
    return `${sinal}${diff.toLocaleString("pt-BR")} ${unidade}`;
  };

  // Distinção de grandezas em tags
  const tipoGrandezaBadges: Record<
    KpiMetric["tipoGrandeza"],
    { label: string; variant: "neutral" | "goiaba" | "pistache" | "info" }
  > = {
    faturado: { label: "Faturado", variant: "goiaba" },
    pago: { label: "Arrecadado / Pago", variant: "pistache" },
    consumido: { label: "Físico / Consumido", variant: "info" },
    operacao: { label: "Rede / Operação", variant: "neutral" },
  };

  const badgeInfo = tipoGrandezaBadges[metric.tipoGrandeza] || {
    label: metric.tipoGrandeza,
    variant: "neutral",
  };

  // Avaliação semântica da variação (verde vs vermelho)
  const isPositiveChange = (metric.variacaoPercentual ?? 0) > 0;
  const isNegativeChange = (metric.variacaoPercentual ?? 0) < 0;
  const isNeutral = metric.variacaoPercentual === 0;

  let trendColor = "text-muted bg-[var(--bg-surface-hover)]";
  if (metric.bomSentido === "positivo") {
    if (isPositiveChange) {
      trendColor = "text-[var(--status-success)] bg-[var(--status-success)]/10";
    } else if (isNegativeChange) {
      trendColor =
        "text-[var(--accent-goiaba)] bg-[var(--accent-goiaba-subtle)]";
    }
  } else if (metric.bomSentido === "negativo") {
    // Para DEC/FEC, diminuir é bom!
    if (isNegativeChange) {
      trendColor = "text-[var(--status-success)] bg-[var(--status-success)]/10";
    } else if (isPositiveChange) {
      trendColor =
        "text-[var(--accent-goiaba)] bg-[var(--accent-goiaba-subtle)]";
    }
  }

  return (
    <article
      aria-label={`${metric.nome}: ${formatValue(metric.valorAtual, metric.unidade)}`}
      className={`min-w-0 flex flex-col justify-between rounded-xl border border-border bg-surface shadow-sm ${compact ? "p-3" : "p-4"}`}
    >
      {/* Cabeçalho do Card */}
      <div>
        <div className="flex items-center justify-between gap-2 mb-2">
          <Badge variant={badgeInfo.variant}>{badgeInfo.label}</Badge>
          <button
            type="button"
            onClick={() => setShowDetails((prev) => !prev)}
            aria-expanded={showDetails}
            aria-label={`Ver detalhes e fórmula de ${metric.nome}`}
            className="text-muted hover:text-content p-1 rounded transition-colors focus-visible:outline-2 focus-visible:outline-brand cursor-pointer"
          >
            <HelpCircle className="size-4" />
          </button>
        </div>

        <h3 className="font-heading text-sm font-semibold text-content leading-tight">
          {metric.nome}
        </h3>
        {metric.subtitulo && (
          <p className="text-xs text-muted mt-0.5">{metric.subtitulo}</p>
        )}
      </div>

      {/* Valor Principal */}
      <div className={compact ? "my-2" : "my-3"}>
        <div
          className={`break-words font-heading font-bold tracking-tight text-content ${compact ? "text-xl" : "text-2xl 2xl:text-3xl"}`}
        >
          {formatValue(metric.valorAtual, metric.unidade)}
        </div>
      </div>

      {/* Variação e Comparação */}
      <div className="pt-3 border-t border-[var(--line-subtle)] text-xs">
        {comparisonUnavailable ? (
          <span className="text-muted">{comparisonUnavailable}</span>
        ) : metric.valorAnterior != null ? (
          metric.baseZero ? (
            <div className="flex items-center gap-2">
              <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded font-mono font-medium text-xs bg-[var(--bg-surface-hover)] text-muted">
                N/D
              </span>
              <span className="text-muted">Base anterior zero</span>
            </div>
          ) : metric.variacaoPercentual == null ? (
            <span className="text-muted">Comparação indisponível</span>
          ) : (
            <div className="flex flex-wrap items-center gap-2">
              <span
                className={`inline-flex items-center gap-1 px-2 py-0.5 rounded font-mono font-semibold ${trendColor}`}
              >
                {isPositiveChange && <TrendingUp className="size-3.5" />}
                {isNegativeChange && <TrendingDown className="size-3.5" />}
                {isNeutral && <Minus className="size-3.5" />}
                <span>
                  {metric.variacaoPercentual != null
                    ? `${metric.variacaoPercentual > 0 ? "+" : ""}${metric.variacaoPercentual.toFixed(2).replace(".", ",")}%`
                    : "N/D"}
                </span>
              </span>

              {metric.variacaoAbsoluta != null && (
                <span className="text-muted font-mono">
                  ({formatDiff(metric.variacaoAbsoluta, metric.unidade)})
                </span>
              )}

              <span className="w-full text-muted mt-1 break-words">
                {comparacaoLabel}:{" "}
                <strong className="text-content font-medium">
                  {formatValue(metric.valorAnterior, metric.unidade)}
                </strong>
              </span>
            </div>
          )
        ) : (
          <span className="text-muted font-mono">
            {comparacaoLabel === "Sem comparação"
              ? "Sem comparação selecionada"
              : "Sem dados no período de comparação"}
          </span>
        )}
      </div>

      {/* Detalhes Expansíveis (Definição, Fórmula e Lote) */}
      {showDetails && (
        <div
          role="region"
          aria-label={`Definição e rastreabilidade de ${metric.nome}`}
          className="mt-4 pt-3 border-t border-border/80 text-xs text-muted space-y-2 bg-[var(--bg-surface-hover)] p-3 rounded-lg"
        >
          <div>
            <strong className="text-content block font-medium">
              Definição:
            </strong>
            <span>{metric.definicao}</span>
          </div>
          <div>
            <strong className="text-content block font-medium">
              Fórmula matemática:
            </strong>
            <code className="break-words font-mono text-content bg-surface px-1.5 py-0.5 rounded border border-border">
              {metric.formula}
            </code>
          </div>
          <div className="flex flex-wrap items-center justify-between gap-2 text-[11px] pt-1 border-t border-[var(--line-subtle)] font-mono">
            <span>Unidade: {metric.unidade}</span>
            <span>{loteVersao}</span>
          </div>
        </div>
      )}
    </article>
  );
}
