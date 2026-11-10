// Perguntas já exercitadas no fluxo Gold local. Datas são exemplos editáveis.
const assistantExamples = {
  distribution: "Distribua a receita faturada por município em junho de 2026.",
  ranking: "Quais municípios tiveram maior consumo medido em junho de 2026?",
  comparison:
    "Compare o consumo medido em Recife entre janeiro e junho de 2026.",
  monthlySeries:
    "Como evoluiu o consumo medido em Recife, mês a mês, de janeiro a junho de 2026?",
} as const;

export const ASSISTANT_EXAMPLES: string[] = Object.values(assistantExamples);
export const ASSISTANT_HOME_SUGGESTIONS = [
  assistantExamples.distribution,
  assistantExamples.monthlySeries,
  "Compare a receita de Recife entre maio de 2026 e junho de 2026.",
  "Quais municípios apresentaram a maior queda no consumo de energia nos últimos 12 meses e como essa redução impactou a receita faturada, considerando as diferentes classes de consumo?",
];

// Exemplos adicionais baseados nos cenários positivos da matriz Gold v2.
// Não se confundem com as sugestões da tela inicial nem prometem cobertura futura.
export const FAQ_EXAMPLE_GROUPS = [
  {
    title: "Receita e preços",
    questions: [
      "Qual foi a receita faturada em Recife em junho de 2026?",
      "Qual foi o faturamento residencial em Olinda em junho de 2026?",
      "Qual foi a receita comercial em Jaboatão dos Guararapes no último trimestre?",
      "Qual foi a receita residencial no bairro Brasília Teimosa, em Recife, em junho de 2026?",
      "Qual foi o ticket médio no município de Recife em junho de 2026?",
      "Qual foi o preço médio observado da energia residencial no município de Recife em junho de 2026?",
      "Qual classe mais contribuiu para a receita no município de Recife em junho de 2026?",
      "Quanto da variação da receita residencial foi efeito preço e quanto foi efeito volume?",
    ],
  },
  {
    title: "Consumo e geração distribuída",
    questions: [
      "Qual foi o consumo residencial em Olinda em junho de 2026?",
      "Qual foi o consumo das unidades com geração distribuída no município de Recife em junho de 2026?",
      "Qual foi o consumo médio por unidade com leitura no município de Recife em junho de 2026?",
      "O consumo residencial em Olinda caiu entre maio de 2026 e junho de 2026?",
      "Qual bairro de Recife mais perdeu volume residencial entre maio de 2026 e junho de 2026?",
      "Quantas UCs com geração distribuída em Olinda tiveram queda de consumo acima de 30%?",
    ],
  },
  {
    title: "Comparações entre períodos",
    questions: [
      "Quanto cresceu a receita comercial em Jaboatão dos Guararapes entre maio de 2026 e junho de 2026?",
      "Compare a receita de Recife entre maio de 2026 e junho de 2026.",
      "Compare o consumo medido de Recife entre maio de 2026 e junho de 2026.",
    ],
  },
  {
    title: "Atendimento",
    questions: [
      "Qual é a satisfação média do atendimento no histórico acumulado?",
    ],
  },
];

export const FAQ_EXAMPLES = FAQ_EXAMPLE_GROUPS.flatMap(
  (group) => group.questions,
);
