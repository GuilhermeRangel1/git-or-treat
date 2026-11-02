import { Database, MessageCircle, ShieldCheck, Sparkles } from "lucide-react";

export function AssistantIdentity({ pending }: { pending: boolean }) {
  return (
    <aside
      aria-label="Assistente Grid 360"
      className="assistant-identity"
      data-pending={pending}
    >
      <div aria-hidden="true" className="assistant-emblem">
        <div className="assistant-emblem-aura" />
        <div className="assistant-emblem-orbit">
          <span />
        </div>
        <div className="assistant-emblem-orbit assistant-emblem-orbit-secondary">
          <span />
        </div>
        <div className="assistant-emblem-frame" />
        <div className="assistant-emblem-core">
          <Sparkles />
        </div>
        <span className="assistant-emblem-spark assistant-emblem-spark-one" />
        <span className="assistant-emblem-spark assistant-emblem-spark-two" />
      </div>
      <div className="assistant-name">
        <p className="font-heading text-[28px] font-semibold text-content">
          Grid 360
        </p>
        <p className="mt-1 text-xs font-semibold uppercase tracking-[0.12em] text-muted">
          Seu assistente de energia
        </p>
      </div>
      <span className="assistant-presence">
        <span
          className={pending ? "bg-brand" : "bg-[var(--accent-pistache)]"}
        />
        {pending ? "Consultando" : "Pronto para perguntar"}
      </span>
      <p className="assistant-identity-caption text-sm leading-6 text-muted">
        Transforme perguntas em uma leitura mais clara dos seus dados.
      </p>
      {pending && (
        <div className="assistant-processing-rail" aria-hidden="true">
          <p className="mb-4 text-xs font-semibold uppercase tracking-widest text-muted">
            Consulta em andamento
          </p>
          <div className="flex justify-center gap-3">
            {[ShieldCheck, Database, MessageCircle].map((Icon, index) => (
              <span
                key={index}
                style={{ animationDelay: `${index * 0.35}s` }}
                className="assistant-processing-icon"
              >
                <Icon className="size-4" />
              </span>
            ))}
          </div>
          <p className="mt-3 text-sm leading-6 text-muted">
            Aguarde a resposta fundamentada.
          </p>
        </div>
      )}
    </aside>
  );
}

export function ProcessingIndicator() {
  return (
    <div
      role="status"
      className="flex w-fit items-center gap-3 rounded-2xl border border-divider bg-canvas/50 px-4 py-3 text-base text-muted"
    >
      <Sparkles aria-hidden="true" className="size-4 text-brand" />
      <span>Consultando os dados</span>
      <span aria-hidden="true" className="flex gap-1">
        {[0, 1, 2].map((index) => (
          <span
            key={index}
            className="assistant-processing-dot"
            style={{ animationDelay: `${index * 0.2}s` }}
          />
        ))}
      </span>
    </div>
  );
}
