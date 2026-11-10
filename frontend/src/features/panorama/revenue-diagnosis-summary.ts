import type {
  RevenueDiagnosis,
  RevenueWindow,
} from "@/shared/analytics/revenueContract";
import {
  compactMoney,
  groupLabel,
  percent,
  signedCompactMoney,
} from "./revenue-diagnosis-format";

/** Abaixo deste percentual, a GD não é apresentada como principal explicação. */
export const GD_MAIN_EXPLANATION_THRESHOLD = 50;

export type DiagnosisSummaryParagraph = {
  /** Frase-chave, exibida em negrito no início do parágrafo. */
  lead: string;
  /** Restante do parágrafo; pode ser vazio. */
  body: string;
};

/** Conteúdo do cartão "Resposta ao Diretor". */
export type DiagnosisSummary = {
  question: string;
  paragraphs: DiagnosisSummaryParagraph[];
  /** Texto da linha "Próximo passo"; null quando não há dado de GD. */
  nextStep: string | null;
  footer: string;
};

function joinLabels(labels: string[]) {
  const names = labels.map(groupLabel);
  if (names.length <= 1) return names.join("");
  return `${names.slice(0, -1).join(", ")} e ${names.at(-1)}`;
}

/**
 * Monta a resposta do Diretor Comercial por regras fixas, sem IA.
 * Só responde "por que a receita subiu só…" quando o preço adicionou, o volume
 * retirou e o saldo ficou positivo; em qualquer outro caso devolve null.
 * "Porque" só explica a conta de preço e volume, nunca a causa do volume.
 */
export function buildRevenueDiagnosisSummary(
  window: RevenueWindow | null | undefined,
  diagnosis: RevenueDiagnosis | null | undefined,
): DiagnosisSummary | null {
  if (
    !window ||
    (window.status !== "available" && window.status !== "partial") ||
    window.windows.length !== 4
  )
    return null;
  const price = window.components.preco ?? null;
  const volume = window.components.volume ?? null;
  const balance = window.total_change_brl;
  if (
    price === null ||
    volume === null ||
    balance === null ||
    !(price > 0) ||
    !(volume < 0) ||
    !(balance > 0)
  )
    return null;

  const change = window.change_percent ?? null;
  const offset = diagnosis?.volume_offset_percent ?? null;
  const paragraphs: DiagnosisSummaryParagraph[] = [
    {
      lead:
        offset !== null
          ? `Porque o volume devolveu ${percent(offset)} do ganho de preço.`
          : "Porque o volume retirou parte do ganho de preço.",
      body: `O preço observado adicionou ${compactMoney(price)} e o volume retirou ${compactMoney(volume)}. Saldo: ${signedCompactMoney(balance)}.`,
    },
  ];

  const gd = diagnosis?.gd.share_negative_volume_percent ?? null;
  const concentration = diagnosis?.concentration ?? null;
  const scope =
    concentration?.dimension === "classe_consumo"
      ? "Entre as classes"
      : "No território";
  const places = concentration ? joinLabels(concentration.labels) : "";

  if (gd !== null) {
    const territory = concentration
      ? `${scope}, ${percent(concentration.share_negative_volume_percent)} está em ${places}.`
      : "";
    paragraphs.push(
      gd >= GD_MAIN_EXPLANATION_THRESHOLD
        ? {
            lead: "Os dados apontam a GD como principal explicação da queda de volume:",
            body: [`${percent(gd)} dela está em UCs com GD.`, territory]
              .filter(Boolean)
              .join(" "),
          }
        : {
            lead: `${percent(gd)} da queda de volume está em UCs com GD.`,
            body: territory,
          },
    );
  } else if (concentration) {
    paragraphs.push({
      lead: `${scope}, ${percent(concentration.share_negative_volume_percent)} da queda de volume está em ${places}.`,
      body: "",
    });
  }

  return {
    question: `Por que a receita subiu só ${change !== null ? percent(change) : compactMoney(balance)}?`,
    paragraphs,
    nextStep:
      gd !== null
        ? "medir a energia gerada pelas UCs com GD; a causa ainda não está comprovada."
        : null,
    footer:
      window.status === "partial"
        ? "Preço observado não é tarifa · Base parcial"
        : "Preço observado não é tarifa",
  };
}
