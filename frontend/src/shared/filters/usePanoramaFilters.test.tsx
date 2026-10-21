import { describe, expect, it } from "vitest";
import { act, renderHook } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { usePanoramaFilters } from "./usePanoramaFilters";

describe("usePanoramaFilters", () => {
  it("carrega os valores padrão quando a URL não possui parâmetros", () => {
    const { result } = renderHook(() => usePanoramaFilters(), {
      wrapper: ({ children }) => (
        <MemoryRouter initialEntries={["/panorama"]}>{children}</MemoryRouter>
      ),
    });

    expect(result.current.filters).toEqual({
      periodo: "2024-04",
      comparacao: "anterior",
      municipio: "todos",
      classe: "todas",
    });
    expect(result.current.hasActiveFilters).toBe(false);
  });

  it("carrega os filtros a partir dos parâmetros de busca na URL", () => {
    const { result } = renderHook(() => usePanoramaFilters(), {
      wrapper: ({ children }) => (
        <MemoryRouter
          initialEntries={[
            "/panorama?periodo=2024-03&comparacao=ano_anterior&municipio=Recife&classe=Residencial",
          ]}
        >
          {children}
        </MemoryRouter>
      ),
    });

    expect(result.current.filters).toEqual({
      periodo: "2024-03",
      comparacao: "ano_anterior",
      municipio: "Recife",
      classe: "Residencial",
    });
    expect(result.current.hasActiveFilters).toBe(true);
  });

  it("atualiza o filtro e sincroniza com a URL", () => {
    const { result } = renderHook(() => usePanoramaFilters(), {
      wrapper: ({ children }) => (
        <MemoryRouter initialEntries={["/panorama"]}>{children}</MemoryRouter>
      ),
    });

    act(() => {
      result.current.setFilter("municipio", "Olinda");
    });

    expect(result.current.filters.municipio).toBe("Olinda");
    expect(result.current.hasActiveFilters).toBe(true);
  });

  it("reseta os filtros para o padrão", () => {
    const { result } = renderHook(() => usePanoramaFilters(), {
      wrapper: ({ children }) => (
        <MemoryRouter
          initialEntries={["/panorama?municipio=Olinda&classe=Comercial"]}
        >
          {children}
        </MemoryRouter>
      ),
    });

    expect(result.current.hasActiveFilters).toBe(true);

    act(() => {
      result.current.resetFilters();
    });

    expect(result.current.filters).toEqual({
      periodo: "2024-04",
      comparacao: "anterior",
      municipio: "todos",
      classe: "todas",
    });
    expect(result.current.hasActiveFilters).toBe(false);
  });
});
