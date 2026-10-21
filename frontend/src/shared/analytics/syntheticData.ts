import type {
  ComparisonType,
  MonthlyDataPoint,
  PanoramaData,
  PanoramaFilters,
} from "./types";

export interface SyntheticRecord {
  competencia: string;
  municipio: string;
  classe: string;
  receitaFaturada: number;
  receitaPaga: number;
  energiaConsumidaKwh: number;
  energiaFaturadaKwh: number;
  ucsAtivas: number;
  decHoras: number;
  fecVezes: number;
}

export const COMPETENCIAS_DISPONIVEIS = [
  {
    value: "2024-05",
    label: "2024-05 (Parcial em aberto)",
    isIncompleto: true,
  },
  {
    value: "2024-04",
    label: "2024-04 (Fechada · Referência)",
    isIncompleto: false,
  },
  { value: "2024-03", label: "2024-03 (Fechada)", isIncompleto: false },
  { value: "2024-02", label: "2024-02 (Fechada)", isIncompleto: false },
  { value: "2024-01", label: "2024-01 (Fechada)", isIncompleto: false },
  { value: "2023-12", label: "2023-12 (Fechada)", isIncompleto: false },
  { value: "2023-11", label: "2023-11 (Fechada)", isIncompleto: false },
  { value: "2023-10", label: "2023-10 (Fechada)", isIncompleto: false },
  { value: "2023-09", label: "2023-09 (Fechada)", isIncompleto: false },
  { value: "2023-08", label: "2023-08 (Fechada)", isIncompleto: false },
  { value: "2023-07", label: "2023-07 (Fechada)", isIncompleto: false },
  { value: "2023-06", label: "2023-06 (Fechada)", isIncompleto: false },
  { value: "2023-05", label: "2023-05 (Fechada)", isIncompleto: false },
  {
    value: "2023-04",
    label: "2023-04 (Fechada · Ano Anterior)",
    isIncompleto: false,
  },
];

export const MUNICIPIOS_DISPONIVEIS = [
  { value: "todos", label: "Todos os municípios" },
  { value: "Recife", label: "Recife" },
  { value: "Olinda", label: "Olinda" },
  { value: "Jaboatão dos Guararapes", label: "Jaboatão dos Guararapes" },
  { value: "São Lourenço da Mata", label: "São Lourenço da Mata (Base zero)" },
];

export const CLASSES_DISPONIVEIS = [
  { value: "todas", label: "Todas as classes" },
  { value: "Residencial", label: "Residencial" },
  { value: "Comercial", label: "Comercial" },
  { value: "Industrial", label: "Industrial" },
  { value: "Rural", label: "Rural (Sem dados na região)" },
  { value: "Poder Público", label: "Poder Público" },
];

// Base sintética granular reconciliada com os controles oficiais do protótipo
export const SYNTHETIC_DATABASE: SyntheticRecord[] = [
  // 2024-04 (Total: Faturado R$ 76.500 | Pago R$ 74.200 | Consumo 90.000 kWh | Faturado 90.000 kWh | UCs 1.248)
  // Recife (Total R$ 38.000 | 45.000 kWh | 620 UCs)
  {
    competencia: "2024-04",
    municipio: "Recife",
    classe: "Residencial",
    receitaFaturada: 21000,
    receitaPaga: 20300,
    energiaConsumidaKwh: 25000,
    energiaFaturadaKwh: 25000,
    ucsAtivas: 520,
    decHoras: 1.2,
    fecVezes: 0.8,
  },
  {
    competencia: "2024-04",
    municipio: "Recife",
    classe: "Comercial",
    receitaFaturada: 12000,
    receitaPaga: 11800,
    energiaConsumidaKwh: 14000,
    energiaFaturadaKwh: 14000,
    ucsAtivas: 80,
    decHoras: 1.15,
    fecVezes: 0.75,
  },
  {
    competencia: "2024-04",
    municipio: "Recife",
    classe: "Industrial",
    receitaFaturada: 5000,
    receitaPaga: 5000,
    energiaConsumidaKwh: 6000,
    energiaFaturadaKwh: 6000,
    ucsAtivas: 20,
    decHoras: 1.0,
    fecVezes: 0.6,
  },

  // Olinda (Total R$ 22.500 | 26.500 kWh | 370 UCs)
  {
    competencia: "2024-04",
    municipio: "Olinda",
    classe: "Residencial",
    receitaFaturada: 12500,
    receitaPaga: 12100,
    energiaConsumidaKwh: 14500,
    energiaFaturadaKwh: 14500,
    ucsAtivas: 310,
    decHoras: 1.45,
    fecVezes: 0.95,
  },
  {
    competencia: "2024-04",
    municipio: "Olinda",
    classe: "Comercial",
    receitaFaturada: 7000,
    receitaPaga: 6900,
    energiaConsumidaKwh: 8500,
    energiaFaturadaKwh: 8500,
    ucsAtivas: 50,
    decHoras: 1.4,
    fecVezes: 0.9,
  },
  {
    competencia: "2024-04",
    municipio: "Olinda",
    classe: "Industrial",
    receitaFaturada: 3000,
    receitaPaga: 3000,
    energiaConsumidaKwh: 3500,
    energiaFaturadaKwh: 3500,
    ucsAtivas: 10,
    decHoras: 1.3,
    fecVezes: 0.85,
  },

  // Jaboatão dos Guararapes (Total R$ 16.000 | 18.500 kWh | 258 UCs)
  {
    competencia: "2024-04",
    municipio: "Jaboatão dos Guararapes",
    classe: "Residencial",
    receitaFaturada: 8500,
    receitaPaga: 8200,
    energiaConsumidaKwh: 10000,
    energiaFaturadaKwh: 10000,
    ucsAtivas: 220,
    decHoras: 1.5,
    fecVezes: 0.95,
  },
  {
    competencia: "2024-04",
    municipio: "Jaboatão dos Guararapes",
    classe: "Comercial",
    receitaFaturada: 5500,
    receitaPaga: 5400,
    energiaConsumidaKwh: 6000,
    energiaFaturadaKwh: 6000,
    ucsAtivas: 30,
    decHoras: 1.42,
    fecVezes: 0.92,
  },
  {
    competencia: "2024-04",
    municipio: "Jaboatão dos Guararapes",
    classe: "Industrial",
    receitaFaturada: 2000,
    receitaPaga: 1500,
    energiaConsumidaKwh: 2500,
    energiaFaturadaKwh: 2500,
    ucsAtivas: 8,
    decHoras: 1.38,
    fecVezes: 0.9,
  },

  // 2024-03 (Total: Faturado R$ 80.000 | Pago R$ 78.500 | Consumo 100.000 kWh | Faturado 100.000 kWh | UCs 1.250)
  // Recife (Total R$ 39.800 | 50.000 kWh | 622 UCs)
  {
    competencia: "2024-03",
    municipio: "Recife",
    classe: "Residencial",
    receitaFaturada: 22800,
    receitaPaga: 22300,
    energiaConsumidaKwh: 29000,
    energiaFaturadaKwh: 29000,
    ucsAtivas: 522,
    decHoras: 1.3,
    fecVezes: 0.88,
  },
  {
    competencia: "2024-03",
    municipio: "Recife",
    classe: "Comercial",
    receitaFaturada: 12000,
    receitaPaga: 11900,
    energiaConsumidaKwh: 15000,
    energiaFaturadaKwh: 15000,
    ucsAtivas: 80,
    decHoras: 1.25,
    fecVezes: 0.8,
  },
  {
    competencia: "2024-03",
    municipio: "Recife",
    classe: "Industrial",
    receitaFaturada: 5000,
    receitaPaga: 5000,
    energiaConsumidaKwh: 6000,
    energiaFaturadaKwh: 6000,
    ucsAtivas: 20,
    decHoras: 1.1,
    fecVezes: 0.65,
  },

  // Olinda (Total R$ 23.400 | 29.500 kWh | 370 UCs)
  {
    competencia: "2024-03",
    municipio: "Olinda",
    classe: "Residencial",
    receitaFaturada: 13400,
    receitaPaga: 13100,
    energiaConsumidaKwh: 17000,
    energiaFaturadaKwh: 17000,
    ucsAtivas: 310,
    decHoras: 1.55,
    fecVezes: 1.05,
  },
  {
    competencia: "2024-03",
    municipio: "Olinda",
    classe: "Comercial",
    receitaFaturada: 7000,
    receitaPaga: 6900,
    energiaConsumidaKwh: 9000,
    energiaFaturadaKwh: 9000,
    ucsAtivas: 50,
    decHoras: 1.48,
    fecVezes: 0.98,
  },
  {
    competencia: "2024-03",
    municipio: "Olinda",
    classe: "Industrial",
    receitaFaturada: 3000,
    receitaPaga: 3000,
    energiaConsumidaKwh: 3500,
    energiaFaturadaKwh: 3500,
    ucsAtivas: 10,
    decHoras: 1.4,
    fecVezes: 0.9,
  },

  // Jaboatão dos Guararapes (Total R$ 16.800 | 20.500 kWh | 258 UCs)
  {
    competencia: "2024-03",
    municipio: "Jaboatão dos Guararapes",
    classe: "Residencial",
    receitaFaturada: 9300,
    receitaPaga: 8900,
    energiaConsumidaKwh: 11000,
    energiaFaturadaKwh: 11000,
    ucsAtivas: 220,
    decHoras: 1.6,
    fecVezes: 1.05,
  },
  {
    competencia: "2024-03",
    municipio: "Jaboatão dos Guararapes",
    classe: "Comercial",
    receitaFaturada: 5500,
    receitaPaga: 5400,
    energiaConsumidaKwh: 6500,
    energiaFaturadaKwh: 6500,
    ucsAtivas: 30,
    decHoras: 1.5,
    fecVezes: 1.0,
  },
  {
    competencia: "2024-03",
    municipio: "Jaboatão dos Guararapes",
    classe: "Industrial",
    receitaFaturada: 2000,
    receitaPaga: 2000,
    energiaConsumidaKwh: 3000,
    energiaFaturadaKwh: 3000,
    ucsAtivas: 8,
    decHoras: 1.45,
    fecVezes: 0.95,
  },

  // 2024-05 (Período em aberto/incompleto - Dados preliminares)
  {
    competencia: "2024-05",
    municipio: "Recife",
    classe: "Residencial",
    receitaFaturada: 14000,
    receitaPaga: 8000,
    energiaConsumidaKwh: 16000,
    energiaFaturadaKwh: 16000,
    ucsAtivas: 520,
    decHoras: 0.8,
    fecVezes: 0.4,
  },
  {
    competencia: "2024-05",
    municipio: "Recife",
    classe: "Comercial",
    receitaFaturada: 8000,
    receitaPaga: 5000,
    energiaConsumidaKwh: 9000,
    energiaFaturadaKwh: 9000,
    ucsAtivas: 80,
    decHoras: 0.7,
    fecVezes: 0.35,
  },
  {
    competencia: "2024-05",
    municipio: "Olinda",
    classe: "Residencial",
    receitaFaturada: 9000,
    receitaPaga: 4500,
    energiaConsumidaKwh: 10000,
    energiaFaturadaKwh: 10000,
    ucsAtivas: 310,
    decHoras: 0.9,
    fecVezes: 0.45,
  },

  // 2023-04 (Ano anterior homólogo para comparação anual: Total R$ 83.000 | 104.000 kWh | 1.252 UCs)
  {
    competencia: "2023-04",
    municipio: "Recife",
    classe: "Residencial",
    receitaFaturada: 24000,
    receitaPaga: 23600,
    energiaConsumidaKwh: 31000,
    energiaFaturadaKwh: 31000,
    ucsAtivas: 522,
    decHoras: 1.45,
    fecVezes: 0.98,
  },
  {
    competencia: "2023-04",
    municipio: "Recife",
    classe: "Comercial",
    receitaFaturada: 12500,
    receitaPaga: 12300,
    energiaConsumidaKwh: 16000,
    energiaFaturadaKwh: 16000,
    ucsAtivas: 80,
    decHoras: 1.35,
    fecVezes: 0.85,
  },
  {
    competencia: "2023-04",
    municipio: "Recife",
    classe: "Industrial",
    receitaFaturada: 5200,
    receitaPaga: 5200,
    energiaConsumidaKwh: 6500,
    energiaFaturadaKwh: 6500,
    ucsAtivas: 20,
    decHoras: 1.2,
    fecVezes: 0.7,
  },
  {
    competencia: "2023-04",
    municipio: "Olinda",
    classe: "Residencial",
    receitaFaturada: 14200,
    receitaPaga: 13900,
    energiaConsumidaKwh: 18000,
    energiaFaturadaKwh: 18000,
    ucsAtivas: 312,
    decHoras: 1.65,
    fecVezes: 1.15,
  },
  {
    competencia: "2023-04",
    municipio: "Olinda",
    classe: "Comercial",
    receitaFaturada: 7200,
    receitaPaga: 7000,
    energiaConsumidaKwh: 9200,
    energiaFaturadaKwh: 9200,
    ucsAtivas: 50,
    decHoras: 1.55,
    fecVezes: 1.05,
  },
  {
    competencia: "2023-04",
    municipio: "Olinda",
    classe: "Industrial",
    receitaFaturada: 3100,
    receitaPaga: 3100,
    energiaConsumidaKwh: 3700,
    energiaFaturadaKwh: 3700,
    ucsAtivas: 10,
    decHoras: 1.45,
    fecVezes: 0.95,
  },
  {
    competencia: "2023-04",
    municipio: "Jaboatão dos Guararapes",
    classe: "Residencial",
    receitaFaturada: 9600,
    receitaPaga: 9300,
    energiaConsumidaKwh: 11500,
    energiaFaturadaKwh: 11500,
    ucsAtivas: 220,
    decHoras: 1.7,
    fecVezes: 1.15,
  },
  {
    competencia: "2023-04",
    municipio: "Jaboatão dos Guararapes",
    classe: "Comercial",
    receitaFaturada: 5200,
    receitaPaga: 5100,
    energiaConsumidaKwh: 5900,
    energiaFaturadaKwh: 5900,
    ucsAtivas: 30,
    decHoras: 1.58,
    fecVezes: 1.08,
  },
  {
    competencia: "2023-04",
    municipio: "Jaboatão dos Guararapes",
    classe: "Industrial",
    receitaFaturada: 2000,
    receitaPaga: 2000,
    energiaConsumidaKwh: 2200,
    energiaFaturadaKwh: 2200,
    ucsAtivas: 8,
    decHoras: 1.5,
    fecVezes: 1.0,
  },

  // Histórico anterior para a série temporal (2023-05 a 2024-02 aproximados com perfil consistente)
  ...gerarHistoricoMensal(),
];

function gerarHistoricoMensal(): SyntheticRecord[] {
  const meses = [
    { comp: "2023-05", fat: 82500, pag: 81000, kwh: 103000 },
    { comp: "2023-06", fat: 81800, pag: 80200, kwh: 101500 },
    { comp: "2023-07", fat: 81200, pag: 79800, kwh: 100000 },
    { comp: "2023-08", fat: 82000, pag: 80600, kwh: 101000 },
    { comp: "2023-09", fat: 81500, pag: 80100, kwh: 99500 },
    { comp: "2023-10", fat: 82200, pag: 80900, kwh: 101200 },
    { comp: "2023-11", fat: 80900, pag: 79400, kwh: 98500 },
    { comp: "2023-12", fat: 83500, pag: 82100, kwh: 103500 },
    { comp: "2024-01", fat: 81000, pag: 79200, kwh: 101000 },
    { comp: "2024-02", fat: 80500, pag: 78900, kwh: 99800 },
  ];

  const records: SyntheticRecord[] = [];
  for (const item of meses) {
    // Distribuído 50% Recife, 30% Olinda, 20% Jaboatão
    records.push(
      {
        competencia: item.comp,
        municipio: "Recife",
        classe: "Residencial",
        receitaFaturada: item.fat * 0.3,
        receitaPaga: item.pag * 0.3,
        energiaConsumidaKwh: item.kwh * 0.3,
        energiaFaturadaKwh: item.kwh * 0.3,
        ucsAtivas: 522,
        decHoras: 1.35,
        fecVezes: 0.9,
      },
      {
        competencia: item.comp,
        municipio: "Recife",
        classe: "Comercial",
        receitaFaturada: item.fat * 0.15,
        receitaPaga: item.pag * 0.15,
        energiaConsumidaKwh: item.kwh * 0.15,
        energiaFaturadaKwh: item.kwh * 0.15,
        ucsAtivas: 80,
        decHoras: 1.25,
        fecVezes: 0.82,
      },
      {
        competencia: item.comp,
        municipio: "Recife",
        classe: "Industrial",
        receitaFaturada: item.fat * 0.05,
        receitaPaga: item.pag * 0.05,
        energiaConsumidaKwh: item.kwh * 0.05,
        energiaFaturadaKwh: item.kwh * 0.05,
        ucsAtivas: 20,
        decHoras: 1.15,
        fecVezes: 0.68,
      },
      {
        competencia: item.comp,
        municipio: "Olinda",
        classe: "Residencial",
        receitaFaturada: item.fat * 0.18,
        receitaPaga: item.pag * 0.18,
        energiaConsumidaKwh: item.kwh * 0.18,
        energiaFaturadaKwh: item.kwh * 0.18,
        ucsAtivas: 310,
        decHoras: 1.5,
        fecVezes: 1.0,
      },
      {
        competencia: item.comp,
        municipio: "Olinda",
        classe: "Comercial",
        receitaFaturada: item.fat * 0.09,
        receitaPaga: item.pag * 0.09,
        energiaConsumidaKwh: item.kwh * 0.09,
        energiaFaturadaKwh: item.kwh * 0.09,
        ucsAtivas: 50,
        decHoras: 1.45,
        fecVezes: 0.95,
      },
      {
        competencia: item.comp,
        municipio: "Olinda",
        classe: "Industrial",
        receitaFaturada: item.fat * 0.03,
        receitaPaga: item.pag * 0.03,
        energiaConsumidaKwh: item.kwh * 0.03,
        energiaFaturadaKwh: item.kwh * 0.03,
        ucsAtivas: 10,
        decHoras: 1.35,
        fecVezes: 0.88,
      },
      {
        competencia: item.comp,
        municipio: "Jaboatão dos Guararapes",
        classe: "Residencial",
        receitaFaturada: item.fat * 0.12,
        receitaPaga: item.pag * 0.12,
        energiaConsumidaKwh: item.kwh * 0.12,
        energiaFaturadaKwh: item.kwh * 0.12,
        ucsAtivas: 220,
        decHoras: 1.58,
        fecVezes: 1.02,
      },
      {
        competencia: item.comp,
        municipio: "Jaboatão dos Guararapes",
        classe: "Comercial",
        receitaFaturada: item.fat * 0.06,
        receitaPaga: item.pag * 0.06,
        energiaConsumidaKwh: item.kwh * 0.06,
        energiaFaturadaKwh: item.kwh * 0.06,
        ucsAtivas: 30,
        decHoras: 1.48,
        fecVezes: 0.96,
      },
      {
        competencia: item.comp,
        municipio: "Jaboatão dos Guararapes",
        classe: "Industrial",
        receitaFaturada: item.fat * 0.02,
        receitaPaga: item.pag * 0.02,
        energiaConsumidaKwh: item.kwh * 0.02,
        energiaFaturadaKwh: item.kwh * 0.02,
        ucsAtivas: 8,
        decHoras: 1.42,
        fecVezes: 0.92,
      },
    );
  }
  return records;
}

// Determina competência de comparação
export function getCompetenciaComparada(
  competencia: string,
  comparacao: ComparisonType,
): string | null {
  if (comparacao === "nenhuma") return null;
  const [anoStr, mesStr] = competencia.split("-");
  const ano = parseInt(anoStr, 10);
  const mes = parseInt(mesStr, 10);

  if (comparacao === "ano_anterior") {
    return `${ano - 1}-${String(mes).padStart(2, "0")}`;
  }

  // Anterior (m-1)
  if (mes === 1) {
    return `${ano - 1}-12`;
  }
  return `${ano}-${String(mes - 1).padStart(2, "0")}`;
}

// Formatação amigável de competência
export function formatCompetenciaLabel(competencia: string): string {
  const [ano, mes] = competencia.split("-");
  const meses = [
    "Jan",
    "Fev",
    "Mar",
    "Abr",
    "Mai",
    "Jun",
    "Jul",
    "Ago",
    "Set",
    "Out",
    "Nov",
    "Dez",
  ];
  const idx = parseInt(mes, 10) - 1;
  const nomeMes = meses[idx] || mes;
  return `${nomeMes}/${ano.slice(2)}`;
}

// Função agregadora de dados para o Panorama
export function calculateSyntheticPanorama(
  filters: PanoramaFilters,
): PanoramaData {
  const { periodo, comparacao, municipio, classe } = filters;
  const compAnterior = getCompetenciaComparada(periodo, comparacao);

  // Filtra registros do período atual
  const registrosAtuais = SYNTHETIC_DATABASE.filter((r) => {
    if (r.competencia !== periodo) return false;
    if (
      municipio !== "todos" &&
      r.municipio.toLowerCase() !== municipio.toLowerCase()
    )
      return false;
    if (classe !== "todas" && r.classe.toLowerCase() !== classe.toLowerCase())
      return false;
    return true;
  });

  // Filtra registros do período comparado
  const registrosAnteriores = compAnterior
    ? SYNTHETIC_DATABASE.filter((r) => {
        if (r.competencia !== compAnterior) return false;
        if (
          municipio !== "todos" &&
          r.municipio.toLowerCase() !== municipio.toLowerCase()
        )
          return false;
        if (
          classe !== "todas" &&
          r.classe.toLowerCase() !== classe.toLowerCase()
        )
          return false;
        return true;
      })
    : [];

  // Agrega valores atuais
  const atual = somarRegistros(registrosAtuais);
  const anterior = compAnterior ? somarRegistros(registrosAnteriores) : null;

  const isIncompleto = periodo === "2024-05";

  // Preço médio efetivo = Receita Faturada / Energia Faturada
  const precoMedioAtual =
    atual.energiaFaturada > 0
      ? atual.receitaFaturada / atual.energiaFaturada
      : 0;
  const precoMedioAnterior =
    anterior && anterior.energiaFaturada > 0
      ? anterior.receitaFaturada / anterior.energiaFaturada
      : null;

  // Monta métricas com comparação e tratamento de base zero
  const buildMetric = (
    id: string,
    nome: string,
    subtitulo: string,
    categoria: "financeiro" | "fisico" | "operacional",
    tipoGrandeza: "faturado" | "pago" | "consumido" | "operacao",
    valAtual: number,
    valAnterior: number | null,
    unidade: string,
    definicao: string,
    formula: string,
    bomSentido: "positivo" | "negativo" = "positivo",
  ) => {
    const temAnterior = valAnterior !== null && valAnterior !== undefined;
    const baseZero = temAnterior && valAnterior === 0;
    let variacaoAbs: number | undefined = undefined;
    let variacaoPct: number | undefined = undefined;

    if (temAnterior && !baseZero) {
      variacaoAbs = valAtual - (valAnterior as number);
      variacaoPct =
        ((valAtual - (valAnterior as number)) / (valAnterior as number)) * 100;
    } else if (temAnterior && baseZero) {
      variacaoAbs = valAtual;
      // quando base anterior é zero, % é matematicamente indefinido
      variacaoPct = undefined;
    }

    return {
      id,
      nome,
      subtitulo,
      categoria,
      tipoGrandeza,
      valorAtual: valAtual,
      valorAnterior: temAnterior ? (valAnterior as number) : undefined,
      variacaoAbsoluta: variacaoAbs,
      variacaoPercentual: variacaoPct,
      unidade,
      definicao,
      formula,
      baseZero,
      bomSentido,
    };
  };

  // Série temporal dos últimos 12 meses (ou todas as competências disponíveis)
  const serieMensal = buildMonthlySeries(municipio, classe);

  return {
    filtros: filters,
    periodoIncompleto: isIncompleto,
    totalRegistros: registrosAtuais.length,
    dataAtualizacao: "2024-04-30T18:00:00Z",
    loteVersao: "Lote Gold 2024.04-sintetico-v1",
    metricas: {
      receitaFaturada: buildMetric(
        "rec_fat",
        "Receita Faturada",
        "Valor faturado em contas emitidas",
        "financeiro",
        "faturado",
        atual.receitaFaturada,
        anterior ? anterior.receitaFaturada : null,
        "R$",
        "Total monetário faturado no ciclo de faturamento da competência.",
        "Σ(faturas_emitidas.valor_total)",
        "positivo",
      ),
      receitaPaga: buildMetric(
        "rec_pag",
        "Receita Arrecadada / Paga",
        "Valor liquidado e recebido",
        "financeiro",
        "pago",
        atual.receitaPaga,
        anterior ? anterior.receitaPaga : null,
        "R$",
        "Total financeiro liquidado e recebido no período (distingue-se do faturado).",
        "Σ(pagamentos.valor_pago)",
        "positivo",
      ),
      energiaConsumida: buildMetric(
        "ene_con",
        "Energia Consumida",
        "Volume medido nos medidores",
        "fisico",
        "consumido",
        atual.energiaConsumida,
        anterior ? anterior.energiaConsumida : null,
        "kWh",
        "Volume físico medido nos pontos de entrega das unidades consumidoras.",
        "Σ(medicoes.leitura_atual - medicoes.leitura_anterior)",
        "positivo",
      ),
      energiaFaturada: buildMetric(
        "ene_fat",
        "Energia Faturada",
        "Volume faturado nas contas",
        "fisico",
        "faturado",
        atual.energiaFaturada,
        anterior ? anterior.energiaFaturada : null,
        "kWh",
        "Volume de energia considerado para fins tarifários (após compensação GD e limites contratuais).",
        "Σ(faturas.consumo_faturado_kwh)",
        "positivo",
      ),
      precoMedioEfetivo: buildMetric(
        "prc_med",
        "Preço Médio Efetivo",
        "Receita faturada ÷ volume faturado",
        "financeiro",
        "faturado",
        precoMedioAtual,
        precoMedioAnterior,
        "R$/kWh",
        "Tarifa média efetiva praticada no período. Não confundir com a tarifa homologada ANEEL.",
        "Receita Faturada / Energia Faturada",
        "positivo",
      ),
      ucsAtivas: buildMetric(
        "ucs_atv",
        "UCs Ativas",
        "Unidades com contrato regular",
        "operacional",
        "operacao",
        atual.ucsAtivas,
        anterior ? anterior.ucsAtivas : null,
        "UCs",
        "Contagem de unidades consumidoras ativas com faturamento ou medição regular.",
        "COUNT(DISTINCT uc_id WHERE status = 'ATIVO')",
        "positivo",
      ),
      continuidadeDec: buildMetric(
        "cont_dec",
        "Duração Equivalente (DEC)",
        "DEC médio simplificado",
        "operacional",
        "operacao",
        atual.decHoras,
        anterior ? anterior.decHoras : null,
        "horas/UC",
        "Duração média simplificada das interrupções por unidade consumidora atendida.",
        "Σ(duracao_interrupcao × ucs_afetadas) / Total UCs",
        "negativo",
      ),
      continuidadeFec: buildMetric(
        "cont_fec",
        "Frequência Equivalente (FEC)",
        "FEC médio simplificado",
        "operacional",
        "operacao",
        atual.fecVezes,
        anterior ? anterior.fecVezes : null,
        "interrupções/UC",
        "Frequência média simplificada de interrupções por unidade consumidora atendida.",
        "Σ(ucs_afetadas_interrupcao) / Total UCs",
        "negativo",
      ),
    },
    serieMensal,
  };
}

function somarRegistros(registros: SyntheticRecord[]) {
  if (registros.length === 0) {
    return {
      receitaFaturada: 0,
      receitaPaga: 0,
      energiaConsumida: 0,
      energiaFaturada: 0,
      ucsAtivas: 0,
      decHoras: 0,
      fecVezes: 0,
    };
  }

  const totais = registros.reduce(
    (acc, r) => ({
      receitaFaturada: acc.receitaFaturada + r.receitaFaturada,
      receitaPaga: acc.receitaPaga + r.receitaPaga,
      energiaConsumida: acc.energiaConsumida + r.energiaConsumidaKwh,
      energiaFaturada: acc.energiaFaturada + r.energiaFaturadaKwh,
      ucsAtivas: acc.ucsAtivas + r.ucsAtivas,
      decPonderado: acc.decPonderado + r.decHoras * r.ucsAtivas,
      fecPonderado: acc.fecPonderado + r.fecVezes * r.ucsAtivas,
    }),
    {
      receitaFaturada: 0,
      receitaPaga: 0,
      energiaConsumida: 0,
      energiaFaturada: 0,
      ucsAtivas: 0,
      decPonderado: 0,
      fecPonderado: 0,
    },
  );

  const decMedio =
    totais.ucsAtivas > 0 ? totais.decPonderado / totais.ucsAtivas : 0;
  const fecMedio =
    totais.ucsAtivas > 0 ? totais.fecPonderado / totais.ucsAtivas : 0;

  return {
    receitaFaturada: Math.round(totais.receitaFaturada * 100) / 100,
    receitaPaga: Math.round(totais.receitaPaga * 100) / 100,
    energiaConsumida: Math.round(totais.energiaConsumida * 100) / 100,
    energiaFaturada: Math.round(totais.energiaFaturada * 100) / 100,
    ucsAtivas: totais.ucsAtivas,
    decHoras: Math.round(decMedio * 100) / 100,
    fecVezes: Math.round(fecMedio * 100) / 100,
  };
}

function buildMonthlySeries(
  municipio: string,
  classe: string,
): MonthlyDataPoint[] {
  // Ordena competências cronologicamente
  const competencias = [
    "2023-05",
    "2023-06",
    "2023-07",
    "2023-08",
    "2023-09",
    "2023-10",
    "2023-11",
    "2023-12",
    "2024-01",
    "2024-02",
    "2024-03",
    "2024-04",
  ];

  return competencias.map((comp) => {
    const regs = SYNTHETIC_DATABASE.filter((r) => {
      if (r.competencia !== comp) return false;
      if (
        municipio !== "todos" &&
        r.municipio.toLowerCase() !== municipio.toLowerCase()
      )
        return false;
      if (classe !== "todas" && r.classe.toLowerCase() !== classe.toLowerCase())
        return false;
      return true;
    });

    const s = somarRegistros(regs);
    return {
      competencia: comp,
      label: formatCompetenciaLabel(comp),
      receitaFaturada: s.receitaFaturada,
      receitaPaga: s.receitaPaga,
      energiaConsumidaKwh: s.energiaConsumida,
      energiaFaturadaKwh: s.energiaFaturada,
      ucsAtivas: s.ucsAtivas,
      decHoras: s.decHoras,
      fecVezes: s.fecVezes,
    };
  });
}
