import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, it, vi } from "vitest";
import MunicipalityMap from "./MunicipalityMap";

afterEach(() => vi.unstubAllGlobals());

function renderMap(selectedCode: string, onClearSelection?: () => void) {
  // Sem a malha, só o cabeçalho e os botões do cartão são exercitados.
  vi.stubGlobal(
    "fetch",
    vi.fn(() => Promise.reject(new Error("sem malha"))),
  );
  return render(
    <MunicipalityMap
      items={[]}
      layer="revenue"
      selectedCode={selectedCode}
      partialCodes={new Set()}
      onSelect={() => {}}
      onClearSelection={onClearSelection}
    />,
  );
}

it("mostra 'Limpar seleção' só com município selecionado e a aciona", async () => {
  const user = userEvent.setup();
  const onClearSelection = vi.fn();
  const { unmount } = renderMap("2607901", onClearSelection);

  await user.click(screen.getByRole("button", { name: "Limpar seleção" }));
  expect(onClearSelection).toHaveBeenCalledTimes(1);
  expect(screen.getByRole("button", { name: "Enquadrar RMR" })).toBeVisible();
  unmount();

  renderMap("", onClearSelection);
  expect(
    screen.queryByRole("button", { name: "Limpar seleção" }),
  ).not.toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Enquadrar RMR" })).toBeVisible();
});
