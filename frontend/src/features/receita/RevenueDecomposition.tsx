import type { RevenueEnvelope } from "./contract";
import { signedValueTone } from "@/shared/ui/signedValue";

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
  const window = envelope.data.window_decomposition;
  if (window) {
    const labels = [
      ["Volume da base comum", "volume"],
      ["Preço observado da base comum", "preco"],
      ["Interação preço × volume", "interacao"],
      ["Entradas no recorte", "entradas"],
      ["Saídas do recorte", "saidas"],
      ["Sem leitura, fora da base", "sem_leitura"],
      ["Outras parcelas fora da base", "outros"],
    ];
    return (
      <section
        aria-labelledby="revenue-window-title"
        className="min-w-0 rounded-xl bg-surface p-5 sm:p-6"
      >
        <h2
          id="revenue-window-title"
          className="font-heading text-xl font-semibold text-content"
        >
          Preço × volume por janela
        </h2>
        {window.windows.length === 4 ? (
          <p className="mt-3 text-sm text-muted">
            {window.windows[0]} a {window.windows[1]} → {window.windows[2]} a{" "}
            {window.windows[3]}
          </p>
        ) : null}
        <p className="mt-2 text-sm text-muted">
          Esta análise usa períodos definidos para a comparação, independentes
          dos meses selecionados na série.
        </p>
        {window.status === "partial" ? (
          <p role="status" className="mt-3 text-sm text-muted">
            Resultado parcial: {window.incomplete_groups} de{" "}
            {window.group_count} recortes sem base ou valores completos. As
            parcelas mostram somente valores conhecidos.
          </p>
        ) : null}
        {window.status === "unavailable" ? (
          <p role="status" className="mt-3 text-sm text-muted">
            Decomposição indisponível para este recorte.
          </p>
        ) : (
          <dl className="mt-4 grid gap-3">
            {labels.map(([label, key]) => (
              <div key={key} className="flex flex-wrap justify-between gap-2">
                <dt>{label}</dt>
                <dd
                  className={`font-semibold [overflow-wrap:anywhere] ${signedValueTone(window.components[key] ?? null)}`}
                >
                  {signedAmount(window.components[key] ?? null)}
                </dd>
              </div>
            ))}
            <div className="flex flex-wrap justify-between gap-2 border-t border-border pt-3">
              <dt>Variação total nas janelas</dt>
              <dd
                className={`font-semibold [overflow-wrap:anywhere] ${signedValueTone(window.total_change_brl)}`}
              >
                {signedAmount(window.total_change_brl)}
              </dd>
            </div>
          </dl>
        )}
        {window.limitations.map((note) => (
          <p key={note} className="mt-3 text-xs leading-relaxed text-muted">
            {note}
          </p>
        ))}
      </section>
    );
  }
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
            Ilustração da variação entre extremos; depende de uma série de dados
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
                signedValueTone(value)
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
        Preço observado usa uma base comparável e não é tarifa homologada.
        Receita faturada e paga são grandezas distintas.
      </p>
    </section>
  );
}
