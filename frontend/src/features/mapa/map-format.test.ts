import { describe, expect, it } from "vitest";
import {
  compactLayerValue,
  formatCompetence,
  formatPeriod,
  layerValue,
  neighborhoodLabel,
  signedMoney,
} from "./map-format";

// O Intl do pt-BR separa "R$" do número com espaço sem quebra.
const plain = (text: string) => text.replace(/ /g, " ");

describe("formatação de competência", () => {
  it("usa mês abreviado e ano, como a barra de filtros", () => {
    expect(formatCompetence("2026-06")).toBe("Jun/2026");
    expect(formatPeriod("2026-05", "2026-06")).toBe("Mai/2026 a Jun/2026");
  });

  it("devolve o texto original quando não é uma competência", () => {
    expect(formatCompetence("junho")).toBe("junho");
    expect(formatCompetence("2026-13")).toBe("2026-13");
  });
});

describe("valores da camada", () => {
  it("resume valores grandes e preserva o valor completo à parte", () => {
    expect(plain(compactLayerValue(57324.09, "revenue"))).toBe("R$ 57,3 mil");
    expect(plain(compactLayerValue(4313585.27, "revenue"))).toBe("R$ 4,3 mi");
    expect(plain(layerValue(4313585.27, "revenue"))).toBe("R$ 4.313.585,27");
  });

  it("usa kWh nas camadas de consumo", () => {
    expect(plain(compactLayerValue(57324, "consumption"))).toBe("57,3 mil kWh");
    expect(plain(layerValue(1500, "consumption"))).toBe("1.500 kWh");
  });

  it("mostra o sinal nas camadas de variação", () => {
    expect(plain(compactLayerValue(-1200000, "revenue_change"))).toBe(
      "−R$ 1,2 mi",
    );
    expect(plain(compactLayerValue(50000, "consumption_change"))).toBe(
      "+50 mil kWh",
    );
    expect(plain(layerValue(-5, "revenue_change"))).toBe("−R$ 5,00");
    expect(plain(signedMoney(0))).toBe("R$ 0,00");
    expect(signedMoney(null)).toBe("Indisponível");
  });
});

describe("rótulo de bairro", () => {
  it("tira o prefixo do município quando ele é o do painel", () => {
    expect(
      neighborhoodLabel(
        "JABOATÃO DOS GUARARAPES / SUCUPIRA",
        "Jaboatão dos Guararapes",
      ),
    ).toBe("SUCUPIRA");
  });

  it("ignora acento e caixa na comparação", () => {
    expect(
      neighborhoodLabel(
        "SAO LOURENCO DA MATA / CENTRO",
        "São Lourenço da Mata",
      ),
    ).toBe("CENTRO");
  });

  it("mantém o rótulo quando o prefixo é de outro município ou não existe", () => {
    expect(neighborhoodLabel("OLINDA / CARMO", "Recife")).toBe(
      "OLINDA / CARMO",
    );
    expect(neighborhoodLabel("CENTRO", "Recife")).toBe("CENTRO");
    expect(neighborhoodLabel("RECIFE / ", "Recife")).toBe("RECIFE / ");
  });
});
