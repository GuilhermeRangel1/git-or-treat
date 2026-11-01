import { describe, expect, it } from "vitest";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import FilterBar from "./FilterBar";
import { usePanoramaFilters } from "./usePanoramaFilters";

function Filters() {
  const { filters, setFilters, hasActiveFilters, errors } =
    usePanoramaFilters();
  return (
    <FilterBar
      filters={filters}
      onApply={setFilters}
      hasActiveFilters={hasActiveFilters}
      errors={errors}
    />
  );
}

describe("FilterBar", () => {
  it("mostra opções Gold aplicadas sem classificá-las como inválidas", () => {
    render(
      <MemoryRouter>
        <FilterBar
          filters={{
            periodo: "2026-06",
            comparacao: "anterior",
            municipio: "Jaboatão dos Guararapes",
            classe: "Poder Público",
          }}
          onApply={() => {}}
          hasActiveFilters
          availableOptions={{
            competencias: ["2026-06"],
            municipios: ["Jaboatão dos Guararapes"],
            classes: ["Poder Público"],
          }}
        />
      </MemoryRouter>,
    );

    expect(
      screen.getByText("Jaboatão dos Guararapes", { selector: "dd" }),
    ).toBeVisible();
    expect(screen.getByText("Poder Público", { selector: "dd" })).toBeVisible();
    expect(screen.queryByText("Município inválido")).not.toBeInTheDocument();
    expect(screen.queryByText("Classe inválida")).not.toBeInTheDocument();
  });

  it("mantém alterações como rascunho até aplicar e cancela sem alterar a URL", async () => {
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
    await user.click(toggle);
    const panel = screen.getByRole("dialog", { name: "Ajustar filtros" });
    await user.selectOptions(
      within(panel).getByLabelText("Município"),
      "Recife",
    );
    expect(
      screen.getByText("Todos os municípios", { selector: "dd" }),
    ).toBeVisible();
    await user.click(within(panel).getByRole("button", { name: "Cancelar" }));
    expect(
      screen.getByText("Todos os municípios", { selector: "dd" }),
    ).toBeVisible();
    await user.click(toggle);
    const reopened = screen.getByRole("dialog", { name: "Ajustar filtros" });
    await user.selectOptions(
      within(reopened).getByLabelText("Município"),
      "Recife",
    );
    await user.click(
      within(reopened).getByRole("button", { name: "Aplicar filtros" }),
    );
    expect(screen.getByText("Recife", { selector: "dd" })).toBeVisible();
  });

  it("descarta alterações ao pressionar Escape e devolve foco ao acionador", async () => {
    const user = userEvent.setup();
    render(
      <MemoryRouter>
        <Filters />
      </MemoryRouter>,
    );
    const toggle = screen.getByRole("button", { name: "Ajustar filtros" });
    await user.click(toggle);
    const panel = screen.getByRole("dialog", { name: "Ajustar filtros" });
    await user.selectOptions(
      within(panel).getByLabelText("Município"),
      "Recife",
    );
    await user.keyboard("{Escape}");
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(
      screen.getByText("Todos os municípios", { selector: "dd" }),
    ).toBeVisible();
    expect(toggle).toHaveFocus();
  });

  it("limpa o rascunho sem gravar até que filtros sejam aplicados", async () => {
    const user = userEvent.setup();
    render(
      <MemoryRouter initialEntries={["/?municipio=Recife"]}>
        <Filters />
      </MemoryRouter>,
    );
    const toggle = screen.getByRole("button", { name: "Ajustar filtros" });
    await user.click(toggle);
    const panel = screen.getByRole("dialog", { name: "Ajustar filtros" });
    await user.selectOptions(
      within(panel).getByLabelText("Município"),
      "Recife",
    );
    await user.click(
      within(panel).getByRole("button", { name: "Limpar filtros" }),
    );
    expect(within(panel).getByLabelText("Município")).toHaveValue("todos");
    expect(screen.getByText("Recife", { selector: "dd" })).toBeVisible();
    await user.selectOptions(
      within(panel).getByLabelText("Comparar com"),
      "nenhuma",
    );
    await user.click(
      within(panel).getByRole("button", { name: "Aplicar filtros" }),
    );
    expect(
      screen.getByText("Sem comparação", { selector: "dd" }),
    ).toBeVisible();
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
    expect(
      screen.getByRole("combobox", { name: "Comparar com" }),
    ).toHaveAttribute("aria-invalid", "true");
  });
});
