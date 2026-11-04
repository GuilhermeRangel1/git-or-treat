import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { expect, it } from "vitest";
import type { RevenueEnvelope } from "@/shared/analytics/revenueContract";
import MunicipalityPanel from "./MunicipalityPanel";
import { municipalities } from "./municipalities";

it("shows available amounts without a percentage-variation field", () => {
  const item = {
    comparison: {
      initial: { billed_amount: 100, measured_energy_kwh: 50 },
      final: { billed_amount: 120, measured_energy_kwh: 60 },
      billed_amount_change_brl: 20,
      measured_energy_change_kwh: 10,
      billed_amount_change_percent: 20,
    },
  } as unknown as RevenueEnvelope["data"]["breakdown"]["items"][number];

  render(
    <MemoryRouter>
      <MunicipalityPanel
        municipality={municipalities[0]}
        item={item}
        detail={undefined}
        detailError={false}
        query={null}
        layer="revenue"
        revenueHref={null}
        onRetryDetail={() => undefined}
      />
    </MemoryRouter>,
  );

  expect(screen.getByText("Faturamento · R$", { exact: true })).toBeVisible();
  expect(screen.queryByText(/percentual/i)).not.toBeInTheDocument();
});
