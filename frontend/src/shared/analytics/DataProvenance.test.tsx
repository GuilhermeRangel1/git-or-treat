import { render, screen, within } from "@testing-library/react";
import { expect, it } from "vitest";
import DataProvenance from "./DataProvenance";

const source = {
  kind: "gold_csv",
  version: `GOLD-ARTIFICIAL:${"a".repeat(64)}`,
  is_demo: false,
  updated_at: "2026-10-29T13:00:00Z",
};

it("mostra período, unidades, lote completo e limitações sem truncar a identidade", () => {
  render(
    <DataProvenance
      source={source}
      period={{ start: "2022-07", end: "2026-06" }}
      units={["R$", "kWh"]}
      limitations={["Pagamentos ausentes.", "Pagamentos ausentes."]}
    />,
  );
  const panel = screen.getByRole("region", {
    name: "Período, unidades e fonte dos dados",
  });
  expect(within(panel).getByText("07/2022 a 06/2026")).toBeVisible();
  expect(within(panel).getByText("R$ · kWh")).toBeVisible();
  expect(within(panel).getByText(source.version)).toHaveClass("break-all");
  expect(within(panel).getByText("Importação local")).toBeVisible();
  expect(within(panel).getAllByText("Pagamentos ausentes.")).toHaveLength(1);
});

it("distingue cobertura mensal de vigência da fila e preserva a indisponibilidade", () => {
  render(
    <DataProvenance
      source={source}
      period={{ start: "2022-07", end: "2026-06" }}
      units={["UCs", "kWh (estimativa indisponível)"]}
      limitations={["Sem estimativa de recuperação."]}
      periodLabel="Cobertura do consumo no lote"
      periodNote="Fila sem janela temporal própria."
    />,
  );
  expect(screen.getByText("Cobertura do consumo no lote")).toBeVisible();
  expect(screen.getByText("Fila sem janela temporal própria.")).toBeVisible();
  expect(screen.getByText(/kWh \(estimativa indisponível\)/)).toBeVisible();
});
