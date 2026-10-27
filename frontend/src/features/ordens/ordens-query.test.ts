import { expect, it } from "vitest";
import { formatOrderDate, parseOrdersQuery } from "./ordens-query";

it.each([
  ["has_result=true", "true", true],
  ["has_result=false", "false", false],
])("encaminha o filtro canônico %s para a API", (query, value, hasResult) => {
  const parsed = parseOrdersQuery(new URLSearchParams(query));

  expect(parsed.hasResult).toBe(hasResult);
  expect(new URLSearchParams(parsed.request).get("has_result")).toBe(value);
});

it("preserva prioridade e tamanho da página ao consultar o resultado", () => {
  const parsed = parseOrdersQuery(
    new URLSearchParams("priority=ALTA&page=3&page_size=5&has_result=false"),
  );

  expect(parsed.request).toBe(
    "priority=ALTA&has_result=false&page=3&page_size=5",
  );
  expect(parsed.page).toBe(3);
  expect(parsed.pageSize).toBe(5);
});

it("mantém o identificador pedido na URL sem enviá-lo como filtro da API", () => {
  const parsed = parseOrdersQuery(
    new URLSearchParams("uc_id=UC-1041&order_id=77"),
  );

  expect(parsed.orderId).toBe(77);
  expect(new URLSearchParams(parsed.request).has("order_id")).toBe(false);
});

it("recusa identificador de ordem inválido na URL", () => {
  expect(() => parseOrdersQuery(new URLSearchParams("order_id=0"))).toThrow(
    "O identificador da ordem informado não é válido.",
  );
});

it.each(["has_result=TRUE", "has_result=1", "has_result="])(
  "recusa has_result não canônico (%s)",
  (query) => {
    expect(() => parseOrdersQuery(new URLSearchParams(query))).toThrow(
      "O filtro de resultado informado não é válido.",
    );
  },
);

it("recusa has_result duplicado", () => {
  expect(() =>
    parseOrdersQuery(new URLSearchParams("has_result=true&has_result=false")),
  ).toThrow("inválidos ou estão repetidos");
});

it("formata a data da OS em dd/MM com ano completo no fuso de Recife", () => {
  expect(formatOrderDate("2026-10-24T01:30:00Z")).toBe(
    "23/10/2026, 22:30 (Recife)",
  );
});
