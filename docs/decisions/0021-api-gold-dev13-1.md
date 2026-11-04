# ADR-0021 — API analítica sobre a publicação Gold

**Data:** 28/10/2026. **Estado:** implementação técnica autorizada da DEV-13.1, com homologação de negócio e aceite integrado pendentes. Escopo desta rodada: API; telas em etapa posterior.

**Identificação:** renumerada de ADR-0018 para ADR-0021 em 31/10/2026 para preservar a ADR-0018 de janelas relativas GenAI já integrada à `develop`. Conteúdo e estado da decisão mantidos.

## Contexto

A DEV-12 publica sete tabelas em transação única e mantém `gold_carga_atual` como identidade da publicação. O dicionário chegou à `develop`, a Gold foi recarregada e o [mapeamento](../plans/2026-10-28-dev13-1-gold-api-mapeamento.md) identificou diferenças materiais frente aos contratos sintéticos.

Os providers atuais expõem listas em memória e fórmulas demonstrativas. Copiar consumo medido para energia faturada, traduzir categorias em scores ou reconstruir ocorrências a partir de agregados alteraria o significado da origem. Também não basta consultar o lote e os fatos em transações diferentes durante uma recarga.

## Decisão

Adotar modo explícito `ANALYTICS_SOURCE=gold`, sem fallback. Evoluir as rotas existentes por capacidade e publicar contratos Gold identificados pela versão `2.0.0`; preservar o comportamento sintético nas suas versões existentes. A configuração do ambiente seleciona a fonte; não há mistura de origens por conveniência de cada indicador.

Consultas Gold usam SQL para filtros, agregações, contagens e paginação. Metadados e fatos de uma resposta compartilham conexão/transação de leitura `REPEATABLE READ READ ONLY`. `source.version` identifica o lote; esquema físico e fingerprint são metadados distintos. `expected_lote` e `expected_fingerprint` detectam troca entre chamadas e retornam conflito em vez de consultar retrospectivamente tabelas já substituídas. A verificação do fingerprint é necessária também quando o carregador recebe conteúdo diferente sob o mesmo nome de lote.

Leituras Gold reutilizam o controle de identidade e permissão de leitura existente no servidor: sessão individual no portal e credenciais de serviço privadas apenas em CLI/Swagger no desenvolvimento. Essa contenção técnica não conclui perfis por área/território de WEB-10. O modo `demo` permanece restrito à fonte sintética. Credenciais não são adicionadas ao frontend ou ao proxy.

Panorama usa `receita_base_comparavel_reais` e `consumo_base_comparavel_kwh` para receita, consumo e preço; os totais financeiros independentes não são combinados nem usados como fallback. Preço observado é a razão da mesma base comparável, sem alegar tarifa homologada. Receita paga, energia faturada independente e população ativa histórica não são deduzidas. `ucsFaturadasNoMes` fica indisponível porque a Gold publica contagens distintas por grupo dimensional, sem IDs para deduplicar UCs entre linhas agregadas. Ausência de declaração de fechamento mensal fica explícita; comparações observadas não comprovam completude da origem.

A fila reproduz categoria, motivo e evidências da Gold, sem score ou energia recuperável inventados. Para CSV v2, a ordem padrão usa `posicao_fila_inspecao` ascendente, antes da paginação; `uc_id` e categoria textual continuam como opções explícitas. Isso preserva a posição calculada pela Gold e não aprova política de despacho ou ordenação por `ordem_prioridade_inspecao`. A prioridade operacional BAIXA/MEDIA/ALTA continua distinta da classificação de triagem. A variação da Gold conserva suas duas janelas fixas e contagens de meses observados.

A criação de ordem grava evidência operacional v2 independente dos DTOs analíticos em evolução. Ordem e evento continuam atômicos. A publicação usa trava exclusiva transacional; criação Gold usa a contraparte compartilhada na mesma transação que valida o lote e grava ordem/evento. Reenvio confirmado continua resolvido antes de exigir Gold. Snapshots v1/legados permanecem legíveis e não são reescritos por cargas novas.

Operação usa numeradores de `indicadores_dec_fec`, sem reconstruir eventos individuais. Acumulados usam uma população cadastral por alimentador quando constante e válida. DEC e FEC têm elegibilidade independente: o consolidado soma numeradores e uma base por alimentador elegível para cada indicador. Se as populações diferirem, os campos genéricos de base comum ficam nulos; bases e alimentadores específicos continuam explícitos. Falta de mês/base válida impede tratar a janela como comparável. Linhas observadas não provam completude da origem, e os resultados continuam simplificados, sem homologação regulatória. Esta extensão técnica da ADR-0015 não conclui DE-05 ou WEB-06.

## Alternativas consideradas

- Materializar as tabelas em listas para reaproveitar integralmente a demonstração: exigiria ler fatos desnecessários e manter definições incompatíveis com a exportação.
- Criar uma API paralela desvinculada dos providers atuais: aumentaria caminhos e regras duplicados. Foram mantidos pontos de composição existentes e DTOs específicos onde a semântica mudou.
- Preencher campos ausentes com zero ou outra grandeza: descartado por tornar o contrato numericamente enganoso.

## Consequências e limites

Os decoders atuais das telas não estão prontos para os contratos Gold. A API será verificada primeiro por HTTP; não ativar o perfil integrado como se a interface já tivesse sido adaptada. Receita, UC 360, KPIs antigos e insight não se tornam Gold automaticamente; capacidades sem implementação devem falhar explicitamente.

As lacunas de dados continuam nos requisitos originais. A aceitação desta implementação técnica não remove estimativa recuperável, ocorrências individuais ou energia faturada dos critérios de produto. Nova exportação ou revisão de escopo aprovada continua necessária para o que a Gold atual não sustenta.

## Fontes técnicas

Context7 não estava disponível na sessão. Foram consultadas as fontes primárias: [SQLAlchemy — conexões e isolamento](https://docs.sqlalchemy.org/en/21/core/connections.html), [PostgreSQL 18 — isolamento](https://www.postgresql.org/docs/18/transaction-iso.html) e [travas consultivas transacionais](https://www.postgresql.org/docs/18/functions-admin.html#FUNCTIONS-ADVISORY-LOCKS). Versões efetivamente executadas e resultados ficam na evidência da entrega; documentação não substitui teste de concorrência.


### Revisao de 31/10/2026: KPIs cadastrais e faturamento por UC

A limitacao anterior de UCs faturadas considerava apenas contagens dimensionais. A projecao `consumo_mensal_uc` traz IDs, competencia e `tem_fatura`: a API passa a contar UCs distintas nessa fonte, com filtros pelo cadastro unico de `visao_360_uc`. O identificador legado `ucsAtivas` representa em Gold a base cadastrada atual, rotulada UCs cadastradas no lote, incluindo todos os status e sem comparacao historica. Energia faturada permanece sem medida comprovada. Regras e evidencias: [mapeamento](../plans/2026-10-31-panorama-kpis-mapeamento.md).
