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
  valorAtual: number | null;
  valorAnterior?: number | null;
  variacaoAbsoluta?: number | null;
  variacaoPercentual?: number | null;
  unidade: string;
  definicao: string;
  formula: string;
  baseZero?: boolean;
  bomSentido?: "positivo" | "negativo"; // se variação positiva é boa (ex: receita = positivo; DEC/FEC = negativo)
  status?: "available" | "partial" | "empty" | "unavailable";
  limitacoes?: string[];
  statusComparacao?: "available" | "partial" | "empty" | "unavailable";
  limitacoesComparacao?: string[];
}

export interface MonthlyDataPoint {
  competencia: string; // "2024-01"
  label: string; // "Jan/24"
  receitaFaturada: number | null;
  receitaPaga: number | null;
  energiaConsumidaKwh: number | null;
  energiaFaturadaKwh: number | null;
  ucsAtivas: number | null;
  decHoras: number | null;
  fecVezes: number | null;
  status?: "available" | "partial" | "empty" | "unavailable";
}

export interface PanoramaFilterOptions {
  competencias: string[];
  municipios: string[];
  classes: string[];
}

export interface PanoramaOrigin {
  kind: "gold" | "synthetic";
  isDemo: boolean;
  version: string;
  fingerprint?: string;
  schemaVersion?: string;
  contractVersion: string;
  temporalScope?: string;
  limitations: string[];
}

export interface PanoramaData {
  filtros: PanoramaFilters;
  periodoIncompleto: boolean;
  totalRegistros: number;
  dataAtualizacao: string;
  loteVersao: string;
  fechamentoMensalDeclarado?: boolean;
  opcoesFiltros?: PanoramaFilterOptions;
  origem?: PanoramaOrigin;
  metricas: {
    receitaFaturada: KpiMetric;
    receitaPaga: KpiMetric;
    energiaConsumida: KpiMetric;
    energiaFaturada: KpiMetric;
    precoMedioEfetivo: KpiMetric;
    ucsAtivas: KpiMetric;
    continuidadeDec: KpiMetric;
    continuidadeFec: KpiMetric;
    ucsFaturadasNoMes?: KpiMetric;
  };
  serieMensal: MonthlyDataPoint[];
}
