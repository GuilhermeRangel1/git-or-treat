import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import UC360PeriodForm from "./UC360PeriodForm";
describe("UC360PeriodForm", () => {
  it("aplica mês e ano e rejeita intervalo invertido", () => {
    const onApply = vi.fn();
    render(
      <UC360PeriodForm
        appliedStart="2025-01"
        appliedEnd="2025-02"
        period={{ start: "2025-01", end: "2025-02", granularity: "month" }}
        onApply={onApply}
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: "Ajustar filtros" }));
    fireEvent.change(screen.getByLabelText("Ano inicial"), {
      target: { value: "2026" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Aplicar período" }));
    expect(screen.getByRole("alert")).toHaveTextContent("início antes do fim");
    expect(onApply).not.toHaveBeenCalled();
    fireEvent.change(screen.getByLabelText("Ano inicial"), {
      target: { value: "2024" },
    });
    fireEvent.change(screen.getByLabelText("Mês inicial"), {
      target: { value: "11" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Aplicar período" }));
    expect(onApply).toHaveBeenCalledWith("2024-11", "2025-02");
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });
});
