export type ComparisonType = "anterior" | "ano_anterior" | "nenhuma";

export interface PanoramaFilters {
  periodo: string; // ex: "2024-04"
  comparacao: ComparisonType;
  municipio: string; // "todos" ou nome do município
  classe: string; // "todas" ou nome da classe
}

export interface KpiMetric {
  id: string;
  nome: string;
  subtitulo?: string;
  categoria: "financeiro" | "fisico" | "operacional";
  tipoGrandeza: "faturado" | "pago" | "consumido" | "operacao";
  valorAtual: number;
  valorAnterior?: number | null;
  variacaoAbsoluta?: number | null;
  variacaoPercentual?: number | null;
  unidade: string;
  definicao: string;
  formula: string;
  baseZero?: boolean;
  bomSentido?: "positivo" | "negativo"; // se variação positiva é boa (ex: receita = positivo; DEC/FEC = negativo)
}

export interface MonthlyDataPoint {
  competencia: string; // "2024-01"
  label: string; // "Jan/24"
  receitaFaturada: number;
  receitaPaga: number;
  energiaConsumidaKwh: number;
  energiaFaturadaKwh: number;
  ucsAtivas: number;
  decHoras: number;
  fecVezes: number;
}

export interface PanoramaData {
  filtros: PanoramaFilters;
  periodoIncompleto: boolean;
  totalRegistros: number;
  dataAtualizacao: string;
  loteVersao: string;
  metricas: {
    receitaFaturada: KpiMetric;
    receitaPaga: KpiMetric;
    energiaConsumida: KpiMetric;
    energiaFaturada: KpiMetric;
    precoMedioEfetivo: KpiMetric;
    ucsAtivas: KpiMetric;
    continuidadeDec: KpiMetric;
    continuidadeFec: KpiMetric;
  };
  serieMensal: MonthlyDataPoint[];
}
