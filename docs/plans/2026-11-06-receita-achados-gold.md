# Receita — resumo sem duplicação e diagnóstico da Gold

Direção escolhida pela pessoa usuária em 06/11/2026: dados objetivos da Gold primeiro. Escopo WEB-02/WEB-07 e apoio a ENT-01; não conclui diagnóstico causal nem introduz síntese de IA.

- Remover os três cartões que repetem o gráfico e o texto genérico “A pergunta de Henrique”. Manter uma frase de variação, a comparação e um único gráfico com os valores exatos.
- Explicar “primeiro ano da base × 12 meses mais recentes” como contexto fixado pela publicação, exibindo datas reais. Não prometer janelas móveis se a publicação não as tiver. Editar competências apenas em Evolução mensal; Resumo/Investigar aplicam somente os recortes.
- Exibir achados calculados no recorte/publicação atuais: proporção do ganho de preço anulada pelo volume, concentração territorial/classe, evolução das UCs faturadas e comparação de consumo das UCs conectadas à GD com o grupo sem registro/cadastro negativo.
- Não copiar percentuais documentais para outros filtros. A análise GD usa os mesmos pares mensais e mínimo de seis pares do V3 e deve reconciliar o efeito-volume com o publicado. Expor insuficiência, base pequena e limitação causal, sem inventar geração/compensação ou tarifa homologada.
- Separar elegibilidade da variação financeira e dos efeitos: total financeiro pode ter percentual mesmo com algum efeito incompleto. Efeitos percentuais completos somente quando o componente está conhecido em todas as linhas. Não bloquear o agregado apenas porque há um subgrupo pequeno, desde que ao menos um grupo com cinco UCs garanta essa base mínima no universo.
- Consultas adicionais são opt-in (`include_diagnosis`), solicitadas somente pelo Resumo. Preservar os consumidores Mapa e a comparação mensal. Repositório consulta; serviço valida/calcula; DTO e decoder preservam o contrato.

## Sequência e verificações

1. Testes de regressão de percentuais independentes e do diagnóstico determinístico; implementar serviço/DTO e consulta de coortes/população, com testes de integração sobre Gold v2 artificial e SQL independente local.
2. Atualizar decoder e transporte; substituir o Resumo e delimitar os filtros, com testes de contexto, ausência e acessibilidade.
3. Rodar testes dirigidos e gates; verificar API real na publicação autorizada, sem divulgar valores absolutos/UCs. Conferir claro/escuro e mobile/desktop com fixture artificial.
4. Atualizar contratos, guias e PRD com os resultados observados; revisão independente final. Sem commit/push ou alteração de estado de aceite sem a evidência necessária.

Ficam fora: séries de energia gerada/compensada ausentes da Gold, tarifa homologada ausente, inferência causal identificada e estudo temporal pesado na requisição do portal. O estudo antes/depois já registrado permanece evidência documental de sua própria amostra; não vira texto fixo para todo recorte.

## Resultado da execução

- Implementado localmente, sem commit/push. A pessoa usuária também aprovou remover a aba mensal e manter histórico sob demanda. Permanecem apenas Resumo e Investigar; links antigos da evolução abrem o diálogo.
- `RevenueOverview` elimina a fileira de KPIs e o texto genérico do case. `RevenueFindings` apresenta achados derivados do retorno atual; `RevenueHistory` permite datas próprias sem perder refinamentos. Datas do diagnóstico são contexto e não controles editáveis; rótulos de primeiro ano/últimos 12 meses dependem da coincidência com o catálogo.
- `revenue_diagnosis.py`, métodos do repositório Gold, DTO e decoder publicam a extensão opt-in. O frontend carrega o detalhamento separadamente para que uma consulta mais demorada não bloqueie o gráfico; erro tem mensagem e repetição próprios. Mapa/consumidores padrão não executam o estudo extra.
- Comparação por GD reconcilia o efeito-volume pareado com V3 e calcula a participação negativa por classe/coorte antes de consolidar os grupos exibidos. Um teste com queda comercial e crescimento residencial no grupo sem GD impede compensação indevida entre classes.
- Verificações observadas: **64 testes Backend direcionados passaram** (diagnóstico, SQL real sobre fixture v2 isolada, decomposição, cobertura, HTTP e Mapa); Ruff dos novos serviços/DTO/endpoint/testes passou, compilação dos módulos de repositório e serviço legado passou. Os arquivos legados completos ainda apresentam avisos Ruff preexistentes fora das linhas novas.
- Frontend: **564 testes completos passaram** com dois workers; após refinamentos de rótulos, **51 testes dirigidos passaram**. Build, lint (dois avisos preexistentes fora de Receita), formatação e fronteiras passaram. Quatro jornadas Chromium artificiais passaram (1440/390 px, claro/escuro), com modal de método, drill-down, histórico, tabela inline, reload e sem overflow. Capturas locais de Resumo desktop e mobile foram inspecionadas; não são dados reais nem evidência de Gold.
- API autenticada real na publicação `GOLD_20261103T173853Z_76c37784`: total e residencial responderam com achados, coortes únicas e percentual financeiro elegível. Participação de GD no total e queda de consumo residencial entre janelas conferidas contra o baseline independente da investigação anterior, na mesma publicação. O default retornou diagnóstico nulo e preservou a consulta básica. A tentativa de nova leitura SQL direta foi interrompida por timeout de metadados Docker antes de abrir a consulta; não foi contada como controle bem-sucedido.
- Revisão independente foi solicitada, mas o agente revisor não pôde executar por limite de uso do serviço. Revisão própria de nulidade, contexto, filtros, cardinalidade, coortes e preservação dos consumidores foi realizada, incluindo o teste adicional citado acima. Não declarar revisão independente concluída nesta etapa.
- Trello: membro conectado, quadro canônico continua não encontrado/acessível. Sincronização pendente. WEB-02/WEB-07/ENT-01 conservam seus estados oficiais; esta revisão não homologa causas nem novos dados.
