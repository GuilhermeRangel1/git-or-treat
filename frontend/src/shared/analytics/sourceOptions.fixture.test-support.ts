// Catálogo artificial das jornadas demonstrativas; nunca usado pelo produto.
export const sourceOptionsFixture = {
  data: {
    competencias: [
      "2024-02",
      "2024-03",
      "2024-04",
      "2024-05",
      "2025-01",
      "2025-02",
    ],
    municipio: ["Recife", "Olinda", "Jaboatão dos Guararapes"],
    bairro: ["Boa Viagem", "Centro"],
    classe: ["Residencial", "Comercial", "Industrial", "Rural"],
    alimentador: ["AL-01", "AL-02"],
    bairros: [
      { municipio: "Recife", bairro: "Boa Viagem" },
      { municipio: "Olinda", bairro: "Centro" },
    ],
  },
  source: {
    kind: "synthetic",
    version: "test-options-v1",
    is_demo: true,
    updated_at: "2026-10-21T00:00:00Z",
  },
  limitations: ["Catálogo artificial exclusivo dos testes."],
};
