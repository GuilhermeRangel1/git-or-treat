import { Fragment, useId, type ReactNode } from "react";
import type {
  RevenueDiagnosis,
  RevenueWindow,
} from "@/shared/analytics/revenueContract";
import PanoramaDiagnosisBar from "./PanoramaDiagnosisBar";
import PanoramaDiagnosisColumns from "./PanoramaDiagnosisColumns";
import PanoramaDiagnosisInfo from "./PanoramaDiagnosisInfo";
import {
  compactMoney,
  groupLabel,
  money,
  percent,
  signedPercent,
} from "./revenue-diagnosis-format";

const COHORT_LABELS: Record<
  RevenueDiagnosis["gd"]["cohorts"][number]["group"],
  string
> = {
  connected_between: "Conexão de GD entre as janelas",
  connected_during: "Conexão de GD na janela final",
  no_record: "Sem registro de GD e com cadastro negativo",
  prior: "GD anterior à janela inicial",
  unknown: "Vigência de GD indeterminada",
};
const GD_NOTE =
  "Comparação das mesmas UCs com ao menos seis pares mensais válidos. A relação com a data de conexão é observada; a Gold não mede energia gerada ou compensada e não comprova relação de causa entre GD e a redução.";

/** Mostra o valor compacto; o exato é o que o leitor de tela lê. */
function Money({ value }: { value: number }) {
  return (
    <span>
      <span aria-hidden="true">{compactMoney(value)}</span>
      <span className="sr-only">{money(value)}</span>
    </span>
  );
}

function headlineVerb(value: number) {
  return value > 0 ? "adicionou" : value < 0 ? "retirou" : "ficou em";
}

function DiagnosisPanel({
  title,
  children,
}: {
  title?: ReactNode;
  children: ReactNode;
}) {
  const titleId = useId();
  return (
    <section
      aria-labelledby={title ? titleId : undefined}
      className="flex min-w-0 flex-col rounded-lg border border-border bg-canvas/50 p-3"
    >
      {title ? (
        <h3
          id={titleId}
          className="mb-1 font-heading text-sm font-semibold leading-5 text-content"
        >
          {title}
        </h3>
      ) : null}
      {children}
    </section>
  );
}

export function PriceVolumePanel({
  window,
  offset,
}: {
  window: RevenueWindow;
  offset: number | null;
}) {
  const price = window.components.preco ?? null;
  const volume = window.components.volume ?? null;
  const headline = [
    { name: "Preço observado", value: price },
    { name: "Volume", value: volume },
  ].filter(
    (part): part is { name: string; value: number } => part.value !== null,
  );
  const balance = window.total_change_brl;
  const columns = [
    ...headline.map((part) => ({ label: part.name, value: part.value })),
    ...(balance !== null
      ? [{ label: "Saldo", value: balance, emphasis: true }]
      : []),
  ];
  const { initial_amount_brl: initial, final_amount_brl: final } = window;
  const hasBilling = initial != null && final != null;

  return (
    <DiagnosisPanel
      title={
        headline.length > 0
          ? headline.map((part, index) => (
              <Fragment key={part.name}>
                {index > 0 ? " · " : ""}
                {part.name} {headlineVerb(part.value)}{" "}
                <Money value={part.value} />
              </Fragment>
            ))
          : undefined
      }
    >
      {columns.length === 0 && offset === null ? (
        <p className="text-sm text-muted">
          Os efeitos de preço e volume não estão disponíveis neste recorte.
        </p>
      ) : (
        <div className="flex flex-1 flex-col justify-between gap-1.5">
          {hasBilling ? (
            <p className="text-xs font-medium leading-5 text-content/80">
              Faturamento: <Money value={initial} /> → <Money value={final} />
            </p>
          ) : null}
          {columns.length > 0 ? (
            <PanoramaDiagnosisColumns columns={columns} />
          ) : null}
          {offset !== null ? (
            <p className="text-xs text-content">
              O volume devolveu {percent(offset)} do ganho de preço
            </p>
          ) : null}
        </div>
      )}
    </DiagnosisPanel>
  );
}

function Highlight({ value, caption }: { value: number; caption: string }) {
  return (
    <div className="rounded-md bg-selected px-3 py-2">
      <p className="font-heading text-2xl font-semibold leading-7 text-content">
        {percent(value)}
      </p>
      <p className="text-xs leading-4 text-content">{caption}</p>
    </div>
  );
}

function GdCohort({
  row,
  scale,
}: {
  row: RevenueDiagnosis["gd"]["cohorts"][number];
  scale: number;
}) {
  const name = COHORT_LABELS[row.group];
  const change = row.measured_energy_change_percent;
  const count = `${row.uc_count.toLocaleString("pt-BR")} UCs`;
  return (
    <li className="grid grid-cols-[minmax(0,1fr)_auto] items-center gap-x-2 text-xs leading-4">
      <span className="font-medium text-content">{name}</span>
      <span className="text-right text-muted">{count}</span>
      {change === null ? (
        <span className="col-span-2 text-right font-medium text-content">
          Base insuficiente
        </span>
      ) : (
        <>
          <PanoramaDiagnosisBar
            value={change}
            max={scale}
            label={`${name}: variação do consumo medido de ${signedPercent(change)}, ${count}`}
          />
          <span className="text-right font-semibold text-content">
            {signedPercent(change)}
          </span>
        </>
      )}
    </li>
  );
}

function GdCohorts({ gd }: { gd: RevenueDiagnosis["gd"] }) {
  const scale = Math.max(
    ...gd.cohorts.map((row) =>
      Math.abs(row.measured_energy_change_percent ?? 0),
    ),
    0,
  );
  return (
    <div className="flex flex-1 flex-col">
      <div className="relative flex items-center gap-1">
        <h4 className="text-xs font-semibold text-content">
          Consumo por grupo de GD
        </h4>
        <PanoramaDiagnosisInfo label="Sobre a comparação por grupo de GD">
          {GD_NOTE}
        </PanoramaDiagnosisInfo>
      </div>
      <ul className="flex flex-1 flex-col justify-between gap-1.5">
        {gd.cohorts.map((row) => (
          <GdCohort key={row.group} row={row} scale={scale} />
        ))}
      </ul>
    </div>
  );
}

/** Some por inteiro quando o recorte não tem concentração nem grupos de GD. */
export function ConcentrationPanel({
  diagnosis,
}: {
  diagnosis: RevenueDiagnosis;
}) {
  const { concentration, gd } = diagnosis;
  const gdShare = gd.share_negative_volume_percent;
  const hasCohorts = gd.cohorts.length > 0;
  const hasHighlights = Boolean(concentration) || gdShare !== null;
  if (!hasHighlights && !hasCohorts) return null;
  return (
    <DiagnosisPanel
      title={hasHighlights ? "Onde a queda de volume se concentra" : undefined}
    >
      <div className="flex flex-1 flex-col gap-2">
        {hasHighlights ? (
          <div
            className={`grid gap-2 ${concentration && gdShare !== null ? "xl:grid-cols-2" : ""}`}
          >
            {concentration ? (
              <Highlight
                value={concentration.share_negative_volume_percent}
                caption={`da queda de volume está em ${concentration.labels.map(groupLabel).join(" e ")}`}
              />
            ) : null}
            {gdShare !== null ? (
              <Highlight
                value={gdShare}
                caption="da queda de volume está em UCs com conexão de GD"
              />
            ) : null}
          </div>
        ) : null}
        {hasCohorts ? <GdCohorts gd={gd} /> : null}
      </div>
    </DiagnosisPanel>
  );
}
