import type { RevenueDiagnosis } from "./contract";
import Button from "@/shared/ui/Button";
import { percentage } from "./revenue-presentation";

const cohortLabels: Record<string, string> = {
  connected_between: "Conexão de GD entre as janelas",
  connected_during: "Conexão de GD na janela final",
  no_record: "Sem registro de GD e com cadastro negativo",
  prior: "GD anterior à janela inicial",
  unknown: "Vigência de GD indeterminada",
};
const pct = (value: number) =>
  `${value.toLocaleString("pt-BR", { maximumFractionDigits: 1 })}%`;

export default function RevenueFindings({
  diagnosis,
  partial,
  onInvestigate,
  loading = false,
  error = false,
  onRetry,
}: {
  diagnosis: RevenueDiagnosis | null | undefined;
  partial: boolean;
  onInvestigate: () => void;
  loading?: boolean;
  error?: boolean;
  onRetry?: () => void;
}) {
  return (
    <section
      aria-labelledby="revenue-findings-title"
      className="grid gap-5 rounded-xl bg-surface p-5 sm:p-6"
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-xs font-medium uppercase tracking-wide text-brand">
            Evidências do recorte
          </p>
          <h2
            id="revenue-findings-title"
            className="mt-2 font-heading text-xl font-semibold text-content"
          >
            O que ajuda a explicar a variação
          </h2>
        </div>
        <Button variant="accent" size="sm" onClick={onInvestigate}>
          Investigar recortes →
        </Button>
      </div>
      {loading ? (
        <p role="status" className="text-sm text-muted">
          Conferindo população faturada e grupos de consumo deste recorte…
        </p>
      ) : error ? (
        <div role="alert" className="text-sm text-muted">
          <p>
            Não foi possível consultar o detalhamento. Os valores observados
            permanecem disponíveis.
          </p>
          {onRetry ? (
            <Button
              className="mt-2"
              variant="control"
              size="sm"
              onClick={onRetry}
            >
              Tentar detalhamento novamente
            </Button>
          ) : null}
        </div>
      ) : !diagnosis || diagnosis.status === "unavailable" ? (
        <p role="status" className="text-sm text-muted">
          Não há evidências adicionais suficientes para diagnosticar este
          recorte.
        </p>
      ) : (
        <>
          <div className="grid gap-5 md:grid-cols-2">
            {diagnosis.volume_offset_percent !== null ? (
              <article>
                <h3 className="text-sm font-semibold text-content">
                  O volume reduziu o ganho de preço
                </h3>
                <p className="mt-2 text-sm text-muted">
                  A contribuição negativa do volume anulou{" "}
                  <strong className="text-content">
                    {pct(diagnosis.volume_offset_percent)}
                  </strong>{" "}
                  do ganho monetário de preço
                  {partial ? " entre as parcelas conhecidas" : ""}.
                </p>
              </article>
            ) : null}
            {diagnosis.concentration ? (
              <article>
                <h3 className="text-sm font-semibold text-content">
                  Onde a redução se concentra
                </h3>
                <p className="mt-2 text-sm text-muted">
                  <strong className="text-content">
                    {diagnosis.concentration.labels.join(" e ")}
                  </strong>{" "}
                  {diagnosis.concentration.labels.length === 1
                    ? "concentra"
                    : "concentram"}{" "}
                  {pct(diagnosis.concentration.share_negative_volume_percent)}{" "}
                  das contribuições negativas de volume entre os grupos
                  conhecidos.
                </p>
              </article>
            ) : null}
            {diagnosis.population ? (
              <article>
                <h3 className="text-sm font-semibold text-content">
                  Como mudou a população faturada
                </h3>
                <p className="mt-2 text-sm text-muted">
                  De{" "}
                  <strong className="text-content">
                    {diagnosis.population.initial_billed_uc_count.toLocaleString(
                      "pt-BR",
                    )}
                  </strong>{" "}
                  para{" "}
                  <strong className="text-content">
                    {diagnosis.population.final_billed_uc_count.toLocaleString(
                      "pt-BR",
                    )}
                  </strong>{" "}
                  UCs com fatura observada
                  {diagnosis.population.change_percent !== null
                    ? ` (${percentage(diagnosis.population.change_percent)})`
                    : ""}
                  . São UCs distintas de cada janela, não o total histórico de
                  clientes cadastrados.
                </p>
              </article>
            ) : null}
          </div>
          <article className="border-t border-border pt-4">
            <h3 className="text-sm font-semibold text-content">
              Quais clientes reduziram o consumo?
            </h3>
            {diagnosis.gd.status === "unavailable" ? (
              <p className="mt-2 text-sm text-muted">
                A comparação por conexão de GD não pôde ser reconciliada neste
                recorte.
              </p>
            ) : (
              <>
                {diagnosis.gd.share_negative_volume_percent !== null ? (
                  <p className="mt-2 text-sm text-muted">
                    UCs com conexão de GD entre as janelas ou durante a janela
                    final concentram{" "}
                    <strong className="text-content">
                      {pct(diagnosis.gd.share_negative_volume_percent)}
                    </strong>{" "}
                    das contribuições negativas de volume da base pareada.
                  </p>
                ) : null}
                <div className="mt-3 overflow-x-auto">
                  <table className="w-full text-left text-sm">
                    <caption className="sr-only">
                      Consumo medido das mesmas UCs e meses nas duas janelas por
                      conexão de GD
                    </caption>
                    <thead>
                      <tr className="border-b border-border">
                        <th
                          scope="col"
                          className="py-2 pr-4 text-xs font-medium text-muted"
                        >
                          Grupo de comparação
                        </th>
                        <th
                          scope="col"
                          className="py-2 pr-4 text-right text-xs font-medium text-muted"
                        >
                          UCs elegíveis
                        </th>
                        <th
                          scope="col"
                          className="py-2 text-right text-xs font-medium text-muted"
                        >
                          Variação do consumo medido
                        </th>
                      </tr>
                    </thead>
                    <tbody>
                      {diagnosis.gd.cohorts.map((row) => (
                        <tr
                          key={row.group}
                          className="border-b border-border last:border-0"
                        >
                          <th
                            scope="row"
                            className="py-3 pr-4 font-normal text-content"
                          >
                            {cohortLabels[row.group]}
                          </th>
                          <td className="py-3 pr-4 text-right text-muted">
                            {row.uc_count.toLocaleString("pt-BR")}
                          </td>
                          <td className="py-3 text-right font-medium text-content">
                            {row.measured_energy_change_percent === null
                              ? "Base insuficiente"
                              : percentage(row.measured_energy_change_percent)}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </>
            )}
            <p className="mt-3 text-xs leading-relaxed text-muted">
              Comparação das mesmas UCs com ao menos seis pares mensais válidos.
              A relação com a data de conexão é observada; a Gold não mede
              energia gerada ou compensada e não comprova que GD causou toda a
              redução.
            </p>
          </article>
        </>
      )}
    </section>
  );
}
