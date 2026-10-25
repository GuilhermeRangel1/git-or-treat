import { expect, it } from "vitest";
import { parseOrdersQuery } from "./ordens-query";

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
