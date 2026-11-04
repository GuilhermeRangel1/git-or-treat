# Consistência das consultas do Assistente — 04/11/2026

## Escopo e composição

Aceite local do [cartão de consistência](https://trello.com/c/NZ3bE2Wd), na branch
`fix/genai-respostas-chat`, sobre `develop` em `5214aee`. Complementa o trabalho
do PR #117 nos requisitos IA-01/02/03/05/06/07/08. Os estados oficiais do PRD
continuam sujeitos aos seus próprios critérios e à cobertura de Dados.
Os doze aceites deste cartão adicional foram concluídos nesta entrega local.

O fluxo verificado é Portal → sessão individual do Backend → planejamento
GenAI → executor Gold restrito → síntese → resposta, visualização e histórico.
A implementação estende o interpretador, perfil e orquestrador existentes.
Não há novas tabelas, privilégios ou chamadas adicionais de modelo no fluxo padrão.

## Mudanças observáveis

- Exclusões como “sem contar com os clientes de Recife”, “tirando residencial”
  e “desconsiderando as UCs de Recife” esclarecem a operação indisponível,
  sem executar igualdade com o valor excluído. A categoria válida “sem GD”
  e o ranking de menor receita permanecem distintos de uma exclusão.
- “Como o consumo mudou de janeiro para março?” reconhece comparação.
  “Março em comparação com fevereiro” identifica fevereiro como base e março
  como destino. Comparação cronológica invertida sem esse sentido explícito
  continua pedindo esclarecimento.
- “Entrou no caixa” pede confirmação sobre receita faturada. “Sim” conserva
  local e competência. Comparação entre municípios oferece a escolha do local,
  em vez de encaminhar ao FAQ. Falta de luz coloquial oferece DEC/FEC e unidades.
- O mesmo detector conceitual é usado pelo planejamento e pelo roteamento
  documental. Perguntas de definição e fórmula continuam conceituais.
- Rankings nomeiam os grupos pedidos. Listas extensas exibem até dez linhas
  completas, respeitando também o orçamento de 4.000 caracteres. Informam
  quantos resultados foram exibidos e o acesso à tabela/CSV.
- Exemplos com pontuação inicial ou conectores quebrados são descartados.
  Exemplos publicados continuam passando pelo planejador e autorização.
- A leitura da identidade materializa ator, perfil e permissões antes de encerrar
  a transação. A espera pela Gold/modelo deixa de manter essa transação aberta.
  Sessão e escopo continuam sendo revalidados nas fronteiras existentes.
- A nota de uma observação usa singular. Em telas menores, o chat preserva uma
  área útil para mensagens e rola sem sobrepor o campo de pergunta e o histórico.

## Conferência dos doze aceites

| Aceite | Evidência e resultado |
| --- | --- |
| Classificar divergências legadas | As três continuam contadas na avaliação demonstrativa. O Gold não oferece agrupamento municipal/classe de `network.interruptions`; seus equivalentes esclarecem DEC/FEC por alimentador. Nenhum total é inventado. |
| Paráfrases e contrastes | Mesmos 12 contrastes na base e candidata, com catálogo artificial. Base acerta 4; candidata acerta 12. Amostra dirigida aos defeitos encontrados, sem extrapolação de precisão geral. Holdout versionado preservado. |
| Calendário | Suíte cobre abreviações, ano compartilhado/ausente, trimestre, virada de ano, mês anterior, lacunas, série e extremos. Comparação real janeiro→junho reconciliada e relação março/fevereiro validada pela borda HTTP. |
| Filtros combinados | Contraprovas de município/classe/GD, geografia desconhecida, exclusão com qualificadores e correção explícita. “Sem GD” mantém o filtro `Não`. Exclusão indisponível não produz plano. |
| Números e operações | Totais, média, rankings e comparação reais conferidos com SQL independente. Empates e bases zero/ausentes cobertos pelas regressões controladas existentes. |
| Contexto e autorização | Conversa real junho→maio→correção de Recife para Olinda mantém a classe residencial. Troca para atendimento acumulado descarta esses filtros. Confirmação “Sim” mantém Igarassu/junho. Comercial não recebe DEC previamente consultado pelo admin; sessão encerrada retorna 401. Cache e revogação têm regressões de Backend. |
| Quatro domínios | Receita e consumo, atendimento acumulado e DEC/FEC pela rota autenticada. Unidade, definição, lote e observações mantidos. |
| Portal e exportação | Ranking dos três menores conferido em texto, gráfico, tabela e CSV. Reabertura conserva os números. Acompanhamento residencial conserva quantidade, direção e competência. Teste HTTP de dez linhas com seis dimensões extensas comprova orçamento textual. |
| Português e exemplos | Valores em português, períodos legíveis, nota singular, escolhas específicas e exemplos executáveis. Contraprovas cobrem exemplos que não podem trocar silenciosamente o recorte. |
| Segurança e falhas | CPF e escrita recusados pela API real. Perfil comercial sem evidência DEC; sessão revogada 401. Falha temporária Gemini aparece como indisponibilidade recuperável, com referência de auditoria. |
| Precisão e latência | Contrastes base/candidata e 18 requisições reais intercaladas. Medidas abaixo separam primeiro dado, resposta final e falha do provedor. Sem chamada de modelo adicional introduzida pela mudança. |
| Matriz e revisão | Matriz ampliada 160/163, mesmas três falhas conhecidas; suíte GenAI 4.517 aprovados/5 skips; Backend 1.202 aprovados/114 skips; Assistente/gráficos 66 aprovados. Revisões independentes de spec e padrões encerradas após corrigir os achados. |

## Reconciliação local

O leitor `venergy_genai_reader` capturou onze controles agregados numa transação
explicitamente somente leitura. A identidade de `gold.publicacao_atual` foi
comparada à `batch_reference` das respostas. Publicação analítica observada
`GOLD_20261103T173853Z_76c37784`, contrato `gold-csv-v2`, catálogo `gold-catalog-v2`.

| Recorte | Controle observado |
| --- | --- |
| Receita Igarassu, jun/2026 | R$ 300.597,10 |
| Três menores receitas, jun/2026 | Araçoiaba R$ 57.324,09; Ilha de Itamaracá R$ 82.510,16; Itapissuma R$ 126.739,30 |
| Mesmo ranking, classe residencial | R$ 16.352,27; R$ 23.144,33; R$ 25.114,22, na mesma ordem |
| Consumo Recife, jan→jun/2026 | 7.622.382 → 5.353.512 kWh; diferença −2.268.870 kWh e −29,77% |
| Consumo médio por UC com leitura, Olinda, jun/2026 | 350,11 kWh por UC com leitura no mês |
| Chamados no histórico acumulado | 318.871 protocolos |
| DEC/FEC, ALM-JAB-015, jun/2026 | 1,8019607843 horas por UC; 1,1470588235 interrupções por UC, com a precisão pública do indicador |

Na comparação de runtimes, as dezesseis respostas numéricas concluídas coincidiram
com SQL independente na mesma publicação. Na rodada funcional, dezesseis casos
distintos foram validados, incluindo esclarecimentos, recusas e conversas.
O arquivo privado dessa rodada conserva 22 tentativas, quatro delas com falha
temporária do provedor; a verificação permitiu uma repetição por caso.
Unidades abreviadas inicialmente no roteiro foram corrigidas para os textos
exatos do catálogo, sem alterar o contrato da aplicação.

Exemplos de controles independentes, executados com a credencial restrita
configurada localmente, sem expor URL ou senha em comandos/saída pública:

```sql
BEGIN READ ONLY;
SELECT schema_version, lote, publication_id FROM gold.publicacao_atual;
SELECT municipio, sum(receita_total_reais) AS valor
FROM gold_v2.diagnostico_receita WHERE competencia = '2026-06'
GROUP BY municipio ORDER BY valor ASC, municipio ASC;
SELECT competencia, sum(consumo_total_kwh) AS valor
FROM gold_v2.diagnostico_receita
WHERE municipio = 'RECIFE' AND competencia BETWEEN '2026-01' AND '2026-06'
GROUP BY competencia ORDER BY competencia;
SELECT sum(consumo_total_kwh) / nullif(sum(qtd_ucs_com_leitura), 0)
FROM gold_v2.diagnostico_receita
WHERE municipio = 'OLINDA' AND competencia = '2026-06';
ROLLBACK;
```

## Comparação de desempenho

Base `5214aee` e candidata executadas em serviços separados, na mesma rede/banco,
com o mesmo perfil admin, Gemini `gemini-3.5-flash-lite` e configuração de cache.
Três perguntas comuns, três repetições por versão, alternando base e candidata.
Os serviços temporários foram removidos depois da comparação.

| Grupo | n | Respostas concluídas | Mediana primeiro dado | Mediana final | p95 final |
| --- | --- | --- | --- | --- | --- |
| Develop, primeira tentativa | 3 | 2 | 15.844 ms | 27.640 ms | 35.500 ms |
| Candidata, primeira tentativa | 3 | 2 | 16.032 ms | 29.000 ms | 36.110 ms |
| Develop, repetições | 6 | 6 | 16.015 ms | 16.125 ms | 27.938 ms |
| Candidata, repetições | 6 | 6 | 16.015 ms | 16.250 ms | 30.954 ms |

As primeiras tentativas da comparação de consumo falharam nas duas versões.
O log sanitizado identifica Gemini sobrecarregado, status 504. A repetição
seguinte consultou novamente o modelo; por isso o grupo de repetições inclui
uma geração após erro, além dos hits de cache. O maior tempo final desse grupo
acompanha essa geração, não uma nova etapa de interpretação.
Nos hits, o log de execução registra trabalho de modelo de 0 ms.

A mediana do primeiro dado nas repetições foi igual nas duas versões. A mediana
final variou 125 ms (aproximadamente 0,8%). Não foi demonstrada regressão
repetível da aplicação nem redução geral de latência. A preparação/prontidão
continua dominando o tempo dos hits, como já registrado no cartão de cache.
Os p95 são estatísticas descritivas de amostras pequenas, não um SLA.

## Reprodução e verificações

- Em `ai-agent`, `GENAI_MODEL_PROVIDER=unavailable python -m pytest -q --tb=short`
  passou com **4.517 testes e 5 skips**. `python -m ruff check app tests` passou.
- `python -m tests.test_genai_regression --expanded --baseline reports/expanded-regression-baseline.json`
  permite repetir o gate ampliado. O relatório desta revisão manteve **160/163**,
  com as três divergências conhecidas, sem reclassificá-las como aprovadas.
- Backend em contêiner descartável sem segredos, código e exemplos de contrato
  montados somente leitura, GenAI instalado e `python -m pytest -q -p no:cacheprovider`:
  **1.202 passaram, 114 skips**, um aviso de depreciação Starlette/httpx.
  Os skips incluem integrações PostgreSQL sem as URLs específicas de teste;
  a reconciliação real desta entrega foi feita separadamente no leitor Gold.
- Testes dirigidos de chat/sessão/continuação/histórico/visualização/exportação:
  **96 passaram** no mesmo tipo de contêiner.
- Em `frontend`, `npm test -- src/features/assistente src/shared/analytics/ChartBoundary.test.tsx`:
  **66 testes, 7 arquivos aprovados**. `npm run lint`, `npm run check:boundaries`,
  `npm run build` e Prettier da folha alterada passaram. O lint mantém dois
  avisos existentes de efeito React em AuthProvider e AssistentePage.
- Navegador local real, sessão admin, texto/valores/tabela/CSV, reabertura e
  acompanhamento conferidos. Em 375×812, log com 225 px e sem sobreposição;
  em 1024×768, log com 237 px e sem overflow horizontal de página. Desktop
  1440×900 também conferido. O tamanho temporário do navegador foi restaurado.
- `git diff --check` passou. `.env`, chaves e relatórios privados ficaram em
  caminhos ignorados. Nenhum commit, push ou PR é evidência desta revisão local.

## Limites preservados no aceite

O fechamento deste cartão atesta as correções e a revisão local descritas.
Cobertura mensal ausente, publicação sem amostra, exclusão não suportada e
operações fora do catálogo continuam com respostas explícitas. As três
divergências demonstrativas permanecem contadas e a indisponibilidade do
provedor permanece um resultado técnico separado de falta de evidência.
Revisões de spec e padrões usaram a base `5214aee` e os arquivos pendentes.
CI remoto depende de publicação posterior autorizada das alterações.
