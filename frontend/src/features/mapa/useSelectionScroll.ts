import { useEffect, useRef, type RefObject } from "react";
import { prefersReducedMotion } from "./map-view";

export function scrollToElement(
  element: HTMLElement | null,
  block: ScrollLogicalPosition = "start",
) {
  element?.scrollIntoView?.({
    behavior: prefersReducedMotion() ? "auto" : "smooth",
    block,
  });
}

/**
 * Leva a página ao lugar certo quando a seleção muda:
 * - ao escolher um município, até o painel de detalhe, mas só depois que o
 *   conteúdo terminou de carregar. Rolar antes deixava o painel fora do lugar,
 *   porque o aviso de carregamento some e os bairros entram depois;
 * - ao limpar a seleção, de volta ao início da área do mapa, depois que o
 *   painel saiu e a página encolheu.
 * Um link que já abre com município selecionado não rola sozinho.
 */
export function useSelectionScroll({
  selectedCode,
  panelReady,
  panelRef,
  mapSectionRef,
}: {
  selectedCode: string;
  panelReady: boolean;
  panelRef: RefObject<HTMLElement | null>;
  mapSectionRef: RefObject<HTMLElement | null>;
}) {
  const lastCode = useRef(selectedCode);
  const pending = useRef<"panel" | "map" | null>(null);

  useEffect(() => {
    if (lastCode.current === selectedCode) return;
    lastCode.current = selectedCode;
    pending.current = selectedCode ? "panel" : "map";
  }, [selectedCode]);

  useEffect(() => {
    const target = pending.current;
    if (!target) return;
    if (target === "map") {
      pending.current = null;
      scrollToElement(mapSectionRef.current, "start");
      return;
    }
    if (!panelReady) return;
    pending.current = null;
    const panel = panelRef.current;
    if (!panel) return;
    // Painel que cabe na tela fica centralizado; o mais alto começa no topo.
    const fits =
      panel.getBoundingClientRect().height <= window.innerHeight - 32;
    scrollToElement(panel, fits ? "center" : "start");
  }, [selectedCode, panelReady, panelRef, mapSectionRef]);
}
