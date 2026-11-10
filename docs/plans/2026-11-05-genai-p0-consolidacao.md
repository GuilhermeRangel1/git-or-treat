# P0 — consolidação do diagnóstico e critérios de negócio

Data: 05/11/2026. Branch `feat/genai-baseline`. **Estado: diagnóstico inicial P0 concluído no alcance descrito neste documento.** A pessoa usuária confirmou no chat a consolidação e o significado de interpretação: identificar métrica, período, filtros, operação e contexto antes da execução.

## Evidências disponíveis

- Planejamento dirigido: 46 casos, 40 conformes e seis divergentes nos oráculos anotados.
- Relatos reais: dois originais, quatro controles e uma continuação; 4/7 conformes. Não misturar esse denominador com o anterior.
- Pacote do case: 24 cenários; 18 esclarecimentos e seis planos. Revisão humana: 12 inadequados, quatro adequados, dois adequados com ressalvas e seis avaliações de natureza distinta (esclarecimento, resposta parcial, decisão de negócio, somente leitura, melhoria adiada e causalidade). Essas categorias não formam uma taxa de acerto numérico.
- Síntese sobre agregados artificiais: 14/14.
- PostgreSQL 16 descartável: um teste integrado passou em 205,42 s, com sessão pública, leitor restrito, SQL independente, evidência e auditoria; modelo falso.

## Causas e prioridades consolidadas

| Eixo | Evidência | Critério de aceite |
| --- | --- | --- |
| Interpretação de entidade, período e operação | Pedidos de total/ranking tratados como local ou classe desconhecidos; percentual de comparação confundido com unidade; datas em ordem natural não reconhecidas | Intenção tipada preserva métrica, período, filtros, agrupamento, operação e contexto; esclarecer apenas informação essencial realmente ausente |
| Capacidade analítica e granularidade | Ranking limitado a uma competência; série mensal proposta quando se pediu total do intervalo; análise composta ausente | Soma, ranking, distribuição e comparação calculados sobre a granularidade correta, com unidade e referência independente; valores e tabelas quando pedidos |
| Conversa e comunicação de limites | Confirmação de classes perde contexto; pedidos compostos descartados; mudança de dados e inferência de fraude recebem perguntas genéricas | Responder a parte executável, explicar limites específicos e preservar contexto; nenhuma escrita nem causalidade inventada |

São eixos sobrepostos: uma pergunta pode ter falha inicial de interpretação e também uma capacidade posterior ausente. A frequência medida no corpus inicial foi 3 casos de classificação de entidade/calendário, 2 de ranking no intervalo e 1 de ranking temporal. A revisão humana confirma o impacto dessas famílias e acrescenta expectativas de apresentação e resposta parcial. Não há amostragem para estimar frequência de produção.

## Primeira entrega escolhida após avaliação humana

Investigar interpretação quantitativa de faturamento, período e agrupamento/ranking, usando os relatos originais e controles. Primeiro comparar a intenção determinística com proposta semântica tipada em observação, reutilizando o catálogo e a composição existentes; não encaminhar a proposta ao executor nessa etapa. A hipótese é ganho de robustez fora das frases canônicas; ainda não foi comprovada. Os dados mostram que a formulação canônica funciona onde variantes naturais falham. Isso justifica avaliar a compreensão antes de limitar a próxima mudança à implementação do máximo mensal.

Critérios congelados antes da implementação:

- Medir a correspondência de métrica, janela, filtros, agrupamento, operação, ordenação e limite com a referência; plano válido sozinho não conta como intenção correta.
- Preservar todos os controles atualmente conformes do conjunto fixado; registrar cada regressão.
- Propostas não podem inventar IDs, períodos, valores de dimensão ou ampliar autorização; falhas de validação não chegam à execução.
- Distinguir intenção compreendida mas operação indisponível de ambiguidade ou ausência de dados.
- Comparar acerto, tipos de erro, latência e consumo disponíveis; sem ganho demonstrado, não promover fallback.

Essa entrega de observação não encerra a correção percebida pelo usuário. A entrega seguinte transforma o resultado validado em comportamento executável, completa uma análise vertical (distribuição por classe/totais e rankings conforme prioridade) e produz valores, tabela e fundamentos. O ranking temporal CASE/P0-37 continua como caso de regressão relevante.

## Reserva e limites

Foi separado `ai-agent/tests/fixtures/gold_p0_reserved.json`: 12 perguntas novas, não executadas e fora da whitelist do avaliador atual. São uma reserva autoral para uso futuro; autoria pelo mesmo assistente não equivale a benchmark cego independente. As intenções anotadas são propostas para revisão, não um novo contrato HTTP. Os 24 casos já apresentados e avaliados continuam desenvolvimento, sem alegação de holdout.

CASE-16 permanece pendente de definição de negócio para inspeções/recuperação, sem bloquear outras famílias. CASE-09 admite esclarecimento; CASE-23 tem melhoria adiada; CASE-18 exige somente leitura explícita; CASE-24 exige limitação causal. A aprovação do formato do CASE-08 não comprova totais anuais ou participações corretos.

## Critérios de saída do diagnóstico inicial

Há conjunto reproduzível, primeira divergência classificada, causas ordenadas por evidência/impacto, baseline técnico e justificativa da primeira entrega. O diagnóstico inicial está consolidado no alcance dos dados artificiais e relatos disponíveis. Permanecem separados os gates de produto: avaliação cega independente, publicação Gold real, inferência Gemini, portal e qualidade numérica das capacidades ainda não implementadas. Custo/tokens reais e latência de produção continuam não medidos. Isso não altera estados de aceite IA do PRD.
