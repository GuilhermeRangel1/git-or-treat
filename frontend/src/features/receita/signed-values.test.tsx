import { render, screen } from "@testing-library/react";
import { expect, it } from "vitest";
import RevenueDecomposition from "./RevenueDecomposition";
import type { RevenueEnvelope } from "./contract";

it("distingue sinais, zero e ausência na decomposição", () => {
  const envelope = {
    data: {
      window_decomposition: {
        status: "available",
        windows: [],
        incomplete_groups: 0,
        group_count: 1,
        components: { volume: -10, preco: 20, interacao: 0 },
        total_change_brl: 10,
        limitations: [],
      },
      price_volume: {},
      comparison: {},
    },
  } as unknown as RevenueEnvelope;
  render(<RevenueDecomposition envelope={envelope} />);
  expect(screen.getByText(/−R\$\s*10,00/)).toHaveClass("text-danger");
  expect(screen.getByText(/\+R\$\s*20,00/)).toHaveClass("text-success");
  expect(screen.getByText(/R\$\s*0,00/)).toHaveClass("text-content");
  expect(screen.getAllByText("Indisponível")[0]).toHaveClass("text-muted");
});
