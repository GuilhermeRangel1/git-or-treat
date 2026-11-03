# Evidência visual no Assistente e no Panorama

Estado: integração em desenvolvimento na branch `feat/genai-graficos-insights-visuais`, base develop `77fa425`. Cartão [gráficos e insights visuais](https://trello.com/c/OGgXnYfa). Referência física obrigatória: Gold CSV v2, catálogo `gold-catalog-v2`, schema `gold_v2`. Nenhuma credencial ou permissão foi alterada.

## Caminho composto

Chat: rota pública existente → planejamento e catálogo → executor SQL restrito do Backend → síntese e guardas existentes → montagem determinística de `visualization` → resposta/auditoria/histórico → decoder → `VisualEvidence`.

Panorama: repositório/snapshot existente → KPIs e distribuição opcional → decoder → modal existente → mesmo componente de gráfico, tabela e exportação. Os gráficos do modal usam dados dos indicadores, sem esperar a síntese. No chat, o consumidor pode negociar dados progressivos com Accept: application/x-ndjson; a prévia é publicada após consulta, auditoria e revalidação, antes da síntese. Clientes JSON anteriores continuam recebendo o envelope integral.

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
| reading | leitura determinística opcional: resumo, próximo passo e IDs exatos das observações exibidas |

O mapper confere plano, proveniência, filtros, publicação, unidade e período; IDs e valores do subconjunto precisam coincidir exatamente. Payload visual acima de 32 KiB é omitido. Fontes sem proveniência, decomposição publicada e múltiplas dimensões de agrupamento mantêm a resposta textual, sem inventar gráfico.

Uma observação permanece indicador. Categorias usam barras horizontais. Série temporal com pelo menos três competências consecutivas e ordenadas usa linha; duas competências ou lacunas usam barras. Nenhuma linha atravessa ausência como continuidade comprovada. Métricas não aditivas não são somadas nem convertidas em participação.

Expressões como “entre as classes” e “entre os municípios” designam agrupamento; elas não acionam a exigência de dois períodos. Intervalos temporais incompletos continuam pedindo esclarecimento.

O perfil Gold v2 aceita cadência mensal explícita (como “mês a mês”) nas janelas já sustentadas pelo executor. Consumo medido admite agrupamento por município, classe e bairro sobre as fontes/dimensões já autorizadas; comparações agrupadas mantêm a capacidade específica de bairro. Cobertura, filtros, escopo e limites continuam revalidados. A resposta resume grupos usando os agregados consultados; comparações mantêm os valores inicial/final e a variação calculada, com números pt-BR e meses legíveis. O runner da matriz reconhece esse formato sem perder o vínculo entre mês e valor.

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

## Entrega progressiva e leitura

As rotas de perguntas atuais, inclusive a conversa persistida, negociam `Accept: application/x-ndjson`. Sem a negociação, o JSON anterior permanece. Cada linha tem `type` (data, complete ou error), status e data. `data` contém dados consultados e uma mensagem explícita de interpretação em andamento; não afirma que o modelo respondeu. `complete` substitui a prévia. O plano e a consulta executam uma vez; a síntese existente é reaproveitada.

A fila comporta um evento e respeita o orçamento da requisição. Dependências request do FastAPI permanecem abertas até o fim do stream; corpo é armazenado antes de observar desconexão, evitando dois consumidores ASGI. Desconectar antes ou depois do primeiro evento cancela a tarefa coordenadora e os monitores. Cancelar coroutine não prova interrupção instantânea de SQL em thread: timeout e controles existentes do servidor continuam necessários.

O transporte limita o fluxo a 256KiB, valida UTF-8 e eventos, rejeita dados duplicados ou posteriores ao final. O domínio confere cada envelope e os pontos. Troca de conversa, conta ou publicação cancela/descarta a solicitação. 401/403/409 retiram a prévia. Em falha do modelo, a interface só conserva os dados depois de revalidar acesso/publicação; a interpretação não é apresentada como sucesso. Falha do renderer mantém tabela/CSV e resposta textual.

`reading` usa somente observações identificadas do subconjunto exibido. Backend calcula diferença absoluta e percentual quando a base inicial é positiva, destaque de pico para séries e extremos para categorias. Ranking não vira participação; rosca só descreve parcelas válidas do total observado. Próximo passo não afirma causa nem remove limitações. A leitura é local e determinística, sem segunda chamada Gemini ou números extraídos da prosa. O insight existente continua responsável pela síntese; nenhum modelo adicional foi introduzido.

Referências de evidência sanitizadas pelo núcleo (`gold.local:` + SHA-256 da referência original) são reconhecidas. O mapper confere o hash exato contra a origem consultada, além do plano/recorte; um hash arbitrário continua rejeitado. Fonte amigável na interface permanece interna, sem mostrar esse identificador.

## Evidências e limites

[Plano de validação](../plans/2026-11-03-genai-graficos-insights-visuais.md): 162 testes Backend e 95 frontend passaram, além de build, formatação, lint sem erro e fronteiras. Chromium exerceu quatro larguras, dois temas, zoom de 200%, movimento reduzido, teclado, foco e árvore de acessibilidade. Testes de erro incluem renderer, fluxo incompleto/excessivo, falha do modelo, acesso negado, cancelamento antes/depois da prévia e contexto inválido.

Gold local com sessão temporária somente leitura e Gemini real: total de um mês, comparação de dois e série de seis reconciliados com SQL independente, mesma publicação, pelo leitor dedicado. Dados iniciais iguais aos pontos finais; CSV real do portal conferiu com pontos/SQL. Histórico restaurou três gráficos de quatro interações; conceitual sem gráfico e retomada consultando o recorte atual. Portal real validou tabela, PNG/CSV e recarga. Conta/sessões/conversas de teste são removidas ao final.

Distribuição do Panorama conferida em três recortes (14/14/5 grupos), sem expansão dos filtros. O lote local não permite participação nesses recortes: barras preservam esse limite. Rosca válida é provada com controles artificiais reconciliados; não certifica cobertura real ausente.

Benchmark exploratório da mesma comparação, três requisições por modo, mesmos serviços/publicação: JSON primeiro resultado/completo p50=15,792s e p95 empírico=19,213s; progressivo primeiro dado p50=14,153s/p95=14,653s, completo p50=16,069s/p95=16,917s. P95 por nearest rank, equivalente ao máximo nessa amostra pequena. Não é SLA nem prova de ganho geral no tempo total. Em14 correlações reais do serviço isolado houve uma chamada ao modelo por correlação; fallback/retentativas existentes não são eliminados.

Estados oficiais IA e homologação de Dados preservados. DEC503 e avisos de consumo permanecem fora desta mudança. Os18critérios técnicos locais estão contemplados com evidências publicadas no [PR #116](https://github.com/GuilhermeRangel1/git-or-treat/pull/116), sem alterar o aceite oficial IA ou realizar merge.
