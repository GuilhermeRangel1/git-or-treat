import type { RevenueEnvelope } from "./contract";

const money = new Intl.NumberFormat("pt-BR", {
  style: "currency",
  currency: "BRL",
});

function signedAmount(value: number | null) {
  if (value === null) return "Indisponível";
  return (
    (value < 0 ? "−" : value > 0 ? "+" : "") + money.format(Math.abs(value))
  );
}

export default function RevenueDecomposition({
  envelope,
}: {
  envelope: RevenueEnvelope;
}) {
  const { price_volume: effects, comparison } = envelope.data;
  const entries = [
    ["Volume a preço inicial", effects.volume_effect_brl],
    ["Preço sobre volume inicial", effects.price_effect_brl],
    ["Interação preço × volume", effects.interaction_effect_brl],
    ["Variação total", comparison.billed_amount_change_brl],
    ...(effects.rounding_adjustment_brl !== null &&
    effects.rounding_adjustment_brl !== 0
      ? ([
          ["Ajuste de arredondamento", effects.rounding_adjustment_brl],
        ] as const)
      : []),
  ] as const;

  return (
    <section
      aria-labelledby="revenue-decomposition-title"
      className="min-h-[368px] min-w-0 rounded-xl bg-surface p-5 sm:p-6"
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2
            id="revenue-decomposition-title"
            className="font-heading text-xl font-semibold text-content"
          >
            {envelope.metadata.source.is_demo
              ? "Preço × volume: ilustração do método"
              : "Preço × volume"}
          </h2>
          <p className="mt-4 text-xs leading-[18px] text-muted">
            Ilustração da variação entre extremos; depende de uma série Gold
            comparável.
          </p>
        </div>
      </div>

      <dl className="mt-4 grid gap-4">
        {entries.map(([label, value]) => (
          <div
            key={label}
            className="flex min-h-10 items-start justify-between gap-4"
          >
            <dt className="text-sm text-content">{label}</dt>
            <dd
              className={
                "flex items-center gap-2 text-right text-base font-semibold " +
                (value === null
                  ? "text-muted"
                  : value < 0
                    ? "text-danger"
                    : value > 0
                      ? "text-success"
                      : "text-content")
              }
            >
              <span aria-hidden="true">
                {value === null ? "" : value > 0 ? "▲" : value < 0 ? "▼" : "▶"}
              </span>
              {signedAmount(value)}
            </dd>
          </div>
        ))}
      </dl>

      <p className="mt-4 text-xs leading-[18px] text-muted">
        Preço observado vem do faturamento ÷ energia faturada; não é reajuste
        homologado. Receita faturada e paga são grandezas distintas.
      </p>
    </section>
  );
}
