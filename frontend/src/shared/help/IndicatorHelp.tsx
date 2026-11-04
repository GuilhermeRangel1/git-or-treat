import { useId, useRef, useState } from "react";
import { BookOpen, Search } from "lucide-react";
import Button from "@/shared/ui/Button";
import Modal from "@/shared/ui/Modal";
import FaqExamples from "./FaqExamples";
import {
  currentEntries,
  findConcepts,
  indicatorFaq,
  type HelpScreen,
} from "./indicatorFaq";

export default function IndicatorHelp({ screen }: { screen: HelpScreen }) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const trigger = useRef<HTMLButtonElement>(null);
  const searchId = useId();
  const entries = currentEntries(indicatorFaq.entries, screen);
  const result = findConcepts(entries, query);
  return (
    <>
      <Button
        ref={trigger}
        type="button"
        variant="ghost"
        size="sm"
        className="h-auto min-h-11 py-2 text-sm"
        onClick={() => {
          setQuery("");
          setOpen(true);
        }}
        leftIcon={<BookOpen aria-hidden="true" className="size-4" />}
      >
        <span className="hidden sm:inline">Entenda os indicadores</span>
        <span className="sm:hidden">Ajuda</span>
      </Button>
      <Modal
        open={open}
        onClose={() => setOpen(false)}
        triggerRef={trigger}
        title="Entenda os indicadores"
        description="Explicações do negócio para ajudar na leitura dos seus dados."
        closeLabel="Fechar ajuda dos indicadores"
        size="sm"
        header="sticky"
      >
        <div className="grid gap-5 p-5 sm:p-6">
          <p className="rounded-xl bg-brand/5 p-3 text-sm leading-6 text-content">
            Esta ajuda explica conceitos. Valores de um município, classe ou
            período são consultados no Assistente e nas telas do portal.
          </p>
          <FaqExamples />
          <div className="grid gap-2">
            <label htmlFor={searchId} className="text-sm font-medium">
              Qual conceito você quer entender?
            </label>
            <div className="relative">
              <Search
                aria-hidden="true"
                className="absolute top-3.5 left-3 size-4 text-muted"
              />
              <input
                id={searchId}
                type="search"
                onKeyDown={(event) => {
                  if (event.key === "Escape") {
                    event.preventDefault();
                    event.stopPropagation();
                    setOpen(false);
                  }
                }}
                value={query}
                maxLength={200}
                onChange={(event) => setQuery(event.target.value)}
                placeholder="Ex.: receita, consumo, DEC ou FEC"
                className="min-h-11 w-full rounded-xl border border-divider bg-canvas py-3 pr-3 pl-10 text-base text-content focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand"
              />
            </div>
          </div>
          <div
            aria-live="polite"
            role="status"
            aria-label="Resultado da busca de conceitos"
            className="text-sm text-muted"
          >
            {result.kind === "quantitative"
              ? "Essa pergunta precisa de uma consulta aos dados. Use o campo de mensagem do Assistente ou os filtros da tela para obter o valor e seu fundamento."
              : result.kind === "unmatched"
                ? "Não encontramos uma definição para essa busca. Tente o nome de um indicador, como consumo ou DEC. Para outras perguntas, use o Assistente."
                : result.entries.length > 1 && query
                  ? "Encontrei estes conceitos. Escolha a pergunta que corresponde à sua dúvida."
                  : `${result.entries.length} explicações disponíveis nesta tela.`}
          </div>
          <div className="grid gap-3">
            {result.entries.map((entry) => (
              <details
                key={entry.id}
                className="group rounded-xl border border-divider bg-canvas/50 p-4"
              >
                <summary className="cursor-pointer text-base font-semibold text-content focus-visible:rounded focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-brand">
                  {entry.question}
                </summary>
                <div className="mt-3 grid gap-3 text-sm leading-6">
                  <p className="text-xs font-medium tracking-wide text-brand">
                    EXPLICAÇÃO DO INDICADOR
                  </p>
                  {entry.definitions.map((definition) => (
                    <p key={definition.metricId} className="text-content">
                      <strong>{definition.label}: </strong>
                      {definition.text}
                    </p>
                  ))}
                  <p className="text-xs text-muted">
                    Fonte interna · {indicatorFaq.source} · Versão{" "}
                    {indicatorFaq.version}
                  </p>
                </div>
              </details>
            ))}
          </div>
          <p className="text-xs leading-5 text-muted">
            As definições são consultadas diretamente nesta ajuda, mesmo quando
            o serviço de IA está indisponível.
          </p>
        </div>
      </Modal>
    </>
  );
}
