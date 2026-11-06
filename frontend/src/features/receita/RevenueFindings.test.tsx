import { render, screen } from "@testing-library/react";
import { expect, it } from "vitest";
import RevenueFindings from "./RevenueFindings";
import { decodeRevenueDiagnosis, type RevenueDiagnosis } from "./contract";

const diagnosis: RevenueDiagnosis = {
  status: "partial",
  volume_offset_percent: 50,
  population: {
    initial_billed_uc_count: 20,
    final_billed_uc_count: 22,
    change_percent: 10,
  },
  concentration: {
    dimension: "municipio",
    labels: ["A", "B"],
    share_negative_volume_percent: 80,
  },
  gd: {
    status: "available",
    cohorts: [
      {
        group: "connected_between",
        uc_count: 10,
        measured_energy_change_percent: -70,
      },
      { group: "no_record", uc_count: 20, measured_energy_change_percent: 10 },
    ],
    share_negative_volume_percent: 100,
    limitations: [],
  },
  limitations: [],
};

it("mostra novos achados do recorte e atualiza a comparação sem repetir o case", () => {
  const { rerender } = render(
    <RevenueFindings diagnosis={diagnosis} partial onInvestigate={() => {}} />,
  );
  expect(screen.getByText(/anulou/)).toHaveTextContent("50%");
  expect(screen.getByText("−70%")).toBeVisible();
  expect(
    screen.queryByText(/Henrique|10,5%|premissas/),
  ).not.toBeInTheDocument();
  const next = structuredClone(diagnosis);
  next.gd.share_negative_volume_percent = 40;
  next.gd.cohorts[0].measured_energy_change_percent = -25;
  rerender(
    <RevenueFindings
      diagnosis={next}
      partial={false}
      onInvestigate={() => {}}
    />,
  );
  expect(screen.getByText("−25%")).toBeVisible();
  expect(screen.queryByText("−70%")).not.toBeInTheDocument();
  expect(
    screen.getByText(/conexão de GD entre as janelas ou durante/),
  ).toHaveTextContent("40%");
});

it("mantém ausência e base pequena explícitas", () => {
  const small = structuredClone(diagnosis);
  small.gd.cohorts[0].measured_energy_change_percent = null;
  render(
    <RevenueFindings diagnosis={small} partial onInvestigate={() => {}} />,
  );
  expect(screen.getByText("Base insuficiente")).toBeVisible();
});

it("valida a fronteira externa do diagnóstico", () => {
  expect(decodeRevenueDiagnosis(diagnosis)?.population?.change_percent).toBe(
    10,
  );
  expect(decodeRevenueDiagnosis(undefined)).toBeNull();
  expect(() =>
    decodeRevenueDiagnosis({
      ...diagnosis,
      population: { ...diagnosis.population, initial_billed_uc_count: 1.5 },
    }),
  ).toThrow();
  expect(() =>
    decodeRevenueDiagnosis({
      ...diagnosis,
      gd: { ...diagnosis.gd, share_negative_volume_percent: 101 },
    }),
  ).toThrow();
  expect(() =>
    decodeRevenueDiagnosis({
      ...diagnosis,
      gd: {
        ...diagnosis.gd,
        cohorts: [
          {
            group: "inventado",
            uc_count: 5,
            measured_energy_change_percent: 10,
          },
        ],
      },
    }),
  ).toThrow();
});
