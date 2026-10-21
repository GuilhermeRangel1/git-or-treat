import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import TestProviders from "../../shared/test/TestProviders";
import PanoramaPage from "./PanoramaPage";
import { calculateSyntheticPanorama } from "../../shared/analytics/syntheticData";

describe("PanoramaPage (WEB-01)", () => {
  beforeEach(() => {
    localStorage.clear();
    vi.stubGlobal(
      "matchMedia",
      vi.fn().mockReturnValue({
        matches: false,
        addEventListener: vi.fn(),
        removeEventListener: vi.fn(),
      }),
    );
    vi.stubGlobal(
      "fetch",
      vi.fn().mockImplementation(async (url: string) => {
        const params = new URL(url, "http://localhost:5173").searchParams;
        const data = calculateSyntheticPanorama({
          periodo: params.get("competencia")!,
          comparacao: params.get("comparacao") as
            "anterior" | "ano_anterior" | "nenhuma",
          municipio: params.get("municipio")!,
          classe: params.get("classe")!,
        });
        return new Response(JSON.stringify({ data }));
      }),
    );
  });

  it("mostra falha da API sem substituir por números locais e permite tentar novamente", async () => {
    vi.mocked(fetch).mockRejectedValueOnce(new Error("offline"));
    render(
      <TestProviders>
        <MemoryRouter>
          <PanoramaPage />
        </MemoryRouter>
      </TestProviders>,
    );
    expect(
      await screen.findByText("Erro na consulta dos indicadores"),
    ).toBeVisible();
    expect(screen.queryByText(/76\.500,00/)).not.toBeInTheDocument();
    await userEvent.click(
      screen.getByRole("button", { name: /Tentar novamente/i }),
    );
    expect(await screen.findByText(/76\.500,00/)).toBeVisible();
  });

  it("trata comparação nula recebida da API sem quebrar os cartões", async () => {
    const data = calculateSyntheticPanorama({
      periodo: "2024-04",
      comparacao: "nenhuma",
      municipio: "todos",
      classe: "todas",
    });
    for (const metric of Object.values(data.metricas)) {
      metric.valorAnterior = null;
      metric.variacaoPercentual = null;
      metric.variacaoAbsoluta = null;
    }
    vi.mocked(fetch).mockResolvedValueOnce(
      new Response(JSON.stringify({ data })),
    );
    render(
      <TestProviders>
        <MemoryRouter initialEntries={["/panorama?comparacao=nenhuma"]}>
          <PanoramaPage />
        </MemoryRouter>
      </TestProviders>,
    );
    expect(await screen.findByText(/76\.500,00/)).toBeVisible();
    expect(screen.getAllByText("Sem comparação selecionada")).toHaveLength(8);
  });

  it("rejeita resposta incompleta da API", async () => {
    vi.mocked(fetch).mockResolvedValueOnce(
      new Response(JSON.stringify({ data: { metricas: {} } })),
    );
    render(
      <TestProviders>
        <MemoryRouter>
          <PanoramaPage />
        </MemoryRouter>
      </TestProviders>,
    );
    expect(
      await screen.findByText("Erro na consulta dos indicadores"),
    ).toBeVisible();
  });

  it("renderiza o cabeçalho e os indicadores com os números da base sintética (benchmark)", async () => {
    render(
      <TestProviders>
        <MemoryRouter initialEntries={["/panorama"]}>
          <PanoramaPage />
        </MemoryRouter>
      </TestProviders>,
    );

    // Título e subtítulo preservados
    expect(
      screen.getByRole("heading", {
        level: 1,
        name: "Sua rede, em perspectiva.",
      }),
    ).toBeVisible();

    // Aguarda o carregamento dos dados e verifica os valores do benchmark (PRD WEB-01)
    expect(await screen.findByText(/76\.500,00/)).toBeVisible();
    expect(await screen.findByText(/74\.200,00/)).toBeVisible();
    expect(screen.getAllByText(/90\.000 kWh/).length).toBeGreaterThan(0);
    expect(screen.getByText(/1\.248 UCs/)).toBeVisible();
    expect(screen.getByText(/0,85/)).toBeVisible();

    // Distinção faturado vs pago
    expect(screen.getAllByText("Faturado").length).toBeGreaterThan(0);
    expect(screen.getByText("Arrecadado / Pago")).toBeVisible();
    expect(screen.getByText("Físico / Consumido")).toBeVisible();

    // Variações percentuais
    expect(screen.getByText("-4,38%")).toBeVisible();
    expect(screen.getByText("-5,48%")).toBeVisible();
    expect(screen.getAllByText("-10,00%").length).toBeGreaterThan(0);
  });

  it("alterar o filtro de município modifica os dados exibidos", async () => {
    const user = userEvent.setup();
    render(
      <TestProviders>
        <MemoryRouter initialEntries={["/panorama"]}>
          <PanoramaPage />
        </MemoryRouter>
      </TestProviders>,
    );

    // Aguarda carga inicial
    expect(await screen.findByText(/76\.500,00/)).toBeVisible();

    const municipioSelect = screen.getByLabelText("Município");
    await user.selectOptions(municipioSelect, "Recife");

    // Recife soma R$ 38.000 e 620 UCs
    expect(await screen.findByText(/38\.000,00/)).toBeVisible();
    expect(screen.getByText(/620 UCs/)).toBeVisible();
  });

  it("exibe aviso de período incompleto na competência 2024-05", async () => {
    render(
      <TestProviders>
        <MemoryRouter initialEntries={["/panorama?periodo=2024-05"]}>
          <PanoramaPage />
        </MemoryRouter>
      </TestProviders>,
    );

    expect(
      await screen.findByText(
        /Competência 2024-05 em aberto · Dados preliminares/i,
      ),
    ).toBeVisible();
  });

  it("exibe estado vazio legítimo quando recorte não possui registros", async () => {
    render(
      <TestProviders>
        <MemoryRouter initialEntries={["/panorama?classe=Rural"]}>
          <PanoramaPage />
        </MemoryRouter>
      </TestProviders>,
    );

    expect(
      await screen.findByText("Nenhum registro para o recorte selecionado"),
    ).toBeVisible();
    expect(
      screen.getByRole("button", { name: "Restaurar filtros padrão" }),
    ).toBeVisible();
  });

  it("permite abrir a definição e fórmula de uma métrica", async () => {
    const user = userEvent.setup();
    render(
      <TestProviders>
        <MemoryRouter initialEntries={["/panorama"]}>
          <PanoramaPage />
        </MemoryRouter>
      </TestProviders>,
    );

    // Aguarda carga
    await screen.findByText(/76\.500,00/);

    const infoButton = screen.getByRole("button", {
      name: "Ver detalhes e fórmula de Receita Faturada",
    });
    await user.click(infoButton);

    expect(
      screen.getByText(
        "Total monetário faturado no ciclo de faturamento da competência.",
      ),
    ).toBeVisible();
    expect(screen.getByText("Σ(faturas_emitidas.valor_total)")).toBeVisible();
  });

  it("alterna entre visualização gráfica e tabela na série histórica", async () => {
    const user = userEvent.setup();
    render(
      <TestProviders>
        <MemoryRouter initialEntries={["/panorama"]}>
          <PanoramaPage />
        </MemoryRouter>
      </TestProviders>,
    );

    // Aguarda carga
    await screen.findByText(/76\.500,00/);

    const toggleTableBtn = screen.getByRole("button", { name: "Ver Tabela" });
    await user.click(toggleTableBtn);

    expect(screen.getByRole("table")).toBeVisible();
    expect(screen.getByRole("button", { name: "Ver Gráfico" })).toBeVisible();
  });
});
