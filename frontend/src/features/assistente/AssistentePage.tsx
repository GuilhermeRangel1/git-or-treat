export default function AssistentePage() {
  return (
    <section
      aria-labelledby="assistant-heading"
      className="mx-auto flex h-full min-h-0 w-full max-w-[960px] flex-col gap-3 rounded-[20px] border border-divider bg-surface p-3 lg:max-h-[800px] lg:gap-4 lg:p-6"
    >
      <header className="flex min-h-[88px] shrink-0 items-start lg:-mr-0.5 lg:min-h-12 [@media(max-height:480px)]:min-h-0">
        <p className="font-heading text-lg leading-[26px] font-semibold lg:text-xl lg:leading-7">
          Assistente Grid 360
        </p>
      </header>
      <div
        role="region"
        aria-label="Histórico da conversa"
        tabIndex={0}
        className="flex min-h-0 flex-1 flex-col gap-4 overflow-y-auto overscroll-contain focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand lg:-mr-0.5 lg:p-4"
      >
        <h1
          id="assistant-heading"
          className="font-heading text-[26px] leading-[34px] font-semibold lg:text-[32px] lg:leading-10 lg:tracking-[-0.64px]"
        >
          O que você quer investigar?
        </h1>
        <p className="text-sm leading-[22px] text-content">
          Explore os exemplos de consumo, faturamento e continuidade. Cada
          resposta informa seu período, recorte e fundamento.
        </p>
      </div>
    </section>
  );
}
