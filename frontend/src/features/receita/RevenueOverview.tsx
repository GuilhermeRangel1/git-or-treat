import { useRef, useState } from "react";
import Modal from "@/shared/ui/Modal";
import Button from "@/shared/ui/Button";
import RevenueFindings from "./RevenueFindings";
import { signedValueTone } from "@/shared/ui/signedValue";
import type { RevenueEnvelope } from "./contract";
import {
  effectLabels,
  money,
  signedMoney,
  percentage,
  windowLabel,
} from "./revenue-presentation";

export default function RevenueOverview({
  envelope,
  onInvestigate,
  diagnosisLoading = false,
  diagnosisError = false,
  onRetryDiagnosis,
}: {
  envelope: RevenueEnvelope;
  onInvestigate: () => void;
  diagnosisLoading?: boolean;
  diagnosisError?: boolean;
  onRetryDiagnosis?: () => void;
}) {
  const window = envelope.data.window_decomposition;
  const [details, setDetails] = useState(false);
  const trigger = useRef<HTMLButtonElement>(null);
  const known = window && window.status !== "unavailable";
  const delta = known ? window.total_change_brl : null;
  const components = Object.keys(effectLabels).map((key) => ({
    key,
    value: known ? (window.components[key] ?? null) : null,
  }));
  const complete =
    known &&
    window.status === "available" &&
    window.initial_amount_brl != null &&
    window.final_amount_brl != null &&
    components.every((item) => item.value !== null);
  const otherComponents = components.filter(
    (item) => !["preco", "volume"].includes(item.key),
  );
  const chartComponents = [
    ...components.filter((item) => ["preco", "volume"].includes(item.key)),
    {
      key: "demais",
      value: otherComponents.every((item) => item.value !== null)
        ? otherComponents.reduce((sum, item) => sum + item.value!, 0)
        : null,
    },
  ];
  let running = window?.initial_amount_brl ?? 0;
  const steps = chartComponents.map((item) => {
    const start = running;
    running += item.value ?? 0;
    return { ...item, start, end: running };
  });
  const all = [
    0,
    window?.initial_amount_brl ?? 0,
    window?.final_amount_brl ?? 0,
    ...steps.flatMap((item) => [item.start, item.end]),
  ];
  const min = Math.min(...all),
    max = Math.max(1, ...all),
    range = max - min;
  const bars = complete
    ? [
        {
          key: "P0",
          value: window.initial_amount_brl!,
          start: 0,
          end: window.initial_amount_brl!,
        },
        ...steps,
        {
          key: "P1",
          value: window.final_amount_brl!,
          start: 0,
          end: window.final_amount_brl!,
        },
      ]
    : steps;
  const scale = Math.max(
    1,
    ...chartComponents.map((item) => Math.abs(item.value ?? 0)),
  );
  return (
    <div className="grid gap-5">
      <section aria-label="Resumo da receita" className="grid gap-4">
        <div>
          <p className="text-xs font-medium uppercase tracking-wide text-brand">
            Entenda a variação
          </p>
          <h2
            id="revenue-overview-title"
            tabIndex={-1}
            className="mt-2 font-heading text-2xl font-semibold text-content focus-visible:outline-2 focus-visible:outline-brand"
          >
            {delta == null
              ? "Comparação da receita"
              : `A receita ${delta > 0 ? "aumentou" : delta < 0 ? "diminuiu" : "ficou estável"}${window?.change_percent != null ? ` ${percentage(Math.abs(window.change_percent)).replace("+", "")}` : ""}`}
          </h2>
          <p className="mt-2 text-sm text-muted">
            {delta != null
              ? `${signedMoney(delta)} de variação observada no recorte.`
              : "Não há base suficiente para calcular a variação."}
          </p>
        </div>
      </section>
      <section
        aria-labelledby="effects-title"
        className="rounded-xl bg-surface p-5 sm:p-6"
      >
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h2
              id="effects-title"
              className="font-heading text-xl font-semibold text-content"
            >
              Como preço e volume compõem a mudança
            </h2>
            <p className="mt-2 text-sm text-muted">
              Contribuições monetárias para a comparação das duas janelas.
            </p>
          </div>
          <Button
            ref={trigger}
            variant="control"
            size="sm"
            onClick={() => setDetails(true)}
          >
            Como calculamos e valores
          </Button>
        </div>
        {known ? (
          <>
            <p className="mt-4 text-xs text-muted">
              {complete
                ? "Ponte entre o faturamento inicial e final · R$"
                : "Parcelas conhecidas · a base parcial não representa fechamento integral"}
            </p>
            <div
              className="mt-5 grid gap-2"
              role="img"
              aria-label={
                complete
                  ? "Cascata da variação de receita"
                  : "Contribuições conhecidas da variação de receita"
              }
            >
              {bars.map((item) => (
                <div
                  key={item.key}
                  className="grid grid-cols-[minmax(0,1fr)_minmax(3rem,2fr)] items-center gap-3 sm:grid-cols-[12rem_minmax(0,1fr)_10rem]"
                >
                  <span className="text-xs text-content">
                    {item.key === "demais"
                      ? "Demais componentes"
                      : (effectLabels[item.key] ??
                        (item.key === "P0"
                          ? "Período inicial"
                          : "Período final"))}
                  </span>
                  <span
                    className="relative block h-7 rounded bg-canvas"
                    aria-hidden="true"
                  >
                    <span
                      className={`absolute inset-y-1 rounded-sm ${item.key === "P0" || item.key === "P1" ? "bg-brand" : (item.value ?? 0) < 0 ? "bg-danger" : "bg-success"}`}
                      style={
                        complete
                          ? {
                              left: `${((Math.min(item.start, item.end) - min) / range) * 100}%`,
                              width: `${(Math.abs(item.end - item.start) / range) * 100}%`,
                            }
                          : {
                              left:
                                (item.value ?? 0) < 0
                                  ? `${50 - (Math.abs(item.value ?? 0) / scale) * 50}%`
                                  : "50%",
                              width: `${(Math.abs(item.value ?? 0) / scale) * 50}%`,
                            }
                      }
                    />
                  </span>
                  <span
                    className={`col-span-2 text-right text-xs font-medium sm:col-span-1 ${item.key === "P0" || item.key === "P1" ? "text-content" : signedValueTone(item.value)}`}
                  >
                    {item.key === "P0" || item.key === "P1"
                      ? money(item.value)
                      : signedMoney(item.value)}
                  </span>
                </div>
              ))}
            </div>
          </>
        ) : (
          <p role="status" className="mt-5 text-sm text-muted">
            Decomposição indisponível para este recorte.
            {window?.limitations.map((note) => (
              <span key={note} className="mt-2 block">
                {note}
              </span>
            ))}
          </p>
        )}
        <p className="mt-5 text-xs leading-relaxed text-muted">
          Preço observado sobre consumo medido na base comparável. Não
          representa tarifa homologada nem energia faturada.{" "}
          {window?.status === "partial"
            ? `${window.incomplete_groups} grupos com base incompleta; não há fechamento integral.`
            : ""}
        </p>
      </section>
      <RevenueFindings
        error={diagnosisError}
        onRetry={onRetryDiagnosis}
        loading={diagnosisLoading}
        diagnosis={envelope.data.diagnosis}
        partial={window?.status === "partial"}
        onInvestigate={onInvestigate}
      />
      <Modal
        open={details}
        onClose={() => setDetails(false)}
        triggerRef={trigger}
        title="Método e valores da comparação"
        closeLabel="Fechar fundamentos"
        size="lg"
        header="inline"
      >
        <div className="grid gap-4 text-sm text-content">
          <p>
            {windowLabel(window?.windows ?? [])}. O método soma efeitos dos
            pares UC/mês da base comum, sem recalcular por preços médios dos
            territórios.
          </p>
          <p>
            Faturamento inicial: {money(window?.initial_amount_brl)} ·
            Faturamento final: {money(window?.final_amount_brl)}.
          </p>
          <p>
            ΔR = preço + volume + interação + entradas + saídas + faturas sem
            leitura + outras parcelas. Contribuições em pontos percentuais
            dividem cada parcela pelo faturamento do período inicial. Não são o
            percentual de variação física de energia.
          </p>
          <dl>
            {components.map((item) => (
              <div
                key={item.key}
                className="flex justify-between gap-4 border-b border-border py-2"
              >
                <dt>{effectLabels[item.key]}</dt>
                <dd className="text-right">{signedMoney(item.value)}</dd>
              </div>
            ))}
          </dl>
          <p>
            Variação: {signedMoney(delta)} · Resíduo:{" "}
            {money(window?.residual_brl)}
          </p>
          {window?.limitations.map((note) => (
            <p key={note} className="text-xs text-muted">
              {note}
            </p>
          ))}
          <p className="text-xs text-muted">
            Atualização:{" "}
            {new Date(envelope.metadata.source.updated_at).toLocaleDateString(
              "pt-BR",
            )}{" "}
            · {envelope.metadata.source.is_demo ? "Demonstração" : "Gold"}
          </p>
        </div>
      </Modal>
    </div>
  );
}
