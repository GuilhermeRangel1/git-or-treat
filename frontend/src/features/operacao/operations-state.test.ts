import { describe, expect, it } from "vitest";
import {
  applyOperationFilters,
  changeOperationMetric,
  openOperationDetail,
  paginateOperationDetail,
  paginateOperationRanking,
  parseOperationParams,
  returnToOperationRanking,
} from "./operations-state";

describe("estado de URL da Operação", () => {
  it("usa defaults e aceita alias periodo", () => {
    expect(parseOperationParams(new URLSearchParams()).query).toMatchObject({
      start: "2025-01",
      end: "2025-02",
      metric: "dec",
      page: 1,
      pageSize: 20,
    });
    expect(
      parseOperationParams(new URLSearchParams("periodo=2025-03")).query,
    ).toMatchObject({
      start: "2025-03",
      end: "2025-03",
    });
  });

  it.each([
    ["competencia_inicio=2025-13&competencia_fim=2025-02", /mês/i],
    ["competencia_inicio=2025-03&competencia_fim=2025-02", /anterior/i],
    ["competencia_inicio=2014-01&competencia_fim=2025-02", /120/],
    [
      "periodo=2025-01&competencia_inicio=2025-01&competencia_fim=2025-02",
      /combine/i,
    ],
    ["periodo=2025-01&periodo=2025-02", /duplicado/i],
    ["page=1000001", /página/i],
    ["ranking_page=0", /página do ranking/i],
    ["ranking_page=abc", /página do ranking/i],
    ["ranking_page=1000001", /página do ranking/i],
    ["page=0&page_size=101", /página|tamanho/i],
    ["metric=energy", /métrica/i],
    ["bairro=Centro", /suportado/i],
    ["feeder_id=" + "A".repeat(101), /alimentador/i],
  ])("não gera consulta para URL inválida: %s", (search, message) => {
    const parsed = parseOperationParams(new URLSearchParams(search));
    expect(parsed.query).toBeNull();
    expect(parsed.errors.join(" ")).toMatch(message);
  });

  it("recusa parâmetro repetido mesmo quando o valor é igual", () => {
    expect(
      parseOperationParams(new URLSearchParams("page=1&page=1")).query,
    ).toBeNull();
  });

  it("aplica filtros resetando página, troca métrica e mantém contexto no detalhe/volta", () => {
    const original = new URLSearchParams(
      "competencia_inicio=2025-01&competencia_fim=2025-02&alimentador=AL-02&metric=fec&page=7&page_size=40",
    );
    const filtered = applyOperationFilters(original, {
      start: "2025-02",
      end: "2025-03",
      feederId: "AL-01",
    });
    expect(filtered.get("page")).toBeNull();
    expect(filtered.get("metric")).toBe("fec");
    const sorted = changeOperationMetric(filtered, "dec");
    const detail = openOperationDetail(sorted, "AL-03");
    expect(parseOperationParams(detail).query).toMatchObject({
      start: "2025-02",
      end: "2025-03",
      feederId: "AL-01",
      detailFeederId: "AL-03",
      metric: "dec",
      page: 1,
    });
    const page = paginateOperationDetail(detail, 3);
    expect(page.get("page")).toBe("3");
    expect(page.get("feeder_id")).toBe("AL-03");
    const returned = returnToOperationRanking(page);
    expect(returned.get("feeder_id")).toBeNull();
    expect(returned.get("competencia_inicio")).toBe("2025-02");
    expect(returned.get("competencia_fim")).toBe("2025-03");
    expect(returned.get("metric")).toBe("dec");
  });

  it("mantém a página do ranking separada da paginação legada do detalhe", () => {
    const original = new URLSearchParams(
      "competencia_inicio=2025-01&competencia_fim=2025-02&ranking_page=3&page=7&page_size=40",
    );
    expect(parseOperationParams(original).query).toMatchObject({
      rankingPage: 3,
      page: 7,
      pageSize: 40,
    });
    const detail = openOperationDetail(original, "AL-40");
    expect(detail.get("ranking_page")).toBe("3");
    expect(detail.get("page")).toBeNull();
    const detailPage = paginateOperationDetail(detail, 2);
    expect(detailPage.get("page")).toBe("2");
    expect(detailPage.get("ranking_page")).toBe("3");
    const returned = returnToOperationRanking(detailPage);
    expect(returned.get("ranking_page")).toBe("3");
    expect(returned.get("page")).toBeNull();
    expect(
      paginateOperationRanking(returned, 1).get("ranking_page"),
    ).toBeNull();
  });
});
