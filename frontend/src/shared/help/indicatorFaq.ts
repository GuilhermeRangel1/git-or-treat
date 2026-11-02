import catalog from "./indicatorFaq.generated.json";

export type HelpScreen =
  "assistente" | "panorama" | "receita" | "operacao" | "uc360";
export type FaqEntry = Omit<(typeof catalog.entries)[number], "validUntil"> & {
  validUntil: string | null;
};
export { catalog as indicatorFaq };

export function normalizeConcept(text: string) {
  return text
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase();
}

export function currentEntries(
  entries: FaqEntry[],
  screen: HelpScreen,
  today = new Date().toISOString().slice(0, 10),
) {
  // A duplicate identity is conflicting content, not an arbitrary first match.
  const ids = entries.map((entry) => entry.id);
  return entries.filter(
    (entry) =>
      entry.status === "active" &&
      entry.screens.includes(screen) &&
      entry.validFrom <= today &&
      (!entry.validUntil || entry.validUntil >= today) &&
      ids.filter((id) => id === entry.id).length === 1,
  );
}

export function findConcepts(entries: FaqEntry[], query: string) {
  const normalized = normalizeConcept(query).trim();
  if (!normalized) return { kind: "browse" as const, entries };
  if (
    /\d|\b(quanto|quantos|quantas|qual foi|compare|comparar|mes passado|este mes|janeiro|fevereiro|marco|abril|maio|junho|julho|agosto|setembro|outubro|novembro|dezembro|residencial|comercial|municipio|bairro|alimentador)\b|\bem\s+(?!que\b|kwh\b|reais\b|horas\b|media\b)[a-z]+/.test(
      normalized,
    )
  )
    return { kind: "quantitative" as const, entries: [] };
  const words = normalized.split(/[^a-z]+/).filter((word) => word.length > 2);
  const matches = entries.filter((entry) =>
    words.some(
      (word) =>
        entry.keywords.includes(word) ||
        (normalizeConcept(entry.question)
          .split(/[^a-z]+/)
          .includes(word) &&
          ![
            "qual",
            "que",
            "como",
            "uma",
            "entre",
            "dos",
            "das",
            "significa",
          ].includes(word)),
    ),
  );
  return {
    kind: matches.length ? ("concept" as const) : ("unmatched" as const),
    entries: matches,
  };
}
