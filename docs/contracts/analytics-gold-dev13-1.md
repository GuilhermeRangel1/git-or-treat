# DEV-13.1 — consumo da API Gold

Este contrato acompanha a [ADR-0021](../decisions/0021-api-gold-dev13-1.md), o [dicionário](../dicionario_gold.md) e o [plano](../plans/2026-10-28-dev13-1-gold-api-plano.md). Escopo: API de Panorama, fila/criação de Ordens e Operação. Não afirma aceite do portal ou reconciliação Databricks → CSV.

## Seleção e acesso

`ANALYTICS_SOURCE=gold` seleciona a publicação real; `synthetic` mantém a demonstração; `unavailable` falha fechado. Não há retorno silencioso a fixtures. A fonte não é selecionada pelo cliente da requisição.

O modo Gold exige identidade/permissão de leitura no servidor. O portal usa `ORDERS_AUTH_MODE=session`; CLI/Swagger pode usar credenciais privadas em `ORDERS_AUTH_MODE=service`. A permissão de leitura existente é reutilizada como contenção técnica, sem concluir autorização individual por área/território. `ORDERS_AUTH_MODE=demo` continua incompatível com Gold.

O portal autenticado usa o cookie HttpOnly `grid360_session`, conforme o [contrato de sessão](local-auth.md). O modo `session` rejeita credenciais Bearer; somente CLI/Swagger no modo `service` usa `Authorization: Bearer <credencial>`. Não colocar credenciais em `VITE_*`, exemplos com dados reais ou proxy. Banco e CSV não são acessados pelo navegador.

As rotas existentes selecionam o contrato conforme a fonte. Gold responde `metadata.contract_version = "2.0.0"`. Operação sintética mantém suas versões 1.0/1.1/1.2; a persistência operacional mantém o ciclo DEV-06/07. Não ativar a integração visual sem adaptar os decoders para Gold.

## Identidade e consistência

Respostas Gold trazem `metadata` com:

| Campo | Significado |
| --- | --- |
| `contract_version` | Versão do contrato HTTP, distinta da versão física |
| `status` | `available`, `partial`, `empty` ou `unavailable` |
| `source.kind` / `is_demo` | `gold` / `false` |
| `source.version` | Identificador do lote publicado |
| `source.updated_at` | Importação local; não equivale a processamento Gold nem fechamento mensal |
| `schema_version` | Contrato físico, atualmente `gold-csv-v2` |
| `fingerprint` | SHA-256 do inventário/conteúdo validado pelo carregador |
| `period` | Janela solicitada em análises mensais; `null` para a fila cadastral |
| `temporal_scope` | `monthly` ou `snapshot` |
| `filters` / `limitations` | Recorte aplicado e limites de interpretação |

Consultas de uma resposta usam um snapshot transacional consistente. Entre respostas, o cliente deve reenviar `expected_lote` **e** `expected_fingerprint`, recebidos nos metadados. Se a publicação divergir, HTTP 409 `stale_batch`; o cliente deve atualizar o conjunto relacionado, não juntar respostas de publicações diferentes. Só o nome do lote é insuficiente: a carga pode substituir conteúdo sob o mesmo rótulo.

Os leitores analíticos usam as tabelas de `gold_v2` e recusam publicação física v1 ou desconhecida. A tabela operacional compartilhada `gold_carga_atual` mantém sua localização. As etapas 1 e 2 alteram o destino físico e alinham as definições das métricas ao CSV v2; ativação e validação no lote real continuam pendentes.

Sem publicação, conexão ou esquema suportado: HTTP 503, sem SQL/credenciais na resposta. Entrada inválida e parâmetro sem suporte: HTTP 422. Campos indisponíveis usam `null` e motivo, nunca zero artificial. A carga atual é determinada por `gold_carga_atual`; a última tentativa pode ter falhado sem substituir a publicação válida.

## Panorama

`GET /api/v1/panorama`

Parâmetros: `competencia=YYYY-MM`, `comparacao=anterior|ano_anterior|nenhuma`, `municipio`, `classe`, `expected_lote`, `expected_fingerprint`. Município/classe globais usam `todos`/`todas`. Na Gold, competência omitida seleciona a competência mais recente observada, sem afirmar fechamento.

`data.metricas` conserva identificadores de produto onde a semântica é compatível e informa valor, unidade, definição, fórmula, estado e limitações. `valorAtual`, referência e variações podem ser nulos.

- `receitaFaturada`: receita de pares UC/mês com fatura e todas as leituras observadas válidas (`receita_base_comparavel_reais`). Não representa pagamento nem toda fatura da Silver.
- `energiaConsumida`: consumo dos mesmos pares UC/mês da receita comparável (`consumo_base_comparavel_kwh`). Totais independentes de receita e consumo não são combinados.
- `precoMedioEfetivo`: preço observado = soma da receita comparável / soma do consumo comparável; não é tarifa homologada. Consumo zero/ausente impede o quociente.
- `receitaPaga` e `energiaFaturada`: indisponíveis como grandezas independentes nesta exportação.
- `ucsAtivas`: identificador legado preservado; em Gold representa **UCs cadastradas no lote**, contagem distinta de `visao_360_uc.id_uc`, filtrada pelo município/classe cadastrais atuais. Inclui todos os status. Não representa UCs ativas históricas; não acompanha competência e não publica comparação mensal.
- `ucsFaturadasNoMes`: contagem distinta de `consumo_mensal_uc.id_uc` com `tem_fatura=true` na competência. Filtros dimensionais usam `LEFT JOIN` 1:1 com `visao_360_uc`, com dimensões ausentes como `Não informado`. Contagem inclui faturas sem leitura e não depende da base comparável financeira. Nunca soma contagens dimensionais. É um indicador complementar de cobertura de faturamento, não um cartão obrigatório específico de WEB-01.
- DEC/FEC: usam a mesma definição e cálculo de Operação; classe específica torna essas métricas indisponíveis, pois não há numeradores por classe. O filtro continua afetando as métricas financeiras.

Comparações são observadas, com a mesma definição e recorte nas duas competências. Base anterior zero admite diferença absoluta e percentual nulo; referência ausente não gera variação. Fechamento/completude não declarados ficam explícitos. Totais com contribuições ausentes são parciais; ausência integral de medida não é soma zero.

Receitas e preços preservam precisão decimal durante o cálculo das diferenças e percentuais. O arredondamento de apresentação ocorre depois: preços exibidos com duas casas não são os operandos da variação percentual. Valores válidos em `Numeric(38,2)` são suportados sem alterar o contexto decimal global; o contrato JSON numérico continua sujeito à precisão do cliente.

`statusComparacao` e `limitacoesComparacao` acompanham os números: valores presentes nas duas competências permitem diferenças observadas com estado parcial pela falta de comprovação de fechamento; contribuições realmente ausentes impedem a comparação da medida. `data.fechamentoMensalDeclarado=false` não certifica mês aberto nem fechado. `data.opcoesFiltros` informa listas reais de `competencias`, `municipios` e `classes`, obtidas na publicação.

A série mensal não preenche receita paga, energia faturada ou população ativa com valores de outra grandeza. Valores da série e dos KPIs devem ser interpretados com seus respectivos estados/limitações.

O insight atual é exclusivamente sintético e não passa a explicar números reais automaticamente. Em Gold, permanece indisponível até sua adaptação própria, com contexto recalculado pelo servidor.

## Fila e detalhe

`GET /api/v1/inspections/queue`

Filtros: município, bairro, classe e alimentador. Filtros são aplicados antes de ordenação/paginação; contagem e resumo cobrem o recorte filtrado inteiro. No Gold, `order_by=queue_position|uc_id|category`; `queue_position` usa `posicao_fila_inspecao` ascendente por padrão, com desempate estável por `id_uc`. Direção explícita `asc|desc` é aceita. `uc_id` continua disponível explicitamente; `category` ordena textualmente e desempata por UC. A ordenação sintética mantém seu contrato e padrão anteriores. Não se ordena por `ordem_prioridade_inspecao`, score ou recuperação.

`data.items` contém UC/território, categoria original, motivo, evidências tipadas e variação quando exportada. Média histórica é kWh por leitura, não necessariamente por mês. Categorias não afirmam fraude; a contagem irregular depende do resultado exato do dicionário. `REVISAR` continua categoria própria.

`potential_recoverable_energy_kwh = null`, com `recovery_unavailable_reason` derivado de `estado_estimativa_recuperacao` e estados preservados na evidência. Estados `BASE_INSUFICIENTE` e `CANDIDATO_REPROVADO_NA_VALIDACAO_TEMPORAL` explicam insuficiência ou reprovação do método; `ESTIMATIVA_UC_INDISPONIVEL` informa que há apenas referência histórica. Médias por inspeção e diferenças de consumo não são convertidas em recuperação individual. Os totais resumem categorias e a ausência de estimativa no recorte, sem pesos inventados.

`GET /api/v1/inspections/queue/{uc_id}` entrega detalhe, `rule_version`, limitações e os mesmos metadados de publicação. Uma UC ausente retorna 404; isso não apaga ordens históricas.

A fila é snapshot: `period = null`, `temporal_scope = snapshot`. Filtros de competência desconhecidos são recusados; não alteram agregados históricos de forma fictícia. Variação conserva P1 jul/2022–jun/2023 e P2 jul/2025–jun/2026, com meses observados; flag falsa pode coexistir com comparação indisponível.

## Criação e preservação operacional

`POST /api/v1/inspections/queue/{uc_id}/orders` conserva `Idempotency-Key`, autenticação de escrita e os campos anteriores. Para Gold, o payload inclui:

```json
{
  "source_version": "lote-recebido-no-detalhe",
  "source_fingerprint": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
  "rule_version": "gold-fila-inspecao-v1",
  "priority": "MEDIA",
  "notes": "Observação operacional opcional"
}
```

O exemplo é artificial. Copiar lote, fingerprint e regra do detalhe atual, não constantes do exemplo. Fingerprint é obrigatório para uma nova intenção Gold. Publicação/regra/UC obsoletas produzem conflito; nenhuma ordem parcial é criada.

Prioridade operacional BAIXA/MEDIA/ALTA é escolha da OS, distinta da categoria da Gold. Evidências de criação são congeladas como `snapshot_schema_version = "2"`; v1 e legado continuam válidos. Snapshot operacional não depende da validade futura dos DTOs analíticos.

No snapshot v2 de criação, o portal lê os nomes físicos mapeados do contrato Gold: `historical_recovery_mean_kwh_per_inspection`, limites inferior/superior, referência e estado históricos, além do estado e método da estimativa individual. Zero numérico é evidência válida; nulo ou estado indisponível não vira zero nem estimativa inventada. Motivo e categoria vêm do snapshot da ordem. Fingerprint, referência da suspeita, schema, lote e códigos técnicos permanecem acessíveis em proveniência recolhida, para não substituir o motivo e as evidências na leitura inicial. Snapshots legados continuam explicitamente identificados e não herdam dados de uma publicação corrente.

Reenvio da mesma intenção confirmada consulta o banco operacional antes de exigir a fonte atual. A adição de fingerprint opcional não deve alterar hashes históricos de intenções sintéticas que não o enviaram. Ordem ativa única por UC, controle otimista, transições, conclusão com resultado, cancelamento dedicado e histórico permanecem nos contratos DEV-06/07.

Recarga nova/repetida/falha não reescreve ordens, resultados, snapshots ou eventos. O lote antigo no snapshot é evidência histórica intencional, não sinal de que a tela analítica continua consultando essa publicação. Consulta, listagem e ciclo das ordens existentes não exigem a presença da UC na Gold atual.

## Operação

`GET /api/v1/operations/options` fornece `data.competencias`, `data.municipios` e `data.alimentadores` (`id`, `municipio`) observados na publicação. Município ausente permanece nulo no alimentador e nos pontos, sem excluir o alimentador; a lista de opções municipais contém somente valores conhecidos. Usa autenticação de leitura e metadados Gold v2 com `temporal_scope=snapshot` e `period=null`, além das guardas de lote/fingerprint. Fonte sintética retorna 422 `unsupported_source`; falhas de acesso ou disponibilidade não autorizam fallback. O catálogo orienta filtros e a seleção inicial da última competência observada, sem afirmar fechamento mensal.

Rotas: `/api/v1/operations/continuity`, `/series`, `/ranking`, `/summary` e `/feeders/{feeder_id}`.

Parâmetros de janela: `periodo=YYYY-MM` ou `competencia_inicio`/`competencia_fim`, sem combiná-los; demais limites continuam explicitados no OpenAPI. Filtros Gold: município/alimentador. Classe/bairro não são suportados, pois a fonte não segrega numeradores por essas dimensões. Não filtrar apenas o denominador.

Os pontos expõem duração em horas, frequência de pares UC–ocorrência, população cadastral e razões DEC/FEC, com competências observadas/ausentes. População é cadastro atual, sem vigência histórica provada. UCs interrompidas não são cobertura da fonte e não podem ser somadas como UCs únicas da janela.

Acumulado: soma dos numeradores / uma base por alimentador, se constante e válida e com todas as competências solicitadas observadas. Denominador variável, ausente/zero, numerador ausente ou mês faltante impede tratar o indicador como acumulado comparável. Mês sem linha não é zero de interrupções.

DEC e FEC têm elegibilidade independente: ausência de duração invalida DEC, sem remover FEC conhecido; ausência de frequência invalida FEC, sem remover DEC conhecido. Denominador ausente/inválido/variável e competência sem linha observada continuam invalidando ambos. Ranking exclui somente alimentadores sem o indicador solicitado.

Consolidado: para cada indicador, somar seu numerador nos alimentadores elegíveis e dividir pela soma de uma população por alimentador incluído. Bases excluídas são identificadas por indicador; nunca somar denominadores repetidos por mês nem calcular média simples de DEC/FEC. A resposta identifica denominador, alimentadores incluídos/excluídos e estado separadamente para DEC e FEC. Campos genéricos de denominador e IDs só representam base comum quando as populações coincidem; caso contrário, são nulos e a limitação registra a diferença. Resultados observados permanecem parciais quanto à completude da origem e não demonstram conformidade regulatória.

Ranking usa valor observado e desempate pelo ID do alimentador. Unidades sem base/janela comparável ficam excluídas. O detalhe traz série e resumo agregado; `occurrences = null`, `occurrences_status = unavailable`. Não há IDs/UCs/durações de ocorrências individuais na exportação, portanto não há paginação fictícia desses eventos.

Uma janela sem linhas observadas tem estado `empty` na continuidade, série, resumo e ranking, mesmo quando o alimentador existe no inventário da publicação. Observações sem denominador válido têm estado `unavailable`; zero observado com base válida mantém valor zero e estado `partial`, pois a fonte não certifica completude mensal.

## Capacidades fora desta fatia

Receita, UC 360 e KPIs antigos não se tornam consumidores Gold pela troca de configuração. Permanecem indisponíveis no modo Gold enquanto seus adaptadores não forem implementados. Campos ausentes identificados no mapeamento continuam dependências para o aceite integral WEB-01 a WEB-07.

Comandos, testes e reconciliação efetivamente executados devem constar na evidência da entrega e no Registro de progresso do PRD. Este contrato descreve comportamento esperado; não substitui essa prova.
