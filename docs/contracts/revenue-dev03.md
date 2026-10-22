# DEV-03 — Contrato compartilhado de Receita 1.1.0

**Data:** 21/10/2026 · **Estado:** aprovado para implementação pela autorização da pessoa usuária nesta sessão.
**Base:** `ebccc238bcec502bfa7a1b36ff32e01b0c6c4567`; branch de execução `dev03`.

Complementa o [catálogo analítico](analytics-api.md), o [desenho](../design/2026-10-21-dev03-design.md) e o [plano](../plans/2026-10-21-dev03-plan.md). Contrato de aplicação demonstrativo; não define Gold. Controlador é responsável por mudanças neste acordo e deve avisar os dois implementadores antes de alterar nomes ou semânticas.

## Operação e tipos

`GET /api/v1/revenue` preserva os parâmetros DEV-01 e acrescenta `group_by`, enum `municipio|bairro|classe`, padrão `municipio`. Competências padrão preservadas: `2025-01` a `2025-02`. Valores desconhecidos, vazios ou parâmetros escalares repetidos retornam 422. Se o tratamento comum precisar mudar para rejeitar repetições, limitar essa mudança a Receita.

Envelope `{data, metadata}`; somente Receita publica `metadata.contract_version = "1.1.0"`. Outros endpoints mantêm sua versão e formato. `metadata` preserva período, filtros efetivos, origem, lote, `is_demo`, atualização e limitações declaradas pela fonte; diagnósticos calculados ficam nos campos de qualidade, cobertura, decomposição e reconciliação correspondentes, sem agregação duplicada em `metadata.limitations`. Não trocar fixtures quando uma fonte real falhar.

Os nomes abaixo correspondem a campos JSON obrigatórios; `?` significa nulidade permitida, não omissão. `number` é número JSON finito; dinheiro usa precisão decimal no servidor e serialização numérica explícita. `Status = available|empty|partial|unavailable`. `Filters` é o objeto DEV-01 com `municipio`, `bairro`, `classe`, `alimentador`, todos `string|null`.

```typescript
type Snapshot = {
  competencia: string; // YYYY-MM
  billed_amount: number | null; // BRL
  billed_energy_kwh: number | null;
  observed_price_brl_per_kwh: number | null;
  billed_uc_count: number | null; // UCs distintas com fatura nesse extremo
  status: Status;
  limitations: string[];
};
type Quality = {
  small_base_threshold_uc: number; // 5 nesta versão demonstrativa
  small_base: boolean;
  percent_change_eligible: boolean;
  limitations: string[];
};
type Comparison = {
  initial: Snapshot;
  final: Snapshot;
  billed_amount_change_brl: number | null;
  billed_energy_change_kwh: number | null;
  measured_energy_change_kwh: number | null;
  billed_amount_change_percent: number | null;
};
type MetricCoverage = {
  status: Status;
  covered_months: string[];
  missing_months: string[];
  limitations: string[];
};
type Coverage = {
  requested_months: string[];
  billed_amount: MetricCoverage;
  billed_energy_kwh: MetricCoverage;
  paid_amount: MetricCoverage;
  measured_energy_kwh: MetricCoverage;
};
type BreakdownItem = {
  key: string; // opaca e estável; bairro inclui município na identidade
  label: string;
  filters: Filters; // recorte efetivo desta linha, incluindo filtros herdados
  comparison: Comparison;
  quality: Quality;
};
type Reconciliation = {
  status: Status;
  initial_known_sum_brl: number | null;
  final_known_sum_brl: number | null;
  comparable_change_sum_brl: number | null;
  non_comparable_group_count: number;
  unattributed_change_brl: number | null;
  residual_brl: number | null;
  limitations: string[];
};
type RevenueData = {
  currency_unit: "BRL";
  energy_unit: "kWh";
  total_billed_amount: number | null;
  total_paid_amount: number | null;
  total_measured_energy_kwh: number | null;
  total_billed_energy_kwh: number | null;
  observed_price_brl_per_kwh: number | null;
  series: {competencia: string; billed_amount: number | null;
    paid_amount: number | null; measured_energy_kwh: number | null;
    billed_energy_kwh: number | null}[];
  comparison: Comparison;
  price_volume: {
    method: "endpoint_price_volume";
    reference_version: "dev03-v1";
    price_effect_brl: number | null;
    volume_effect_brl: number | null;
    interaction_effect_brl: number | null;
    rounding_adjustment_brl: number | null;
    status: Status;
    limitations: string[];
  };
  coverage: Coverage;
  quality: Quality;
  breakdown: {
    dimension: "municipio" | "bairro" | "classe";
    items: BreakdownItem[];
    reconciliation: Reconciliation;
  };
  filter_options: {
    municipios: string[];
    bairros: {municipio: string; bairro: string}[];
    classes: string[];
  };
};
```

`Status` e `Filters` acima são aliases dos tipos descritos em prosa; não são campos extras. Chaves de bairro e filtros usam município/bairro juntos, nunca apenas o rótulo. Opções vêm de toda a fonte, para permitir mudar um filtro já aplicado; a interface limita os bairros ao município escolhido. Ordem estável por rótulo e chave, sem paginação/top-N e sem HTTP por linha nesta entrega.

## Ausência, cobertura e contagens

O adaptador declara cobertura de faturamento e energia faturada independentemente dos fatos encontrados. Para testes pode receber um conjunto explícito de competências cobertas; não inferir completude a partir do mínimo/máximo de faturas existentes. Cobertura das demais grandezas também precisa reconhecer registros nulos e meses faltantes, sem tratar energia medida como faturada. As definições concretas do atributo do repositório ficam sob propriedade backend, desde que esse contrato HTTP seja atendido.

Em um universo cadastral conhecido, mês com cobertura financeira explicitamente completa e sem faturas pode representar zero observado de faturamento/energia faturada, com contagem zero e limitação explicando a regra. Se não houver cobertura comprovada, é ausência (`null`), nunca zero. Um filtro válido sem universo pertinente mantém estado vazio; fatos sem dimensão permanecem no universo com grupo ausente. A série cobre todas as competências solicitadas, incluindo lacunas nulas.

Contar UCs distintas com fatura em cada extremo, sem confundir quantidade de faturas com UCs. `small_base` vale se uma contagem conhecida for menor que cinco; contagem desconhecida também impede percentual e aparece como limitação. `percent_change_eligible` exige duas competências distintas, cobertura financeira comparável, receita inicial positiva e ambas as contagens conhecidas ≥ 5. Qualidade insuficiente bloqueia percentual/ranking percentual, preservando absolutos aritmeticamente conhecidos e avisos.

Comparação por extremos financeiros requer cobertura de **valor faturado** comparável nos extremos e na janela solicitada. Se essa cobertura estiver incompleta, a série/subtotal permanece visível, mas delta em BRL, percentual e decomposição ficam indisponíveis. Cobertura de energia faturada é independente: sua ausência não bloqueia delta financeiro, percentual elegível ou reconciliação em BRL; bloqueia delta em kWh e decomposição. Uma cobertura energética completa pode sustentar delta em kWh mesmo com valor faturado incompleto.

Preço observado em cada extremo exige valor e energia faturados com cobertura completa naquele extremo e energia positiva; a razão acumulada exige ambas as coberturas completas na janela. A decomposição também exige ambas completas na janela, além dos denominadores válidos. Um extremo com valor financeiro conhecido e energia incompleta é `partial`; valor/contagem financeira desconhecidos mantêm a indisponibilidade desse snapshot. Valores conhecidos continuam publicados. Falta de leitura medida/pagamento pode tornar o envelope parcial, sem bloquear uma comparação de faturamento completa. Demonstração e aviso de método provisório, isoladamente, não significam dado incompleto.

Início igual a fim mantém série/acumulado válidos; deltas e decomposição ficam nulos, com motivo de exigir competências distintas. Receita inicial negativa bloqueia percentual; energia não positiva em qualquer extremo bloqueia o método preço-volume. Receita inicial zero ainda admite delta absoluto conhecido.

## Grupos e reconciliação

Nulo ou dimensão vazia recebe rótulo **Não informado** e valor reservado `__grid360_missing__` em filtros/opções. O servidor aceita o marcador apenas onde a fonte realmente tem dimensão ausente, sem confundir o marcador com um nome real; a fonte não pode cadastrar esse texto reservado como valor literal. Não mudar a validação de outras jornadas silenciosamente.

Grupos particionam o universo de fatos/UCs pertinente do recorte, inclusive os que só aparecem em um dos extremos. Não fabricar fatos financeiros por joins com leituras. `initial_known_sum_brl` e `final_known_sum_brl` somam os valores conhecidos **publicados nas linhas** dos grupos. `comparable_change_sum_brl` soma variações conhecidas; se nenhum grupo tiver contribuição conhecida, é `null`, não zero. Se o arredondamento de grupos divergir do extremo agregado publicado, a reconciliação não pode afirmar fechamento completo: conservar as somas visíveis e explicar a diferença em limitações, mesmo quando a variação líquida dos grupos fechar.

Com todos os grupos comparáveis e total conhecido: `residual_brl = delta_total - comparable_change_sum_brl`, `unattributed_change_brl = 0`, estado `available` somente se residual zero a centavos. Com não comparáveis, publicar sua contagem, subtotal conhecido e `unattributed_change_brl = delta_total - comparable_change_sum_brl` quando ambos forem conhecidos; `residual_brl` fica nulo e o estado não afirma fechamento completo. Se a receita total não for comparável, diferença não atribuída também é nula.

Preço/volume/interação de cada recorte devem fechar sua própria variação. Não somar efeitos recalculados em grupos para validar os efeitos do agregado: a mudança de mix impede essa equivalência em geral. Receitas e deltas absolutos são os controles aditivos entre níveis. A interface apresenta receita inicial/final e variação de cada grupo, somas conhecidas e diferenças não atribuídas junto à tabela; os demais detalhes técnicos e diagnósticos permanecem no contrato e nos campos estruturados da API, sem painel dedicado de método, cobertura e limitações.

## Método e controles

Aplicar o método do desenho com `Decimal`, sem usar preço intermediário arredondado. Valores monetários e percentuais são apresentados com duas casas; preço observado com quatro. Usar arredondamento decimal `ROUND_HALF_UP` inclusive em valores negativos. Acumulados somam fatos brutos antes de arredondar; os deltas publicados usam a diferença entre snapshots já quantizados e o percentual usa o mesmo valor inicial publicado. Por exemplo, extremos −5,03 e +5,03 produzem delta +10,06. Soma dos três efeitos + ajuste explícito = delta publicado a centavos; o ajuste contempla também a quantização dos extremos. Ajuste calculável normalmente é zero ou ±0,01; módulo maior que 0,01 sinaliza erro de reconciliação e indisponibilidade, sem mascarar como ajuste normal.

Controle independente de HTTP: R0=80000, R1=76500, Q0=100000, Q1=90000, base suficiente; delta −3500; percentual −4,38 após arredondamento; efeitos volume −8000, preço +5000, interação −500, ajuste zero. A fixture usada nesse teste não precisa ser a mesma do runtime; a demonstração normal deve ter comparações válidas e mais de um recorte explorável.

## Estado no navegador

URL de aplicação usa os filtros base DEV-01, `agrupar_por` e refinamentos `recorte_municipio`, `recorte_bairro`, `recorte_classe`. A query HTTP resulta da composição validada dos filtros e troca `agrupar_por` por `group_by`. Chave TanStack inclui a query efetiva completa. Query inválida não dispara HTTP. Campo escalar repetido é inválido no frontend e no endpoint de Receita.

O filtro legado `alimentador`, quando recebido na URL, compõe a query, a identidade do cache e os filtros base preservados ao aplicar o formulário ou navegar. A tela o identifica no contexto aplicado, mas não acrescenta um seletor de alimentador. O valor é validado quanto a vazio/tamanho no cliente e quanto à existência na fonte no servidor. A detecção de repetição cobre qualquer chave bruta da URL, inclusive nomes não usados como filtros; aplicar um formulário válido remove repetições e permite recuperar o link. Parâmetros desconhecidos únicos não se tornam filtros nem seguem para a consulta HTTP.

Abrir município acrescenta refinamento e permite agrupar seus bairros; abrir bairro preserva seu município; classe pode ser filtrada e agrupada independentemente. Voltar ao total remove somente `recorte_*`. Filtro base nunca pode ser sobrescrito por refinamento contraditório. Formulário e contexto se restauram com reload e histórico; rascunho de formulário continua local. Dados antigos só aparecem com seu contexto original; resposta atrasada não ganha o contexto novo.

Reajuste homologado continua indisponível sem fonte específica. Nenhum campo deste contrato transforma os 10,5% do case em resultado consultado. A identificação de demonstração e os estados relevantes aparecem junto às informações que contextualizam; ausência e falha não aparecem como zeros.
