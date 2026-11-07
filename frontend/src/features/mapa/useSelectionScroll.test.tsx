import { renderHook } from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { useSelectionScroll } from "./useSelectionScroll";

type Props = Parameters<typeof useSelectionScroll>[0];

function setup(initial: { selectedCode: string; panelHeight?: number }) {
  const panel = {
    scrollIntoView: vi.fn(),
    getBoundingClientRect: () => ({ height: initial.panelHeight ?? 300 }),
  };
  const section = { scrollIntoView: vi.fn() };
  const refs = {
    panelRef: { current: panel as unknown as HTMLElement },
    mapSectionRef: { current: section as unknown as HTMLElement },
  };
  const hook = renderHook((props: Props) => useSelectionScroll(props), {
    initialProps: {
      selectedCode: initial.selectedCode,
      panelReady: initial.selectedCode !== "",
      ...refs,
    },
  });
  const update = (selectedCode: string, panelReady: boolean) =>
    hook.rerender({ selectedCode, panelReady, ...refs });
  return { panel, section, update };
}

beforeEach(() => {
  Object.defineProperty(window, "innerHeight", {
    value: 800,
    configurable: true,
  });
});
afterEach(() => vi.unstubAllGlobals());

it("não rola quando a página já abre com um município selecionado", () => {
  const { panel, section } = setup({ selectedCode: "2607901" });
  expect(panel.scrollIntoView).not.toHaveBeenCalled();
  expect(section.scrollIntoView).not.toHaveBeenCalled();
});

it("espera o detalhe terminar de carregar antes de rolar até o painel", () => {
  const { panel, update } = setup({ selectedCode: "" });

  update("2607901", false); // escolheu, mas o detalhe ainda carrega
  expect(panel.scrollIntoView).not.toHaveBeenCalled();

  update("2607901", true); // detalhe chegou: agora a altura é a final
  expect(panel.scrollIntoView).toHaveBeenCalledTimes(1);

  update("2607901", false); // uma nova busca em segundo plano não rola de novo
  update("2607901", true);
  expect(panel.scrollIntoView).toHaveBeenCalledTimes(1);
});

it("centraliza o painel que cabe na tela", () => {
  const { panel, update } = setup({ selectedCode: "", panelHeight: 400 });
  update("2607901", true);
  expect(panel.scrollIntoView).toHaveBeenCalledWith({
    behavior: "smooth",
    block: "center",
  });
});

it("começa pelo topo do painel quando ele é mais alto que a tela", () => {
  const { panel, update } = setup({ selectedCode: "", panelHeight: 1500 });
  update("2607901", true);
  expect(panel.scrollIntoView).toHaveBeenCalledWith({
    behavior: "smooth",
    block: "start",
  });
});

it("ao limpar a seleção, volta ao início da área do mapa", () => {
  const { panel, section, update } = setup({ selectedCode: "2607901" });
  update("", false);

  expect(section.scrollIntoView).toHaveBeenCalledTimes(1);
  expect(section.scrollIntoView).toHaveBeenCalledWith({
    behavior: "smooth",
    block: "start",
  });
  expect(panel.scrollIntoView).not.toHaveBeenCalled();
});

it("rola de novo ao trocar de um município para outro", () => {
  const { panel, update } = setup({ selectedCode: "1" });
  update("2", true);
  expect(panel.scrollIntoView).toHaveBeenCalledTimes(1);
});

it("respeita a preferência por menos movimento", () => {
  vi.stubGlobal(
    "matchMedia",
    vi.fn(() => ({ matches: true })),
  );
  const { panel, update } = setup({ selectedCode: "" });
  update("2607901", true);
  expect(panel.scrollIntoView).toHaveBeenCalledWith({
    behavior: "auto",
    block: "center",
  });
});
