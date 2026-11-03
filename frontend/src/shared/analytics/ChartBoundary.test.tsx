import { expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import ChartBoundary from "./ChartBoundary";
it("falha do renderer conserva as alternativas fora do gráfico", () => {
  const log = vi.spyOn(console, "error").mockImplementation(() => {});
  function Broken(): never {
    throw new Error("renderer indisponível");
  }
  try {
    render(
      <section>
        <ChartBoundary>
          <Broken />
        </ChartBoundary>
        <p>Tabela disponível</p>
      </section>,
    );
    expect(screen.getByRole("status")).toHaveTextContent(
      "Os valores continuam disponíveis",
    );
    expect(screen.getByText("Tabela disponível")).toBeVisible();
  } finally {
    log.mockRestore();
  }
});
