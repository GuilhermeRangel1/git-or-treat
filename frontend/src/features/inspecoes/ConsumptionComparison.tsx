import type { DetailEnvelope } from "./contract";
import { energy } from "./format";

export default function ConsumptionComparison({
  evidence,
}: {
  evidence: DetailEnvelope["data"]["estimate_evidence"];
}) {
  const scale = Math.max(
    evidence.baseline_kwh ?? 0,
    evidence.observed_kwh ?? 0,
  );
  const readings = [
    {
      label: "Referência mensal hipotética",
      value: evidence.baseline_kwh,
      color: "bg-muted",
    },
    {
      label: "Consumo mensal observado (sintético)",
      value: evidence.observed_kwh,
      color: "bg-brand",
    },
  ];
  return (
    <section
      className="mt-5 rounded-lg bg-canvas p-4"
      aria-labelledby="comparison-title"
    >
      <h4 id="comparison-title" className="font-semibold">
        Comparativo de consumo
      </h4>
      <p className="mt-1 text-xs leading-5 text-muted">
        Dados sintéticos em kWh/mês, na mesma escala. A referência é um cenário
        hipotético, não uma média histórica.
      </p>
      <dl className="mt-4 space-y-4">
        {readings.map(({ label, value, color }) => (
          <div key={label}>
            <dt className="text-xs text-muted">{label}</dt>
            <dd className="mt-1">
              <span className="font-mono text-sm">
                {value === null ? "Dado indisponível" : `${energy(value)}/mês`}
              </span>
              {value !== null && (
                <div
                  aria-hidden="true"
                  className="mt-2 h-2 overflow-hidden rounded-full border border-border"
                >
                  <div
                    className={`h-full rounded-full ${color}`}
                    style={{
                      width: `${scale > 0 ? (value / scale) * 100 : 0}%`,
                    }}
                  />
                </div>
              )}
            </dd>
          </div>
        ))}
      </dl>
      <p className="mt-3 text-xs leading-5 text-muted">{evidence.reference}</p>
      {(evidence.baseline_kwh === null || evidence.observed_kwh === null) && (
        <p className="mt-2 text-sm">
          Comparação incompleta: ausência de dado não representa consumo zero.
        </p>
      )}
    </section>
  );
}
