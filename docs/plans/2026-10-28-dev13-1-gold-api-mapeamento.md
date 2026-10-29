# DEV-13.1 — mapeamento da Gold para a API

Data: 28/10/2026. Natureza: preparação e proposta técnica; não implementa consumidores nem conclui requisitos. A prioridade solicitada é **Gold → PostgreSQL → API**, seguida da adaptação das telas. O [plano de execução](2026-10-28-dev13-1-gold-api-plano.md) depende deste mapeamento.

## Escopo e fontes

- Requisitos: WEB-01 a WEB-07; integração com DE-04, DE-05, DE-06 e DE-08. Dependências declaradas: DEV-02 a DEV-08 e DEV-12. A existência das entregas sintéticas não equivale a aceite Gold.
- Primeira entrega executável proposta: Panorama, fila que origina Ordens, persistência de Ordens e Operação na API. Receita e UC 360 são mapeadas como impacto transversal de WEB-02/03, sem prometer seu aceite nesta primeira fatia.
- Fontes: [PRD](../PRD.md), [dicionário](../dicionario_gold.md), [backend](../services/backend.md), [frontend](../services/frontend.md), [arquitetura do portal](../architecture/frontend.md), [contrato CSV](../contracts/gold-csv-v1.md), [catálogo analítico](../contracts/analytics-api.md), contratos DEV-05/06/07/08 e ADR-0015.
- Padrões aplicados: `backend-coding-standards` (camadas, consultas SQL e contratos), `frontend-coding-standards` (decoders, estado remoto e ausências) e `supabase-postgres-best-practices` (inspeção física). Nenhuma biblioteca ou arquitetura nova foi implementada.
- Base reiniciada em `origin/develop`, commit `026cb33`. O trabalho descartado não é base deste plano.

## Evidência observada no PostgreSQL

Consultas executadas em transação `READ ONLY` no contêiner `git-or-treat-db-dev131`, PostgreSQL 18, porta local `55432`, volume `git-or-treat_pgdata`. SQL reproduzível em [perfil somente leitura](2026-10-28-dev13-1-gold-api-perfil.sql). Não executar o contêiner original simultaneamente sobre esse volume. A porta 5432 estava indisponível na recarga anterior; esta inspeção não mudou a infraestrutura.

- `gold_carga_atual`: lote `GOLD_20261028T024507Z_7f5f4fda`, esquema `gold-csv-v1`.
- Série financeira: 48 competências, `2022-07` a `2026-06`; 43.954 UCs distintas em `consumo_mensal_uc`, frente a 45.000 no cadastro. Universo cadastral não equivale ao universo financeiro.
- Diagnóstico e bairro: receita acumulada de R$ 591.560.472,66 e consumo de 790.691.150 kWh em cada tabela. A comparação mensal das três tabelas financeiras encontrou 48 competências comuns e resíduos máximos de receita e energia iguais a zero. Isso comprova consistência interna desses agregados no banco; não reconcilia Delta → CSV nem API → portal.
- Continuidade: 5.856 linhas, 122 alimentadores, cada um com 48 meses observados. Nenhum alimentador apresentou mais de um denominador distinto no lote. A presença de linhas não comprova completude da fonte de ocorrências.
- Cadastro: 45.000 UCs com `status = ATIVA`; não há histórico de status mensal.
- Fila: 808 `ALTA - HISTORICO IRREGULAR`, 42.652 `MEDIA - NUNCA INSPECIONADO`, 517 `BAIXA`, 1.023 `REVISAR - SEM HISTORICO DE CONSUMO`. Não foram observados casos `ALTA - CONSUMO ZERO`; a categoria continua válida no contrato.
- Variação: somente 10.350 UCs têm 12 meses observados em ambas as janelas; 1.461 têm `variacao_pct` nula. Não assumir cobertura de 12 meses para as demais.
- Não foram encontrados registros mensais sem cadastro, nem UCs da fila sem Visão 360 ou sem variação. As PKs asseguram unicidade dos lados cadastrais usados nas junções.
- Banco operacional: zero ordens e zero eventos. Preservação de ordens preenchidas após recarga **não foi demonstrada**.

## Tabelas, chaves e destino

Os nomes físicos levam prefixo `gold_`. Usar `app.models.gold_load.TABLES`, `BATCH` e `ATTEMPTS`; `gold_v1.py` é snapshot histórico da migração, não o lugar para evoluir metadados atuais.

| Tabela lógica / linhas do lote carregado | Grão e chave | Campos úteis | Destino da API |
| --- | --- | --- | --- |
| `diagnostico_receita` / 4.694 | competência, município, classe, subgrupo, bandeira, GD | `receita_total_reais`, `consumo_total_kwh`, contagens, médias e preço efetivo | Panorama por mês/município/classe; futura Receita por dimensões disponíveis |
| `consumo_receita_bairro` / 51.862 | competência, município, bairro, classe | receita, consumo e contagem de UCs faturadas no mês | Receita territorial; fonte adequada para recortes por bairro |
| `consumo_mensal_uc` / 1.928.920 | `id_uc`, `competencia` | `consumo_kwh`, `receita_reais` | histórico UC; consultas especiais que precisem da UC e dimensões atuais |
| `fila_inspecao` / 45.000 | `id_uc` | dimensões atuais, prioridade textual, inspeções realizadas/irregulares, média por leitura | fila/detalhe e evidência congelada na criação de ordem |
| `visao_360_uc` / 45.000 | `id_uc` | cadastro, GD, agregados de atendimentos/interrupções, média por leitura | cadastro atual, população da rede e contexto UC; não eventos individuais |
| `variacao_consumo_uc` / 45.000 | `id_uc` | médias P1/P2, meses observados, diferenças, flag de queda | contexto adicional da fila/UC; comparação fixa, sem estimativa de recuperação |
| `indicadores_dec_fec` / 5.856 | `id_alimentador`, `competencia` | população, numeradores, UCs interrompidas, DEC e FEC | série, ranking, resumo e detalhe agregado de Operação |
| `gold_carga_atual` / registro único | `id = 1` | lote, fingerprint, esquema, importação e manifesto | identidade do conjunto publicado |
| `gold_carga_tentativas` | ID da tentativa | estado, início/fim e manifesto | diagnóstico da carga; tentativa falha não substitui identidade da carga atual |

`controle_gold` não é exportada. O manifesto de origem tem metadados de processamento/exportação; a API deve distinguir processamento Gold, exportação e importação local, sem inventar horário/fuso. Não tratar `importado_em` como fechamento da competência.

Existe ainda `gold_indicadores`, modelo anterior às sete tabelas CSV. Seus índices não comprovam índices nas novas tabelas e ela não deve ser usada como fonte substituta para este lote.

## Panorama: correspondência e revisão das métricas

Caminho atual: `GET /api/v1/panorama` → `get_panorama_repository` → `build_panorama` → listas sintéticas. A rota ainda escreve qualidade sintética, o serviço tem competência padrão `2024-04`, classe `Rural` adicionada manualmente e oito métricas obrigatórias. Alterar somente a dependência não resolve fórmulas, cobertura ou contrato.

| Contrato atual | Correspondência real | Tratamento proposto na API Gold |
| --- | --- | --- |
| `receitaFaturada` | soma de `diagnostico_receita.receita_total_reais` | Disponível no universo UC/mês com fatura **e** leitura; não é toda fatura da Silver nem arrecadação |
| `receitaPaga` | ausente | `null`, estado indisponível e motivo; não inferir pagamento de faturamento |
| `energiaConsumida` | soma de `consumo_total_kwh` | Consumo medido das UCs/mês elegíveis; explicitar cobertura restrita |
| `energiaFaturada` | ausente como medida independente | Indisponível; não copiar consumo medido para preencher o campo |
| `precoMedioEfetivo` | soma da receita / soma do consumo medido | Revisar definição e denominador para preço observado sobre consumo medido elegível; não usar média das tarifas dos grupos, nem afirmar tarifa homologada |
| `ucsAtivas` | cadastro atual em `visao_360_uc`; contagem financeira é outra medida | Não produzir série histórica de UCs ativas. Propor indicador separado `ucsFaturadasNoMes`; cadastro ativo só como snapshot atual com data/limitação |
| `continuidadeDec`, `continuidadeFec` | numeradores e denominadores de `indicadores_dec_fec` | Reutilizar definição de Operação; município/alimentador suportados, classe/bairro indisponíveis nessa tabela |
| série mensal | agregações por competência | Nulos e estados por medida; não transformar ausência em ponto zero |
| comparação | mês anterior, mesmo mês do ano anterior, nenhuma | Preservar essas modalidades no Panorama, com população/cobertura explícitas; ausência de referência ou base zero não gera percentual |

Recalcular médias ponderadas pela base correta: preço = receita/energia; ticket = receita/UCs faturadas; consumo médio = energia/UCs faturadas. Não somar contagens mensais para informar UCs distintas em uma janela. Se a pergunta exigir UCs únicas em vários meses, contar `DISTINCT id_uc` na base mensal elegível.

As competências observadas não fornecem declaração de fechamento/completude mensal. Expor a cobertura observada e a limitação; não declarar um mês completo apenas por existir. O padrão futuro deve ser derivado das competências publicadas e da política de cobertura, não da fixture.

O schema atual `PanoramaMetric.valorAtual` e todos os pontos de série exigem números. Será necessária revisão versionada para `null`, disponibilidade e motivos, inclusive no metadata. O frontend atual rejeita esses nulos; ativar Gold no ambiente compartilhado antes da adaptação do consumidor quebraria o decoder.

## Fila e Ordens: separar triagem de operação

Caminho atual: `/inspections/queue` e `/queue/{uc_id}` → `inspection_analytics` → regra `dev05-v1`, exclusivamente demonstrativa. A criação `/queue/{uc_id}/orders` consulta esse detalhe, valida `source_version`/`rule_version`, persiste snapshot e cria evento. `/orders/search`, detalhe, histórico e transições já usam banco operacional.

| Campo/capacidade | Gold | Revisão necessária |
| --- | --- | --- |
| UC e território | `id_uc`, `municipio`, `bairro`, `classe`, `alimentador` | Mapear diretamente preservando identificadores e grafias; opções de filtros vêm da fonte |
| motivo/prioridade | `prioridade_inspecao` | Expor categoria original, regra e evidências; remover a interpretação de score/probabilidade |
| evidências | contagens de inspeções e `media_consumo_historico` | Média é por leitura, não média mensal; contagem irregular usa resultado exato do dicionário |
| hierarquia Gold | histórico irregular → sem histórico → consumo zero sem solar → nunca inspecionado → baixa | Hierarquia de classificação não resolve automaticamente a ordem de despacho entre categorias. Proposta: definir ordenação explícita e estável; `REVISAR` requer tratamento próprio, sem conversão silenciosa para ALTA/MEDIA/BAIXA |
| score `priority`, pesos `signals.weight` | inexistentes | Revisar contrato para categoria/evidência sem peso inventado; eventual ordinal só para ordenação, identificado como decisão da API |
| energia recuperável | inexistente | `null` com motivo. Diferença de consumo, GD ou média histórica não comprova perda recuperável |
| variação de consumo | junção 1:1 com `variacao_consumo_uc` | P1 jul/2022–jun/2023, P2 jul/2025–jun/2026; expor meses observados; não reagir a um filtro temporal arbitrário como se a Gold fosse recalculada |
| prioridade da OS | `InspectionOrder.priority`: BAIXA/MEDIA/ALTA | Continua escolha operacional validada; distinguir da categoria de triagem. Não gravar texto longo da Gold nesse campo |
| snapshot | `OrderSnapshotV1` exige prioridade numérica | Propor snapshot v2 com categoria/evidências/lote; continuar lendo v1 e legado, sem reescrever JSON histórico |
| ordens existentes | tabelas `operational_*` | Listagem/histórico/transição não dependem da Gold atual; UC que desaparece na recarga não apaga ordem nem fundamentos |

Não importar inspeções históricas como novas ordens. Preservar idempotência, uma ordem ativa por UC, versão otimista e transação ordem+evento. Nova criação valida o lote/regra do detalhe; reenvio confirmado deve continuar resolvido pelo banco operacional antes de consultar Gold.

O cadastro/fila é snapshot sem período mensal de triagem. A API precisa identificar essa temporalidade, sem atribuir aos totais históricos a janela escolhida pelo usuário. Não forçar um período fictício para satisfazer `AnalyticsMetadata.period`.

## Operação: usar agregados, não reconstruir ocorrências

Caminho atual: `/api/v1/operations/{continuity,series,summary,ranking}` e `/feeders/{feeder_id}` → `operations`/`analytics.build_continuity` → listas de eventos e cobertura sintética. A Gold contém agregados, não essas listas.

- Por alimentador/mês: `duration_hours_sum` ← `duracao_total_interrupcoes_horas`; `interruption_count` ← `frequencia_total_interrupcoes`; `denominator_uc_count` ← `total_ucs_alimentador`; valores DEC/FEC correspondem à razão dos respectivos numeradores pela base.
- `ucs_interrompidas` é contagem distinta **do mês**. Não equivale a `covered_uc_count` da demonstração e não pode ser somada para obter UCs distintas em toda a janela. Não inventar cobertura por UC a partir de participação em eventos.
- Denominador é cadastro atual do alimentador, não cadastro histórico mensal nem necessariamente só UCs ativas. Não aplicar `status = 'ATIVO'` da fixture: o valor observado é `ATIVA`, e a regra do denominador deve seguir o dicionário.
- Para uma janela com denominador constante confirmado: somar numeradores mensais e dividir **uma vez** pela população do alimentador. Não dividir pela soma dos denominadores mensais, que produziria outra medida. Se houver denominador variável, não usar `MAX` como solução automática: tornar o acumulado indisponível até definir regra temporal.
- Consolidado: para alimentadores elegíveis na janela, soma dos numeradores / soma de uma base válida por alimentador, conforme proposta de extensão Gold da ADR-0015. Revisar e registrar essa extensão antes de apresentá-la como definição homologada.
- Os 122 alimentadores têm 48 linhas neste lote. Continuar distinguindo meses observados, inexistência de linhas e completude declarada. Próximas cargas podem ter lacunas; não preencher mês ausente com zero.
- Série e ranking podem avançar com a limitação do denominador atual explícita. Elegibilidade por cobertura precisa de regra documentada e evidência de origem; não reutilizar o status demonstrativo `available` sem revisão.
- Município e alimentador são filtros suportados. Classe/bairro não têm numeradores segregados: rejeitar filtro incompatível de forma explícita; não filtrar só o denominador e manter o numerador integral.
- O detalhe pode mostrar série e agregados reais. `event_id`, UC afetada, data individual e duração de cada ocorrência não existem na exportação. Coleção indisponível não é coleção vazia comprovada; revisar contrato/paginação do detalhe. Detalhe de ocorrências exige nova exportação aprovada.

## Consultas, junções e filtros

1. Panorama financeiro usa diagnóstico diretamente; bairro usa agregado territorial. Não unir diagnóstico e bairro por mês/município/classe: ambas têm múltiplas linhas e multiplicariam fatos.
2. Histórico mensal pode receber dimensões por `consumo_mensal_uc LEFT JOIN visao_360_uc USING (id_uc)`, com lado direito único. Registrar que as dimensões são atuais. Preservar faltantes em futuras cargas e mostrar a base sem dimensão, sem perder receita silenciosamente.
3. Fila pode receber variação/Visão 360 por `id_uc` em relações 1:1. Não unir diretamente à série mensal antes de paginar ou contar candidatos.
4. Continuidade deve agregar numeradores antes de juntar uma dimensão única de alimentador. Não unir cada alimentador/mês às UCs para somar os indicadores.
5. Lista/total/resumo usam os mesmos predicados SQL; paginação só limita itens. Desempate estável por UC, alimentador ou ID da ordem, conforme a entidade. Parâmetros de ordenação passam por lista permitida.
6. Filtros disponíveis devem ser derivados por capacidade, com relações município/bairro. Valor inexistente, combinação vazia, fonte indisponível e filtro não suportado são estados diferentes. Não aceitar filtro e ignorá-lo.
7. Consultas devem agregar/filtrar/paginar no PostgreSQL. Não carregar 1,93 milhão de registros para implementar o protocolo atual baseado em listas.

## Lote comum, composição e segurança

Proposta: criar contexto de leitura Gold com lote, esquema, fingerprint, horário local de importação e capacidades. Validar `BATCH`, não a última tentativa de carga. Fonte ausente/incompatível falha fechada; nenhum fallback sintético no modo Gold.

Uma transação de leitura com snapshot consistente deve abranger metadados e todas as consultas de uma resposta. A recarga é atômica, mas várias consultas em `READ COMMITTED` podem observar commits diferentes. Para leituras analíticas, propor transação `REPEATABLE READ`, somente leitura, no ciclo da requisição.

Entre requisições, só devolver o lote não impede mistura. Propor parâmetro opcional `expected_lote`: mismatch retorna 409 e manda recarregar o conjunto. Como a DEV-12 substitui tabelas, não há leitura histórica de lote anterior. A etapa de frontend deverá propagar essa expectativa entre resumo, ranking, detalhe e insight e invalidar caches após troca. Ordens são exceção intencional: o snapshot preserva o lote histórico da criação, sem passar a representar o lote atual.

Para criação de ordem, validar evidência e lote dentro da transação operacional. Avaliar trava compartilhada transacional na mesma chave de publicação da carga (`73460127`, exclusiva no importador), adquirida antes da leitura do lote, para serializar validação/gravação com recarga. Não tornar a transação inteira somente leitura, pois ela grava ordem e evento. A escolha e o tratamento de concorrência precisam de validação na implementação.

`ANALYTICS_SOURCE` hoje aceita apenas `synthetic`/`unavailable`; ambos os providers recusam outras fontes. Propor `gold` como modo explícito, com seleção por capacidade. Receita/UC/KPIs ainda não adaptados devem falhar explicitamente no modo Gold, sem continuar sintéticos ao lado de jornadas reais. Estender contratos específicos dos repositórios; não preencher as listas universais com fatos artificiais.

`ORDERS_AUTH_MODE=demo` exige fonte sintética. Não remover a trava para ligar Gold: API local pode usar o modo de serviço já previsto e produção continua exigindo OIDC. Leituras analíticas reais também precisam de política de acesso no servidor; autenticação das ordens não as protege automaticamente. Credenciais não devem ir para variáveis públicas do frontend.

O insight do Panorama atualmente aceita contexto sintético e usa energia faturada. Até adaptar métrica, lote e controles, deve ficar explicitamente indisponível em Gold. A adaptação é dependência transversal IA-04, não licença para continuar explicando números reais com contexto sintético.

## Índices e volume: o que existe e o que falta medir

Observado em `pg_indexes`: PK mensal `(id_uc, competencia)` e índice de competência; PKs dos dois agregados financeiros iniciadas por competência; PK de continuidade `(id_alimentador, competencia)`; PK por UC em fila, variação e cadastro. Ordens já têm índices de UC/status/prioridade, chave idempotente e índice parcial de UC ativa; histórico tem índice por ordem.

Ainda não foram executados benchmarks HTTP, `EXPLAIN (ANALYZE, BUFFERS)` ou testes concorrentes nesta etapa. Portanto, não se considera desempenho/paginação validados. Na implementação, medir consultas reais com e sem filtros, primeira/última página e resumo separado da página. Avaliar índice por competência na continuidade e índices de filtros/ordenação da fila somente se o plano justificar; 5.856 e 45.000 linhas podem admitir varreduras eficientes. Não adicionar índices por suposição nem alterar o snapshot da migração antiga.

## Impacto posterior no frontend

| Área | Arquivos de referência | Ajuste após estabilizar API |
| --- | --- | --- |
| Panorama | `shared/analytics/{types,panoramaContract,usePanoramaData}.ts`, `features/panorama/*`, `shared/filters/*` | aceitar nulos/estados, opções reais, período padrão, unidades/fórmulas, identidade de lote e insight indisponível |
| Inspeções → criação de ordem | `features/inspecoes/{contract,useInspectionQueue,CreateOrder,SuspicionDetail}.*` | categorias sem score fictício, recuperação ausente, janelas fixas e versão nova de evidência |
| Ordens | `features/ordens/{order-actions,OrderFoundationsDialog}.*`, `shared/api/orders.ts` | ler snapshot v2 e manter v1/legado; diferenciar triagem e prioridade da OS; preservar ciclo existente |
| Operação | `features/operacao/{contract,useOperations,operations-state,OperationDetail,OperationSource}.*` | contrato Gold, base cadastral, filtros suportados e ocorrências indisponíveis; lote esperado entre consultas |

Manter URL para filtros aplicados, TanStack Query para estado remoto, transporte compartilhado e validação runtime. Decoders atuais de Operação fixam versões `1.1.0`/`1.2.0`; prioridade e pesos da fila exigem números; Panorama exige oito números. Esses consumidores precisam mudar antes da ativação integrada. Não ajustar componentes nesta etapa.

## Lacunas e critérios que continuam abertos

| Item do checklist DEV-13.1 | Situação do mapeamento | Evidência necessária para concluir implementação |
| --- | --- | --- |
| tabelas/chaves/grãos/campos | mapeados acima | contratos Gold versionados e HTTP ligado ao banco |
| receita/energia/comparação/prioridade/recuperação/continuidade | diferenças identificadas; propostas explícitas | homologar definições que extrapolam o dicionário e sincronizar PRD/ADR quando aprovadas |
| campos indisponíveis | identificados | API com ausência explícita, sem zeros ou eventos inventados |
| filtros e agregações | consultas seguras propostas; reconciliação mensal interna executada | reconciliação independente por município/classe/bairro e através da API |
| paginação/desempenho/índices | índices inventariados, desempenho não medido | planos SQL, volume real, páginas e comportamento HTTP |
| preservação de ordens | estrutura separada identificada, banco vazio | cenário controlado com ordens preenchidas, recarga nova/repetida/falha e comparação de snapshots/eventos |

WEB-02 permanece limitado pela ausência de energia faturada independente e pagamento; WEB-03 pela ausência de detalhes de faturas, medidores, GD mensal e eventos individuais. WEB-04 não atende estimativa recuperável apenas com estas tabelas. WEB-06 não atende investigação de ocorrências individuais. Expor limitações permite integração útil, mas não conclui integralmente esses aceites; lacunas requerem nova fonte/Gold ou revisão de escopo aprovada.

Trello: consulta ao quadro oficial nesta rodada retornou recurso inexistente ou sem acesso. Sincronização pendente; nenhum cartão foi alterado.
