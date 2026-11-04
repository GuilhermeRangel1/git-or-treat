import { useRef, useState } from "react";
import { Clock3, RefreshCw } from "lucide-react";
import Button from "../../shared/ui/Button";
import Modal from "../../shared/ui/Modal";
import type { PanoramaData } from "../../shared/analytics/types";
import { formatPanoramaTimestamp } from "./panorama-format";

export default function PanoramaStatus({
  data,
  isFetching,
  onRefresh,
}: {
  data: PanoramaData;
  isFetching: boolean;
  onRefresh: () => void;
}) {
  const [open, setOpen] = useState(false);
  const triggerRef = useRef<HTMLButtonElement>(null);
  return (
    <>
      <Button
        ref={triggerRef}
        variant="ghost"
        size="md"
        onClick={() => setOpen(true)}
        leftIcon={<Clock3 className="size-4" aria-hidden="true" />}
      >
        Ver estado de atualização
      </Button>
      <Modal
        open={open}
        onClose={() => setOpen(false)}
        triggerRef={triggerRef}
        title="Estado da atualização"
        description="Metadados retornados pela consulta dos indicadores."
        closeLabel="Fechar estado da atualização"
        size="md"
        header="inline"
      >
        <div className="space-y-4 text-sm">
          <dl className="grid gap-3 sm:grid-cols-2">
            <div>
              <dt className="text-xs text-muted">Fonte</dt>
              <dd className="mt-1 font-medium">
                {data.origem?.kind === "gold" ? "Gold" : "Dados sintéticos"}
              </dd>
            </div>
            <div>
              <dt className="text-xs text-muted">Atualizado em</dt>
              <dd className="mt-1 font-medium">
                {formatPanoramaTimestamp(data.dataAtualizacao)}
              </dd>
            </div>
            <div className="sm:col-span-2">
              <dt className="text-xs text-muted">Versão do lote</dt>
              <dd className="mt-1 break-all font-mono text-xs">
                {data.loteVersao}
              </dd>
            </div>
            {data.origem?.fingerprint && (
              <div className="sm:col-span-2">
                <dt className="text-xs text-muted">Fingerprint</dt>
                <dd className="mt-1 break-all font-mono text-xs">
                  {data.origem.fingerprint}
                </dd>
              </div>
            )}
            {data.origem?.temporalScope && (
              <div>
                <dt className="text-xs text-muted">Escopo temporal</dt>
                <dd className="mt-1 font-medium">
                  {data.origem.temporalScope === "monthly"
                    ? "Mensal"
                    : "Snapshot"}
                </dd>
              </div>
            )}
          </dl>
          <p className="rounded-lg bg-canvas p-3 text-xs text-muted">
            {data.origem?.kind === "gold"
              ? "A atualização identifica a importação local da publicação; não representa processamento Gold nem fechamento mensal."
              : "Esta data e a versão identificam o último conjunto carregado para o recorte atual."}
          </p>
          <Button
            variant="secondary"
            isLoading={isFetching}
            loadingLabel="Atualizando…"
            onClick={onRefresh}
            leftIcon={
              !isFetching ? (
                <RefreshCw className="size-4" aria-hidden="true" />
              ) : undefined
            }
          >
            Atualizar indicadores
          </Button>
        </div>
      </Modal>
    </>
  );
}
