import { formatUCCompetence } from "./uc360-format";

type Point = { competencia: string; measured_energy_kwh: number | null };
const decimal = new Intl.NumberFormat("pt-BR", { maximumFractionDigits: 2 });
const monthIndex = (month: string) =>
  Number(month.slice(0, 4)) * 12 + Number(month.slice(5, 7));

export default function UC360Series({
  data,
  previous,
  pending,
  error,
  onRetry,
}: {
  data?: { items: Point[] };
  previous?: {
    data?: { items: Point[] };
    pending: boolean;
    error: Error | null;
  };
  pending: boolean;
  error: Error | null;
  onRetry: () => void;
}) {
  const rows = [...(data?.items ?? [])].sort((a, b) =>
    a.competencia.localeCompare(b.competencia),
  );
  const previousValues = new Map(
    previous?.data?.items.map((item) => [
      item.competencia,
      item.measured_energy_kwh,
    ]),
  );
  const values = rows.flatMap((row) =>
    row.measured_energy_kwh === null ? [] : [row.measured_energy_kwh],
  );
  const min = Math.min(0, ...values),
    max = Math.max(0, ...values),
    span = max - min || 1;
  const first = rows.length ? monthIndex(rows[0].competencia) : 0;
  const last = rows.length ? monthIndex(rows[rows.length - 1].competencia) : 0;
  const width = Math.min(5000, Math.max(600, (last - first + 1) * 22));
  const points = rows.map((row) => ({
    ...row,
    x:
      50 +
      ((width - 75) * (monthIndex(row.competencia) - first)) /
        Math.max(1, last - first),
    y:
      row.measured_energy_kwh === null
        ? null
        : 20 + ((max - row.measured_energy_kwh) * 160) / span,
  }));
  const groups: (typeof points)[] = [];
  let group: typeof points = [];
  for (const point of points) {
    if (
      point.y === null ||
      (group.length &&
        monthIndex(point.competencia) !==
          monthIndex(group[group.length - 1].competencia) + 1)
    ) {
      if (group.length) groups.push(group);
      group = [];
    }
    if (point.y !== null) group.push(point);
  }
  if (group.length) groups.push(group);
  return (
    <section
      aria-label="Série mensal de consumo"
      className="min-w-0 rounded-xl bg-surface p-4 sm:p-5"
    >
      <h2 className="font-heading text-lg font-semibold">
        Série mensal de consumo medido
      </h2>
      <p className="mt-1 text-sm text-muted">
        kWh por competência; meses sem valor ou sem registro interrompem a
        linha. A ausência não significa zero.
      </p>
      {pending && (
        <p role="status" className="mt-3 text-sm text-muted">
          Carregando série…
        </p>
      )}
      {error && (
        <p role="alert" className="mt-3 text-sm text-muted">
          Não foi possível carregar a série de consumo.{" "}
          <button type="button" className="underline" onClick={onRetry}>
            Tentar novamente
          </button>
        </p>
      )}
      {!pending && !error && values.length === 0 && (
        <p className="mt-3 text-sm text-muted">
          Sem valores de consumo disponíveis para este período.
        </p>
      )}
      {!pending && !error && values.length > 0 && (
        <div className="mt-4 max-w-full overflow-x-auto">
          <svg
            role="img"
            aria-label="Gráfico de consumo medido em kWh; os valores detalhados estão no histórico de consumo."
            viewBox={`0 0 ${width} 220`}
            style={{ width: `${width}px`, maxWidth: "none" }}
            className="h-56"
          >
            <line
              x1="50"
              x2={width - 25}
              y1={20 + (max * 160) / span}
              y2={20 + (max * 160) / span}
              className="stroke-border"
            />
            <text
              x="45"
              y="24"
              textAnchor="end"
              className="fill-muted"
              fontSize="10"
            >
              {decimal.format(max)}
            </text>
            <text
              x="45"
              y="184"
              textAnchor="end"
              className="fill-muted"
              fontSize="10"
            >
              {decimal.format(min)}
            </text>
            {groups
              .filter((entry) => entry.length > 1)
              .map((entry) => (
                <polyline
                  key={entry[0].competencia}
                  points={entry
                    .map((point) => `${point.x},${point.y}`)
                    .join(" ")}
                  fill="none"
                  className="stroke-brand"
                  strokeWidth="2"
                />
              ))}
            {points
              .filter((point) => point.y !== null)
              .map((point) => (
                <circle
                  key={point.competencia}
                  cx={point.x}
                  cy={point.y!}
                  r="3"
                  className="fill-brand"
                >
                  <title>
                    {formatUCCompetence(point.competencia)}:{" "}
                    {decimal.format(point.measured_energy_kwh!)} kWh
                  </title>
                </circle>
              ))}
            <text x="50" y="210" className="fill-muted" fontSize="11">
              {formatUCCompetence(rows[0].competencia)}
            </text>
            <text
              x={width - 25}
              y="210"
              textAnchor="end"
              className="fill-muted"
              fontSize="11"
            >
              {formatUCCompetence(rows[rows.length - 1].competencia)}
            </text>
          </svg>
        </div>
      )}
      <div className="mt-5 border-t border-border pt-4">
        <h3 className="font-heading font-semibold">
          Comparação com o mesmo mês do ano anterior
        </h3>
        <p className="mt-1 text-sm text-muted">
          Consumo medido em kWh. Meses ausentes permanecem sem dado.
        </p>
        {previous?.pending ? (
          <p role="status" className="mt-3 text-sm text-muted">
            Carregando ano anterior…
          </p>
        ) : previous?.error ? (
          <p role="alert" className="mt-3 text-sm text-muted">
            Não foi possível carregar o ano anterior.{" "}
            <button type="button" className="underline" onClick={onRetry}>
              Tentar novamente
            </button>
          </p>
        ) : rows.length > 0 && previous?.data ? (
          <div className="mt-3 overflow-x-auto">
            <table className="w-full min-w-[360px] text-left text-sm">
              <thead className="text-xs text-muted">
                <tr>
                  <th className="pb-2">Competência</th>
                  <th className="pb-2">Consumo no mês</th>
                  <th className="pb-2">Mesmo mês do ano anterior</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((row) => {
                  const priorMonth = `${String(Number(row.competencia.slice(0, 4)) - 1).padStart(4, "0")}${row.competencia.slice(4)}`;
                  const prior = previousValues.get(priorMonth);
                  return (
                    <tr
                      key={row.competencia}
                      className="border-t border-border"
                    >
                      <th scope="row" className="py-2 font-medium">
                        {formatUCCompetence(row.competencia)}
                      </th>
                      <td className="py-2">
                        {row.measured_energy_kwh == null
                          ? "Sem dado"
                          : `${decimal.format(row.measured_energy_kwh)} kWh`}
                      </td>
                      <td className="py-2">
                        {prior == null
                          ? "Sem dado"
                          : `${decimal.format(prior)} kWh`}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        ) : !pending && !error ? (
          <p className="mt-3 text-sm text-muted">
            Sem competências para comparar neste período.
          </p>
        ) : null}
      </div>
    </section>
  );
}
