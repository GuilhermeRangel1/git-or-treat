import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, it } from "vitest";
import OperationSeries from "./OperationSeries";

const period = {
  start: "2025-01",
  end: "2025-03",
  granularity: "month" as const,
};

it("mantém zero conhecido, lacuna indisponível e abre a tabela do período", async () => {
  const user = userEvent.setup();
  render(
    <OperationSeries
      period={period}
      series={[
        {
          period: { start: "2024-12", end: "2024-12", granularity: "month" },
          status: "available",
          dec_hours_per_uc: 4,
          fec_interruptions_per_uc: 3,
          denominator_uc_count: 10,
        },
        {
          period: { start: "2025-01", end: "2025-01", granularity: "month" },
          status: "available",
          dec_hours_per_uc: 0,
          fec_interruptions_per_uc: 0,
          denominator_uc_count: 10,
        },
        {
          period: { start: "2025-03", end: "2025-03", granularity: "month" },
          status: "empty",
          dec_hours_per_uc: null,
          fec_interruptions_per_uc: null,
          denominator_uc_count: 0,
        },
        {
          period: { start: "2025-04", end: "2025-04", granularity: "month" },
          status: "available",
          dec_hours_per_uc: 2,
          fec_interruptions_per_uc: 1,
          denominator_uc_count: 10,
        },
      ]}
    />,
  );

  const dec = screen.getByRole("region", { name: "Série mensal de DEC" });
  expect(dec).toHaveTextContent("Jan/2025: 0 h/UC");
  expect(dec).toHaveTextContent("Fev/2025: indisponível");
  expect(dec).toHaveTextContent("Mar/2025: indisponível");
  expect(dec).not.toHaveTextContent("Dez/2024");
  expect(dec).not.toHaveTextContent("Abr/2025");
  expect(dec.querySelectorAll(".operation-series__point")).toHaveLength(1);

  await user.click(
    screen.getAllByRole("button", { name: "Ver tabela da série →" })[0]!,
  );
  const table = await screen.findByRole("table", {
    name: "Série mensal de DEC simplificado",
  });
  expect(
    within(table).getByRole("row", { name: /Jan\/2025/ }),
  ).toHaveTextContent("0");
  expect(
    within(table).getByRole("row", { name: /Fev\/2025/ }),
  ).toHaveTextContent("Indisponível");
  expect(
    within(table).getByRole("row", { name: /Mar\/2025/ }),
  ).toHaveTextContent("Indisponível");
  expect(
    within(table).getByRole("row", { name: /Mar\/2025/ }),
  ).toHaveTextContent("0 · inválida");
  expect(
    within(table).queryByRole("row", { name: /Dez\/2024|Abr\/2025/ }),
  ).not.toBeInTheDocument();
});
