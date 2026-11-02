type Props = {
  source: {
    kind: string;
    version: string;
    is_demo: boolean;
    updated_at: string;
  };
  period: { start: string; end: string };
  units: readonly string[];
  limitations: readonly string[];
  periodLabel?: string;
  periodNote?: string;
};

function month(value: string) {
  const [year, number] = value.split("-");
  return `${number}/${year}`;
}

export default function DataProvenance({
  source,
  period,
  units,
  limitations,
  periodLabel = "Período consultado",
  periodNote,
}: Props) {
  const notes = [...new Set(limitations)];
  return (
    <section
      aria-label="Período, unidades e fonte dos dados"
      className="grid min-w-0 gap-3 rounded-xl border border-border bg-surface p-4 text-sm"
    >
      <h2 className="font-heading text-base font-semibold">
        Dados desta consulta
      </h2>
      <dl className="grid min-w-0 gap-3 sm:grid-cols-2">
        <div className="min-w-0">
          <dt className="text-xs text-muted">{periodLabel}</dt>
          <dd className="mt-1">
            {month(period.start)} a {month(period.end)}
          </dd>
        </div>
        <div className="min-w-0">
          <dt className="text-xs text-muted">Unidades</dt>
          <dd className="mt-1 break-words">{units.join(" · ")}</dd>
        </div>
        <div className="min-w-0 sm:col-span-2">
          <dt className="text-xs text-muted">Identificação da publicação</dt>
          <dd className="mt-1 break-all">{source.version}</dd>
        </div>
        <div className="min-w-0 sm:col-span-2">
          <dt className="text-xs text-muted">
            {source.kind === "gold_csv"
              ? "Importação local"
              : "Atualização da fonte"}
          </dt>
          <dd className="mt-1">
            {new Date(source.updated_at).toLocaleString("pt-BR", {
              timeZone: "UTC",
            })}{" "}
            UTC
          </dd>
        </div>
      </dl>
      {source.kind === "gold_csv" && (
        <p className="text-muted">
          A data de importação indica quando os dados foram carregados neste
          ambiente; não indica necessariamente quando foram coletados.
        </p>
      )}
      {periodNote && <p className="break-words text-muted">{periodNote}</p>}
      <div className="min-w-0">
        <h3 className="font-medium">Limitações dos dados</h3>
        {notes.length ? (
          <ul className="mt-1 list-disc space-y-1 pl-5 text-muted">
            {notes.map((note) => (
              <li className="break-words" key={note}>
                {note}
              </li>
            ))}
          </ul>
        ) : (
          <p className="mt-1 text-muted">
            A fonte não informou limitações adicionais.
          </p>
        )}
      </div>
    </section>
  );
}
