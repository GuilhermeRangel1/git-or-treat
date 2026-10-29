import { useRef, useState } from "react";
import Button from "../../shared/ui/Button";
import MetricCard from "../../shared/ui/MetricCard";
import Modal from "../../shared/ui/Modal";
import type { PanoramaData } from "../../shared/analytics/types";
import { formatCompetenciaLabel } from "../../shared/analytics/syntheticData";

const metricsOrder = [
  "receitaFaturada",
  "receitaPaga",
  "energiaConsumida",
  "energiaFaturada",
  "precoMedioEfetivo",
  "ucsAtivas",
  "continuidadeDec",
  "continuidadeFec",
] as const;

export default function PanoramaFoundations({
  data,
  comparisonLabel,
  comparisonUnavailable,
}: {
  data: PanoramaData;
  comparisonLabel: string;
  comparisonUnavailable?: string;
}) {
  const [open, setOpen] = useState(false);
  const triggerRef = useRef<HTMLButtonElement>(null);
  return (
    <>
      <Button
        ref={triggerRef}
        variant="ghost"
        size="md"
        className="px-1 underline underline-offset-4"
        onClick={() => setOpen(true)}
      >
        Ver fundamentos
      </Button>
      <Modal
        open={open}
        onClose={() => setOpen(false)}
        triggerRef={triggerRef}
        title="Fundamentos dos indicadores"
        description="Definições, fórmulas, unidades e proveniência do recorte atual."
        closeLabel="Fechar fundamentos"
        size="lg"
        header="sticky"
      >
        <div className="grid gap-4 p-5 sm:grid-cols-2 sm:p-6">
          {metricsOrder.map((key) => (
            <MetricCard
              key={key}
              compact
              metric={data.metricas[key]}
              comparacaoLabel={comparisonLabel}
              loteVersao={data.loteVersao}
              comparisonUnavailable={comparisonUnavailable}
            />
          ))}
          <section className="rounded-xl border border-border bg-canvas p-4 text-sm sm:col-span-2">
            <h3 className="font-semibold">Metadados do conjunto</h3>
            <dl className="mt-3 grid gap-2 text-muted sm:grid-cols-2">
              <div>
                <dt className="inline">Fonte: </dt>
                <dd className="inline">Sintética</dd>
              </div>
              <div>
                <dt className="inline">Lote: </dt>
                <dd className="inline break-all">{data.loteVersao}</dd>
              </div>
              <div>
                <dt className="inline">Atualizado em: </dt>
                <dd className="inline">{data.dataAtualizacao}</dd>
              </div>
              <div>
                <dt className="inline">Competência: </dt>
                <dd className="inline">
                  {formatCompetenciaLabel(data.filtros.periodo)}
                </dd>
              </div>
              <div>
                <dt className="inline">Município: </dt>
                <dd className="inline">{data.filtros.municipio}</dd>
              </div>
              <div>
                <dt className="inline">Classe: </dt>
                <dd className="inline">{data.filtros.classe}</dd>
              </div>
            </dl>
            <p className="mt-3 text-xs text-muted">
              Esta demonstração usa dados sintéticos e não foi reconciliada com
              Gold.
            </p>
          </section>
        </div>
      </Modal>
    </>
  );
}
