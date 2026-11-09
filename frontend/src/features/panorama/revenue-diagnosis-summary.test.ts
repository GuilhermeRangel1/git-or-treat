import { describe, expect, it } from "vitest";
import type {
  RevenueDiagnosis,
  RevenueWindow,
} from "@/shared/analytics/revenueContract";
import {
  buildRevenueDiagnosisSummary,
  type DiagnosisSummary,
} from "./revenue-diagnosis-summary";
import {
  revenueDiagnosis,
  revenueWindow,
} from "./revenue-diagnosis.test-support";

const CONCENTRATION = {
  dimension: "municipio",
  labels: ["RECIFE", "JABOATÃO DOS GUARARAPES"],
  share_negative_volume_percent: 69.5,
};
const GD = {
  status: "available",
  cohorts: [],
  share_negative_volume_percent: 92.7,
  limitations: [],
};
const GD_LEAD =
  "Os dados apontam a GD como principal explicação da queda de volume:";
const NEXT_STEP =
  "medir a energia gerada pelas UCs com GD; a causa ainda não está comprovada.";

function gdShare(value: number | null) {
  return { gd: { ...GD, share_negative_volume_percent: value } };
}

function build(
  window: Record<string, unknown> = {},
  diagnosis: Record<string, unknown> = {},
) {
  return buildRevenueDiagnosisSummary(
    revenueWindow({
      change_percent: 8.1,
      ...window,
    }) as unknown as RevenueWindow,
    revenueDiagnosis({
      concentration: CONCENTRATION,
      gd: GD,
      ...diagnosis,
    }) as unknown as RevenueDiagnosis,
  );
}

/** Intl usa espaço não separável entre "R$" e o número. */
function plain(value: string) {
  return value.replace(/ /g, " ");
}

function paragraphs(summary: DiagnosisSummary) {
  return summary.paragraphs.map((p) =>
    plain(p.body ? `${p.lead} ${p.body}` : p.lead),
  );
}

function allText(summary: DiagnosisSummary) {
  return [
    summary.question,
    ...paragraphs(summary),
    summary.nextStep ?? "",
    summary.footer,
  ].join(" ");
}

describe("buildRevenueDiagnosisSummary", () => {
  it("monta pergunta, dois parágrafos, próximo passo e rodapé com todos os dados", () => {
    const summary = build()!;
    expect(summary.question).toBe("Por que a receita subiu só 8,1%?");
    expect(paragraphs(summary)).toEqual([
      "Porque o volume devolveu 37,2% do ganho de preço. O preço observado adicionou R$ 1,1 mil e o volume retirou R$ 402,00. Saldo: +R$ 796,00.",
      `${GD_LEAD} 92,7% dela está em UCs com GD. No território, 69,5% está em Recife e Jaboatão dos Guararapes.`,
    ]);
    expect(summary.nextStep).toBe(NEXT_STEP);
    expect(summary.footer).toBe("Preço observado não é tarifa");
  });

  it("cada parágrafo começa por uma frase-chave e a pergunta termina com ?", () => {
    const summary = build()!;
    expect(summary.question).toMatch(/^Por que .+\?$/);
    for (const paragraph of summary.paragraphs)
      expect(paragraph.lead.trim().length).toBeGreaterThan(0);
  });

  it("sem change_percent, pergunta pelo saldo em reais", () => {
    expect(plain(build({ change_percent: null })!.question)).toBe(
      "Por que a receita subiu só R$ 796,00?",
    );
  });

  it("sem offset, diz que o volume retirou parte do ganho", () => {
    expect(build({}, { volume_offset_percent: null })!.paragraphs[0].lead).toBe(
      "Porque o volume retirou parte do ganho de preço.",
    );
  });

  it("sem concentração, tira só a frase do território", () => {
    const summary = build({}, { concentration: null })!;
    expect(paragraphs(summary)[1]).toBe(
      `${GD_LEAD} 92,7% dela está em UCs com GD.`,
    );
    expect(summary.nextStep).toBe(NEXT_STEP);
  });

  it("sem GD, fica só o território e some o próximo passo", () => {
    const summary = build({}, gdShare(null))!;
    expect(paragraphs(summary)).toHaveLength(2);
    expect(paragraphs(summary)[1]).toBe(
      "No território, 69,5% da queda de volume está em Recife e Jaboatão dos Guararapes.",
    );
    expect(summary.nextStep).toBeNull();
    expect(allText(summary)).not.toMatch(/GD/);
  });

  it("sem GD e sem concentração, fica só o parágrafo da conta", () => {
    const summary = build({}, { concentration: null, ...gdShare(null) })!;
    expect(summary.paragraphs).toHaveLength(1);
    expect(summary.nextStep).toBeNull();
  });

  it("com GD abaixo de 50%, não diz que os dados apontam a GD", () => {
    const summary = build({}, gdShare(41))!;
    expect(paragraphs(summary)[1]).toBe(
      "41% da queda de volume está em UCs com GD. No território, 69,5% está em Recife e Jaboatão dos Guararapes.",
    );
    expect(allText(summary)).not.toMatch(/os dados apontam/i);
    expect(summary.nextStep).toBe(NEXT_STEP);
  });

  it("com GD em exatamente 50%, já usa a principal explicação", () => {
    expect(build({}, gdShare(50))!.paragraphs[1].lead).toBe(GD_LEAD);
  });

  it("usa os nomes que vêm da API, sem municípios fixos", () => {
    const summary = build(
      {},
      {
        concentration: {
          ...CONCENTRATION,
          labels: ["OLINDA", "PAULISTA", "CABO DE SANTO AGOSTINHO"],
        },
      },
    )!;
    expect(paragraphs(summary)[1]).toContain(
      "está em Olinda, Paulista e Cabo de Santo Agostinho.",
    );
    expect(allText(summary)).not.toMatch(/Recife/);
  });

  it("em base parcial, o rodapé avisa", () => {
    expect(build({ status: "partial" })!.footer).toBe(
      "Preço observado não é tarifa · Base parcial",
    );
  });

  it.each([
    ["preço que não adicionou", { components: { preco: -10, volume: -402 } }],
    ["volume que não retirou", { components: { preco: 1081, volume: 5 } }],
    ["saldo negativo", { total_change_brl: -10 }],
    ["saldo nulo", { total_change_brl: null }],
    ["base indisponível", { status: "unavailable" }],
    ["sem janelas", { windows: [] }],
  ])("devolve null com %s", (_name, overrides) => {
    expect(build(overrides)).toBeNull();
  });

  it("devolve null sem janela", () => {
    expect(buildRevenueDiagnosisSummary(null, null)).toBeNull();
  });

  it.each([
    ["todos os dados", {}],
    ["GD abaixo de 50%", gdShare(30)],
    ["sem offset", { volume_offset_percent: null }],
    ["sem GD", gdShare(null)],
  ])(
    "com %s, nunca usa causa proibida nem liga 'porque' ao volume",
    (_name, overrides) => {
      const summary = build({}, overrides)!;
      const text = allText(summary);
      expect(text).not.toMatch(/devido a|causou/i);
      expect(text).not.toMatch(/saldo\s*=|preço\s*[−-]\s*volume/i);
      // "Porque" aparece uma única vez, na frase-chave da conta de preço e volume.
      expect(text.match(/porque|por isso|já que/gi)).toEqual(["Porque"]);
      expect(summary.paragraphs[0].lead).toMatch(
        /^Porque o volume (devolveu|retirou) .+ ganho de preço\.$/,
      );
    },
  );
});
