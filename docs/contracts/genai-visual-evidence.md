# Evidência visual no Assistente e no Panorama

Estado: integração em desenvolvimento na branch `feat/genai-graficos-insights-visuais`, base develop `77fa425`. Cartão [gráficos e insights visuais](https://trello.com/c/OGgXnYfa). Referência física obrigatória: Gold CSV v2, catálogo `gold-catalog-v2`, schema `gold_v2`. Nenhuma credencial ou permissão foi alterada.

## Caminho composto

Chat: rota pública existente → planejamento e catálogo → executor SQL restrito do Backend → síntese e guardas existentes → montagem determinística de `visualization` → resposta/auditoria/histórico → decoder → `VisualEvidence`.

Panorama: repositório/snapshot existente → KPIs e distribuição opcional → decoder → modal existente → mesmo componente de gráfico, tabela e exportação. Os gráficos do modal usam dados dos indicadores, sem esperar a síntese. No chat, a resposta ainda chega depois da síntese: apresentação progressiva permanece pendente.

Não se extraem números da prosa nem se executa código de gráfico do modelo. Os clientes recusam `visualization` fornecida pelo serviço GenAI; somente o Backend monta esse campo. Não há nova chamada de modelo para selecionar/desenhar gráficos nem consulta extra no chat.

## Contrato opcional do chat

`AIQuestionResponse.visualization` é omitido quando ausente, preservando clientes e respostas históricas anteriores. Só acompanha `answered` com evidência Gold não demonstrativa e contexto da publicação v2.

| Campo | Regra |
| --- | --- |
| contract_version | `v1`; independente da versão física Gold v2 |
| kind | bars, horizontal ou line |
| metric / dimension_ids | identificadores lógicos autorizados do plano, nunca colunas físicas |
| title / unit / precision | rótulo, unidade e 0–6 casas decimais do catálogo aprovado |
| period | período canônico do plano; deve coincidir com o contexto da resposta |
| points | 1–100 observações com ID `row_N`, rótulo de negócio e número finito |
| plot_points | subconjunto exato de até 24 pontos (dez para categorias); tabela/CSV preservam a lista retornada |
| category_label / note | dimensão legível e alcance do resultado, incluindo ranking/top N |

O mapper confere plano, proveniência, filtros, publicação, unidade e período; IDs e valores do subconjunto precisam coincidir exatamente. Payload visual acima de 32 KiB é omitido. Fontes sem proveniência, decomposição publicada e múltiplas dimensões de agrupamento mantêm a resposta textual, sem inventar gráfico.

Uma observação permanece indicador. Categorias usam barras horizontais. Série temporal com pelo menos três competências consecutivas e ordenadas usa linha; duas competências ou lacunas usam barras. Nenhuma linha atravessa ausência como continuidade comprovada. Métricas não aditivas não são somadas nem convertidas em participação.

## Distribuição opcional do Panorama

`data.distribuicao` contém dimension (municipio/classe), periodo, metricId, unidade, total, completo, pontos, visual e agrupados. Origem e filtros são os do envelope existente. Não recebe pontos do navegador.

Gold usa `receita_base_comparavel_reais`, mesma métrica do KPI de receita comparável. Reutiliza `revenue_groups` na mesma conexão/snapshot, com mês, município e classe aplicados: uma consulta agregada adicional por carregamento. Demonstração usa sua própria energia faturada, sempre identificada como fictícia.

Todos os municípios: agrupar por município, preservando a classe. Município específico e todas as classes: agrupar por classe. Ambos específicos: nenhuma distribuição artificial de um grupo. Não remover filtros para produzir mais categorias.

Lista completa: 2–1000 grupos, rótulos válidos/únicos e soma reconciliada com o total. Fora dessas condições, omitir a distribuição e preservar os KPIs. Soma e percentuais usam Decimal. Nulo não vira zero. `completo` significa partição numérica dos valores observados, não mês certificado nem homologação de Dados. Participação exige total positivo, valores não negativos e ausência de medidas nulas. Arredondamento de percentuais não força soma 100.

Partição válida: até seis setores, ou cinco maiores + Demais calculado no Backend, com lista completa separada. Demais casos: até dez barras, sem porcentagem indevida. Lista/tabela/CSV preservam todos os grupos retornados; tabela de vinte linhas por página. Legenda no celular tem rolagem; PNG inclui legenda completa.

## Exportação e apresentação

PNG e CSV estão no chat e nos gráficos do modal. Exportação usa apenas agregados já autorizados e os mesmos pontos da tabela. PNG exporta o resumo visual; CSV exporta a lista retornada. Notas de alcance e limitações relevantes acompanham os dois arquivos.

- PNG: SVG local, fundo do tema, título/recorte/unidade/fonte, rótulos e notas legíveis; largura 1200–3600px conforme a série, metadados quebrados em linhas. Sem captura da página ou serviço externo.
- CSV: UTF-8 com BOM, ponto e vírgula, vírgula decimal, nulo vazio e zero numérico. Preserva precisão dos valores; texto entre aspas com escape de aspas/quebras e neutralização de fórmulas. O arquivo inclui fonte, indicador, recorte, unidade e nota de alcance quando existente.
- Visual: pt-BR, datas amigáveis, moeda e separador de milhar; precisão do catálogo, incluindo DEC com seis casas, sem `.0` desnecessário nas contagens.
- Chat: fonte e definição junto aos metadados; sem acordeão técnico. Limitações e citações documentais continuam visíveis. SQL, nomes físicos, hashes e IDs de lote não entram na apresentação nem nos arquivos.

Antes de salvar, `POST /api/v1/ai/visualizations/verify` revalida a sessão individual, leitura, métrica/dimensões autorizadas e publicação corrente pelo leitor dedicado. Recebe somente metadados, nunca números/SQL. Panorama resolve lote/fingerprint pela regra existente; chat usa a referência canônica. Alteração de permissão/publicação nega o download. O frontend confere também geração de autorização/publicação e desmontagem, inclusive depois da resposta assíncrona. A verificação tem prazo de oito segundos e ocorre só no clique; não acrescenta requisição ao carregamento ou ao Gemini.

## Histórico e memória

O JSON persistido guarda o campo opcional sem migração. Restauração conserva gráfico somente com publicação atual e escopo compatível; indisponibilidade do leitor ou publicação antiga remove a visualização, preservando o texto histórico. Cache e retomadas mantêm as verificações existentes. Retomar assunto replaneja e consulta a fonte atual; pontos antigos não viram fatos da memória. Resposta conceitual não recebe gráfico quantitativo.

## Evidências e limites

[Plano de validação](../plans/2026-11-03-genai-graficos-insights-visuais.md) registra comandos/resultados: 154 testes Backend, 59 frontend, build/lint/fronteiras e Chromium. Reconciliação Gold real somente leitura via `python -m scripts.check_visual_gold`: três distribuições conferidas (14/14/5 grupos) e recorte específico sem expansão. No lote local essas distribuições não admitem participação; barras preservam essa distinção.

Revisão em dois eixos identificou período divergente, CSV sem nota de alcance e PNG estreito para 24pontos; todos corrigidos e revalidados. Ainda faltam apresentação progressiva no chat, interpretação ampliada por gráfico, benchmark comparável e prova integral do novo chat com Gold e modelo real. Esta fatia não alterou DEC503, avisos de consumo ou cobertura, tratados pela colega. Nenhuma nova chamada Gemini; nenhuma certificação de Dados ou mudança dos estados oficiais IA.
