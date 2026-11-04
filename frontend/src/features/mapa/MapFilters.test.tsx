import { expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import MapFilters from "./MapFilters";

it("matches the Panorama filter summary and applies published month, class and layer options", async () => {
  const user = userEvent.setup();
  const onApply = vi.fn();
  render(
    <MapFilters
      months={["2025-01", "2025-02", "2025-03"]}
      classes={["Residencial", "Comercial"]}
      searchValues={{
        competencia_inicio: "2025-02",
        competencia_fim: "2025-03",
        classe: "",
        municipio: "",
        camada: "revenue",
      }}
      onApply={onApply}
    />,
  );
  expect(screen.getByRole("region", { name: "Filtros do mapa" })).toHaveClass(
    "min-h-[92px]",
    "rounded-xl",
    "bg-surface",
    "px-4",
    "py-4",
  );
  expect(screen.getByText("Fev/2025")).toBeVisible();
  await user.click(screen.getByRole("button", { name: "Ajustar filtros" }));
  expect(screen.getByLabelText("Competência inicial")).toHaveClass(
    "bg-canvas",
    "text-sm",
  );
  await user.selectOptions(screen.getByLabelText("Classe"), "Comercial");
  await user.selectOptions(
    screen.getByLabelText("Camada"),
    "consumption_change",
  );
  await user.click(screen.getByRole("button", { name: "Aplicar filtros" }));
  expect(onApply).toHaveBeenCalledWith({
    competencia_inicio: "2025-02",
    competencia_fim: "2025-03",
    classe: "Comercial",
    municipio: "",
    camada: "consumption_change",
  });
});

it("keeps draft filters unapplied on cancel and restores focus after Escape", async () => {
  const user = userEvent.setup();
  const onApply = vi.fn();
  render(
    <MapFilters
      months={["2025-01", "2025-02"]}
      classes={["Residencial", "Comercial"]}
      searchValues={{
        competencia_inicio: "2025-01",
        competencia_fim: "2025-02",
        classe: "Residencial",
        municipio: "2611606",
        camada: "revenue",
      }}
      onApply={onApply}
    />,
  );
  const trigger = screen.getByRole("button", { name: "Ajustar filtros" });
  await user.click(trigger);
  await user.selectOptions(screen.getByLabelText("Classe"), "Comercial");
  await user.click(screen.getByRole("button", { name: "Cancelar" }));
  expect(onApply).not.toHaveBeenCalled();
  await user.click(trigger);
  await user.keyboard("{Escape}");
  expect(onApply).not.toHaveBeenCalled();
  expect(trigger).toHaveFocus();
});

it("clears all draft filters like Panorama and waits for Apply", async () => {
  const user = userEvent.setup();
  const onApply = vi.fn();
  render(
    <MapFilters
      months={["2025-01", "2025-07"]}
      classes={["Residencial"]}
      searchValues={{
        competencia_inicio: "2025-07",
        competencia_fim: "2025-07",
        classe: "Residencial",
        municipio: "2611606",
        camada: "revenue_change",
      }}
      onApply={onApply}
    />,
  );
  await user.click(screen.getByRole("button", { name: "Ajustar filtros" }));
  await user.click(screen.getByRole("button", { name: "Limpar filtros" }));
  expect(onApply).not.toHaveBeenCalled();
  expect(screen.getByLabelText("Competência inicial")).toHaveValue("2025-01");
  expect(screen.getByLabelText("Competência final")).toHaveValue("2025-07");
  expect(screen.getByLabelText("Classe")).toHaveValue("");
  expect(screen.getByLabelText("Camada")).toHaveValue("revenue");
  await user.click(screen.getByRole("button", { name: "Aplicar filtros" }));
  expect(onApply).toHaveBeenCalledWith({
    competencia_inicio: "2025-01",
    competencia_fim: "2025-07",
    classe: "",
    municipio: "",
    camada: "revenue",
  });
});

it("shows clear when only a municipality is selected and resets it", async () => {
  const user = userEvent.setup();
  const onApply = vi.fn();
  render(
    <MapFilters
      months={["2025-01", "2025-02"]}
      classes={[]}
      searchValues={{
        competencia_inicio: "2025-01",
        competencia_fim: "2025-02",
        municipio: "2611606",
        camada: "revenue",
      }}
      onApply={onApply}
    />,
  );
  await user.click(screen.getByRole("button", { name: "Ajustar filtros" }));
  await user.click(screen.getByRole("button", { name: "Limpar filtros" }));
  expect(onApply).not.toHaveBeenCalled();
  await user.click(screen.getByRole("button", { name: "Aplicar filtros" }));
  expect(onApply).toHaveBeenCalledWith({
    competencia_inicio: "2025-01",
    competencia_fim: "2025-02",
    classe: "",
    municipio: "",
    camada: "revenue",
  });
});

it("does not apply an empty month by falling back to the latest publication", async () => {
  const user = userEvent.setup();
  const onApply = vi.fn();
  render(
    <MapFilters
      months={["2025-01", "2025-02"]}
      classes={[]}
      searchValues={{
        competencia_inicio: "",
        competencia_fim: "2025-02",
        camada: "revenue",
      }}
      onApply={onApply}
    />,
  );
  await user.click(screen.getByRole("button", { name: "Ajustar filtros" }));
  expect(screen.getByLabelText("Competência inicial")).toHaveValue("");
  expect(
    screen.getByRole("button", { name: "Aplicar filtros" }),
  ).toBeDisabled();
  expect(onApply).not.toHaveBeenCalled();
});
