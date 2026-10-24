import { describe, expect, it } from "vitest";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import FilterBar from "./FilterBar";
import { usePanoramaFilters } from "./usePanoramaFilters";

function Filters() {
  const { filters, setFilter, resetFilters, hasActiveFilters, errors } =
    usePanoramaFilters();
  return (
    <FilterBar
      filters={filters}
      onFilterChange={setFilter}
      onReset={resetFilters}
      hasActiveFilters={hasActiveFilters}
      errors={errors}
    />
  );
}

describe("FilterBar", () => {
  it("mostra o resumo compacto e abre os ajustes sob demanda", async () => {
    const user = userEvent.setup();
    render(
      <MemoryRouter>
        <Filters />
      </MemoryRouter>,
    );
    expect(screen.getByText("Abr/2024")).toBeVisible();
    expect(screen.getByText("Mar/2024")).toBeVisible();
    expect(screen.queryByRole("combobox")).not.toBeInTheDocument();
    const toggle = screen.getByRole("button", { name: "Ajustar filtros" });
    expect(toggle).toHaveAttribute("aria-expanded", "false");
    await user.click(toggle);
    const panel = screen.getByRole("region", {
      name: "Ajustar recorte do Panorama",
    });
    await user.selectOptions(
      within(panel).getByLabelText("Município"),
      "Recife",
    );
    expect(screen.getByText("Recife", { selector: "dd" })).toBeVisible();
    await user.click(
      within(panel).getByRole("button", { name: "Limpar filtros" }),
    );
    expect(within(panel).getByLabelText("Município")).toHaveValue("todos");
    await user.selectOptions(
      within(panel).getByLabelText("Comparação"),
      "nenhuma",
    );
    expect(
      screen.getByText("Sem comparação", { selector: "dd" }),
    ).toBeVisible();
    await user.keyboard("{Escape}");
    expect(screen.queryByRole("combobox")).not.toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Ajustar filtros" }),
    ).toHaveFocus();
  });
  it("abre valores inválidos para correção sem ocultar a validação", () => {
    render(
      <MemoryRouter initialEntries={["/?comparacao=bad"]}>
        <Filters />
      </MemoryRouter>,
    );
    expect(
      screen.getByText("Comparação inválida", { selector: "dd" }),
    ).toBeVisible();
    expect(screen.getByLabelText("Comparação")).toHaveAttribute(
      "aria-invalid",
      "true",
    );
  });
});
