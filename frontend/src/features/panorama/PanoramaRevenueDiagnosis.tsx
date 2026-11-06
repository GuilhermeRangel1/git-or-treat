import { ArrowRight } from "lucide-react";
import Button from "@/shared/ui/Button";
import {
  ConcentrationPanel,
  PriceVolumePanel,
} from "./PanoramaDiagnosisFindings";
import {
  fullPeriodLabel,
  groupLabel,
  periodLabel,
} from "./revenue-diagnosis-format";
import { usePanoramaRevenueDiagnosis } from "./usePanoramaRevenueDiagnosis";

function PeriodTag({
  label,
  start,
  end,
}: {
  label: string;
  start: string;
  end: string;
}) {
  const full = fullPeriodLabel(start, end);
  return (
    <div
      role="group"
      aria-label={`${label}: ${full}`}
      title={full}
      className="flex items-baseline gap-1.5"
    >
      <span className="text-[11px] font-medium uppercase tracking-wide text-muted">
        {label}
      </span>
      <span className="font-heading text-sm font-semibold text-content">
        {periodLabel(start, end)}
      </span>
    </div>
  );
}

export default function PanoramaRevenueDiagnosis({
  municipio,
  classe,
  latestPeriod,
}: {
  municipio: string;
  classe: string;
  latestPeriod: string;
}) {
  const query = usePanoramaRevenueDiagnosis({
    municipio,
    classe,
    latestPeriod,
  });
  const window = query.data?.window;
  const diagnosis = query.data?.diagnosis;
  const known =
    window && window.status !== "unavailable" && window.status !== "empty";
  const filtered = municipio !== "todos" || classe !== "todas";
  const hasRightPanel =
    diagnosis &&
    (diagnosis.concentration ||
      diagnosis.gd.share_negative_volume_percent !== null ||
      diagnosis.gd.cohorts.length > 0);

  return (
    <section
      aria-labelledby="panorama-revenue-diagnosis-title"
      className="grid min-w-0 gap-3 rounded-xl border border-border bg-surface p-4"
    >
      <div>
        <div className="flex flex-wrap items-center justify-between gap-x-4 gap-y-1">
          <h2
            id="panorama-revenue-diagnosis-title"
            className="font-heading text-lg font-semibold text-content"
          >
            Diagnóstico comercial
          </h2>
          {known ? (
            <div className="flex flex-col items-start gap-0.5 sm:flex-row sm:items-center sm:gap-2">
              <PeriodTag
                label="ANTES"
                start={window.windows[0]}
                end={window.windows[1]}
              />
              <ArrowRight
                aria-hidden="true"
                className="size-3.5 rotate-90 text-muted sm:rotate-0"
              />
              <PeriodTag
                label="DEPOIS"
                start={window.windows[2]}
                end={window.windows[3]}
              />
            </div>
          ) : null}
        </div>
        {known ? (
          <p className="text-xs font-medium leading-5 text-content/80">
            <span>12 meses em cada período · não depende do filtro de mês</span>
            {filtered ? (
              <>
                {" · "}
                <span>
                  Recorte:{" "}
                  {municipio === "todos"
                    ? "Todos os municípios"
                    : groupLabel(municipio)}{" "}
                  ·{" "}
                  {classe === "todas" ? "Todas as classes" : groupLabel(classe)}
                </span>
              </>
            ) : null}
          </p>
        ) : null}
      </div>

      {query.data && known ? (
        <>
          <div
            className={`grid min-w-0 gap-3 ${hasRightPanel ? "md:grid-cols-2" : ""}`}
          >
            <PriceVolumePanel
              window={window}
              offset={diagnosis?.volume_offset_percent ?? null}
            />
            {diagnosis ? <ConcentrationPanel diagnosis={diagnosis} /> : null}
          </div>
          <p className="text-xs leading-4 text-muted">
            {window.status === "partial" ? (
              <>
                <span className="font-semibold">
                  Base parcial: {window.incomplete_groups}{" "}
                  {window.incomplete_groups === 1
                    ? "grupo incompleto"
                    : "grupos incompletos"}
                </span>
                {" · "}
              </>
            ) : null}
            Preço observado não é tarifa · Não indica causa
          </p>
        </>
      ) : query.data ? (
        <p role="status" className="text-sm text-muted">
          Não há evidências suficientes para o diagnóstico deste recorte.
        </p>
      ) : query.isFetching ? (
        <p role="status" className="text-sm text-muted">
          Consultando o diagnóstico deste recorte…
        </p>
      ) : (
        <div role="alert" className="text-sm text-muted">
          <p>
            Não foi possível consultar o diagnóstico comercial. Os indicadores
            continuam disponíveis.
          </p>
          <Button
            className="mt-2"
            variant="control"
            size="sm"
            onClick={() => void query.refetch()}
          >
            Tentar novamente
          </Button>
        </div>
      )}
    </section>
  );
}
