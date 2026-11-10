import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, it, vi } from "vitest";
import RevenueInvestigation from "./RevenueInvestigation";
import type { RevenueEnvelope } from "./contract";

it("prioriza a perda de volume e explora o recorte com os mesmos efeitos publicados", async () => {
  const onExplore = vi.fn();
  const onViewDiagnosis = vi.fn();
  const data = {
    data: {
      window_decomposition: {
        windows: ["2022-07", "2023-06", "2025-07", "2026-06"],
      },
      window_breakdown: [
        {
          key: "a",
          label: "Município A",
          filters: { municipio: "A" },
          decomposition: {
            status: "available",
            components: { volume: 10, preco: 20 },
            total_change_brl: 30,
            change_percent: null,
            limitations: [],
          },
        },
        {
          key: "b",
          label: "Município B",
          filters: { municipio: "B" },
          decomposition: {
            status: "partial",
            components: { volume: -80, preco: 50 },
            total_change_brl: -30,
            change_percent: null,
            limitations: ["Base parcial."],
          },
        },
      ],
    },
  } as unknown as RevenueEnvelope;
  render(
    <RevenueInvestigation
      envelope={data}
      groupBy="municipio"
      onGroupByChange={() => {}}
      onExplore={onExplore}
      onViewDiagnosis={onViewDiagnosis}
    />,
  );
  const buttons = screen.getAllByRole("button", { name: /Explorar Município/ });
  expect(buttons[0]).toHaveAccessibleName("Explorar Município B");
  await userEvent.click(buttons[0]);
  expect(onExplore).toHaveBeenCalledWith(
    expect.objectContaining({ filters: { municipio: "B" } }),
  );
  expect(screen.getByText(/Parcelas conhecidas/)).toBeVisible();
  await userEvent.click(
    screen.getByRole("button", { name: "Ver diagnóstico deste recorte" }),
  );
  expect(onViewDiagnosis).toHaveBeenCalledOnce();
  expect(screen.queryByText(/NaN|Infinity/)).not.toBeInTheDocument();
});
