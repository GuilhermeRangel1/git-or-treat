import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import UC360PeriodForm from "./UC360PeriodForm";

function renderForm(onApply = vi.fn()) {
  render(
    <UC360PeriodForm
      appliedStart="2025-01"
      appliedEnd="2025-02"
      period={{ start: "2025-01", end: "2025-02", granularity: "month" }}
      onApply={onApply}
    />,
  );
  return onApply;
}

describe("UC360PeriodForm", () => {
  it.each([
    ["0000-01", "2025-02", true, false],
    ["2025-13", "2025-02", true, false],
    ["2025-01", "0000-01", false, true],
    ["2025-01", "2024-12", true, true],
  ])(
    "associa o erro aos campos para o intervalo %s–%s",
    (start, end, invalidStart, invalidEnd) => {
      const onApply = renderForm();
      const startInput = screen.getByLabelText("Competência inicial");
      const endInput = screen.getByLabelText("Competência final");
      fireEvent.change(startInput, { target: { value: start } });
      fireEvent.change(endInput, { target: { value: end } });
      fireEvent.submit(
        screen.getByRole("form", { name: "Período da consulta" }),
      );

      expect(onApply).not.toHaveBeenCalled();
      expect(
        screen.getByText("Período aplicado:").parentElement,
      ).toHaveTextContent("01/2025 a 02/2025");
      expect(startInput).toHaveAttribute("id");
      expect(endInput).toHaveAttribute("id");
      const alert = screen.getByRole("alert");
      if (invalidStart) {
        expect(startInput).toHaveAttribute("aria-invalid", "true");
        expect(startInput).toHaveAttribute("aria-describedby", alert.id);
      } else {
        expect(startInput).not.toHaveAttribute("aria-invalid", "true");
        expect(startInput).not.toHaveAttribute("aria-describedby");
      }
      if (invalidEnd) {
        expect(endInput).toHaveAttribute("aria-invalid", "true");
        expect(endInput).toHaveAttribute("aria-describedby", alert.id);
      } else {
        expect(endInput).not.toHaveAttribute("aria-invalid", "true");
        expect(endInput).not.toHaveAttribute("aria-describedby");
      }
      expect(document.activeElement).toBe(invalidStart ? startInput : endInput);
    },
  );

  it("aplica competências válidas e mantém o texto de período", () => {
    const onApply = renderForm();
    const startInput = screen.getByLabelText("Competência inicial");
    const endInput = screen.getByLabelText("Competência final");
    fireEvent.change(startInput, { target: { value: "2024-11" } });
    fireEvent.change(endInput, { target: { value: "2025-03" } });
    fireEvent.submit(screen.getByRole("form", { name: "Período da consulta" }));

    expect(onApply).toHaveBeenCalledWith("2024-11", "2025-03");
    expect(startInput).not.toHaveAttribute("aria-invalid", "true");
    expect(endInput).not.toHaveAttribute("aria-invalid", "true");
  });

  it("limpa erro associado quando o rascunho é corrigido", () => {
    const onApply = renderForm();
    const startInput = screen.getByLabelText("Competência inicial");
    const endInput = screen.getByLabelText("Competência final");
    fireEvent.change(startInput, { target: { value: "0000-01" } });
    fireEvent.submit(screen.getByRole("form", { name: "Período da consulta" }));
    expect(startInput).toHaveAttribute(
      "aria-describedby",
      screen.getByRole("alert").id,
    );

    fireEvent.change(startInput, { target: { value: "2024-12" } });
    fireEvent.change(endInput, { target: { value: "2025-03" } });
    fireEvent.submit(screen.getByRole("form", { name: "Período da consulta" }));

    expect(onApply).toHaveBeenCalledWith("2024-12", "2025-03");
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    expect(startInput).not.toHaveAttribute("aria-describedby");
    expect(endInput).not.toHaveAttribute("aria-describedby");
  });
});
