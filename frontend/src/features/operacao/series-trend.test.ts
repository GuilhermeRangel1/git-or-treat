import { describe, expect, it } from "vitest";
import { describeVariation, trendOf } from "./series-trend";

describe("trendOf", () => {
  it("trata valor maior como piora e menor como melhora", () => {
    expect(trendOf(2, 1)).toBe("worse");
    expect(trendOf(1, 2)).toBe("better");
  });

  it("trata valores iguais como estáveis", () => {
    expect(trendOf(1.5, 1.5)).toBe("flat");
    expect(trendOf(0, 0)).toBe("flat");
  });

  it("ignora diferenças menores que a precisão exibida", () => {
    expect(trendOf(1.0004, 1)).toBe("flat");
    expect(trendOf(1.001, 1)).toBe("worse");
  });

  it("não compara quando falta um dos meses", () => {
    expect(trendOf(null, 1)).toBe("none");
    expect(trendOf(1, null)).toBe("none");
    expect(trendOf(null, null)).toBe("none");
  });
});

describe("describeVariation", () => {
  it("descreve piora em percentual", () => {
    expect(describeVariation(1.5, 1, "h/UC")).toEqual({
      trend: "worse",
      short: "▲ +50% vs mês anterior",
      sentence: "piorou 50% em relação ao mês anterior",
    });
  });

  it("descreve melhora em percentual", () => {
    expect(describeVariation(0.5, 1, "h/UC")).toEqual({
      trend: "better",
      short: "▼ −50% vs mês anterior",
      sentence: "melhorou 50% em relação ao mês anterior",
    });
  });

  it("usa a diferença absoluta quando o mês anterior foi zero", () => {
    expect(describeVariation(0.5, 0, "h/UC")).toEqual({
      trend: "worse",
      short: "▲ +0,5 h/UC vs mês anterior",
      sentence: "piorou 0,5 h/UC em relação ao mês anterior",
    });
  });

  it("descreve estabilidade e omite o que não tem comparação", () => {
    expect(describeVariation(1, 1, "h/UC")?.trend).toBe("flat");
    expect(describeVariation(1, null, "h/UC")).toBeNull();
    expect(describeVariation(null, 1, "h/UC")).toBeNull();
  });
});
