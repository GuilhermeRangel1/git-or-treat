# Serviço: backend e banco local

**Escopo:** sustenta WEB-01 a WEB-11 e IA-01 a IA-06 do [PRD](../PRD.md). **Estado:** API FastAPI, conexão SQLAlchemy, modelos ORM e migração Alembic existem. A DEV-01 acrescenta contratos analíticos e uma fonte sintética explícita; os requisitos funcionais seguem pendentes de Gold e aceite integrado conforme o PRD. **Stack atual:** Python 3.12 no Docker/CI, FastAPI, SQLAlchemy e PostgreSQL com driver psycopg 3; os testes HTTP usam SQLite.

## Responsabilidade

Importar tabelas Gold exportadas, servir recortes consistentes ao portal, manter estado das ordens de inspeção e disponibilizar acesso controlado ao agente. Gold é a fonte analítica; ordens/status/resultados digitados no portal são dados operacionais e devem ter modelo e trilha separados para não sobrescrever a extração.

As ordens têm persistência operacional inicial, separada da tabela `gold_indicadores`. As rotas analíticas têm contratos de consumo e podem consultar a fonte sintética explícita; ainda não leem Gold. `/ai/query` continua indisponível e devolve 503 para entradas válidas, sem simular resultado Gold. As cargas v1 e v2 são transacionais, conforme os [contratos provisórios v1](../contracts/gold-csv-v1.md) e [v2](../contracts/gold-csv-v2.md); as rotas ainda não consomem as tabelas carregadas. O health check preserva a resposta atual e sinaliza falha de conexão no corpo. Swagger UI e ReDoc estão em `/docs` e `/redoc`.

## DEV-01: contratos antes da Gold

### Infraestrutura de carga — DEV-12

O carregador registra cada tentativa em `gold_carga_tentativas`, publica versão `gold-csv-v1`, contagens e controles em `gold_carga_atual` e confirma sucesso junto das sete tabelas em uma transação. Rejeições preservam a publicação anterior e mantêm auditoria sem valores dos registros. Migração `goldv1000002`, gerador de CSVs artificiais e [runbook de execução/recuperação](../contracts/gold-load-dev12.md). Isso completa a infraestrutura sintética DEV-12; DE-06 continua em andamento até reconciliação com a origem real. Adaptação de consultas e portal fica na DEV-13.

O [catálogo](../contracts/analytics-api.md), [desenho](../design/2026-10-20-dev01-design.md) e [ADR-0004](../decisions/0004-contratos-analiticos-e-fonte-sintetica.md) definem a fronteira entre fonte, serviços e HTTP. `ANALYTICS_SOURCE=synthetic` ativa explicitamente a demonstração; o padrão indisponível falha com 503. Os contratos incluem disponibilidade, unidade, competências, filtros efetivos, origem/versão e limitações. Zero legítimo não equivale a ausência.

O adaptador sintético não depende de PostgreSQL e não altera ordens. A implementação Gold futura precisa mapear os conceitos e reconciliar números; contratos provisórios da aplicação não definem colunas reais. Os contratos operacionais existentes e os endpoints de perguntas/insights do serviço IA permanecem preservados.

Nas ordens, endpoints HTTP validam os schemas de entrada/saída e delegam operações ao serviço, que recebe a sessão SQLAlchemy e usa os modelos ORM. `app/db/base.py` declara `Base` sem importar conexão; `app/core/database.py` configura engine, pooling, `SessionLocal` e `get_db`. Os modelos importam `Base` do módulo neutro, e Alembic carrega esses modelos para compor `target_metadata`. O import compatível `app.core.database.Base` permanece disponível.

A revisão posterior da DEV-01 explicita cobertura temporal da fonte de interrupções, mantendo-a separada da cobertura cadastral. Janelas desconhecidas não produzem zero disponível; janelas parcialmente observadas identificam o trecho usado. A busca/projeção das UCs fica no serviço, e a continuidade usa a validação comum de filtros. Veja os casos no [catálogo de contratos](../contracts/analytics-api.md).

A revisão Alembic `7c4a2b1e9d60` acrescenta defaults de inserção do servidor aos timestamps de ordens, sem mudar a migração inicial, nomes persistidos do enum ou atualização direta por SQL. O gate de migrações compara esquema/modelos após upgrade e testa PostgreSQL descartável com papel de migração sem superusuário. Banco com resíduos é recusado antes de qualquer alteração. Os caminhos host/Compose/testes e os comandos ficam no [README do backend](../../backend/README.md).

## Requisitos de produto e contratos ainda pendentes

DEV-03 implementada e verificada com fonte sintética: Receita usa o [contrato 1.1.0](../contracts/revenue-dev03.md), com snapshots dos extremos, cobertura financeira explícita, contagem de UCs, recortes e controles de reconciliação. As regras ficam em `app/services/revenue_analytics.py`, com repositório injetável e cálculos Decimal. A [ADR-0008](../decisions/0008-exploracao-demonstrativa-receita.md) registra as decisões provisórias; demais jornadas preservam seus contratos e as operações continuam separadas. Consulte [comandos, controles e pendências](../plans/2026-10-21-dev03-evidence.md). O método demonstrativo não homologa métricas Gold.

A DEV-04 implementa demonstrativamente WEB-03 segundo [contrato UC 1.1.0](../contracts/uc360-dev04.md), [plano](../plans/2026-10-22-dev04-plan.md) e [ADR-0009](../decisions/0009-uc360-contratos-de-consulta.md). Busca e detalhe DEV-01 preservam 1.0.0; overview e históricos por seção acrescentam comparação e paginação. Cobertura da UC por fonte, medida e período/snapshot é independente da presença de linhas. O serviço é responsável por comparação e resumo do universo filtrado; o repositório delimita acesso/paginação. Integração Gold, chaves reais e reconciliação continuam pendentes.

| Domínio | Operações necessárias | Condições de aceite |
| --- | --- | --- |
| Indicadores | Métricas agregadas, comparação temporal, filtros geográficos e por classe | Resposta inclui unidade, janela, filtros e metadados de atualização; reconcilia com Gold |
| Receita | Série e decomposição preço-volume | Valor total fecha com componentes; recortes não duplicam fatos |
| UC | Busca e resumo 360 | Histórico de consumo, fatura, medidor, GD, interrupções e chamados, com paginação e ausências claras |
| Inspeção | Listar fila, detalhar evidência, criar/alterar/cancelar ordem, registrar resultado | Prioridade explicável; validação e trilha de transições; idempotência para repetição |
| Operação | DEC/FEC por alimentador/período e ocorrências | Mesma fórmula da Gold, sem rótulo de conformidade regulatória |
| IA | Consulta controlada às Gold e trilha da resposta | Credencial somente leitura, allowlist de tabelas, limite/timeout de consultas |

O case não prescreve nomes de rota. A DEV-01 versiona contratos JSON, paginação, erros, tipos, nulidade e exemplos sem dados pessoais. A demonstração desses contratos não conclui as funcionalidades reconciliadas com Gold.

Para a fronteira com a GenAI, a decisão aprovada na [ADR-0002](../decisions/0002-genai-gold-query-owner.md) atribui ao Backend a execução exclusiva das consultas Gold por um contrato estruturado, sem SQL livre do agente. A aprovação define propriedade e fluxo; não significa que o adaptador ou a consulta Gold real estejam implementados ou autorizados. A rota `/api/v1/ai/query` existente é legado indisponível: valida o corpo e responde 503; não consulta dados, anuncia uma lista fictícia de tabelas nem fornece evidência.

Histórico de GENAI-01: a revisão documental de 25/10/2026 descreveu como proposta o fluxo planejar (GenAI) → revalidar e consultar (Backend) → sintetizar (GenAI), coordenado pelo Backend atrás de `POST /api/v1/ai/questions`, com papel somente leitura, revalidação do plano também no cache e auditoria da execução. A ADR-0002 foi aprovada em 25/10/2026 com base nos comentários de concordância de Backend e Engenharia de Dados no PR #54, sem Approve formal no GitHub. O [contrato](../contracts/genai-query-execution.md) continua preparação: nenhuma rota interna, adaptador ou consulta Gold foi implementada; P-04, DE-06, DE-08 e as dependências de catálogo, autorização e prazos seguem abertas. A [ADR-0016](../decisions/0016-priorizacao-melhorias-pre-gold.md) registra a priorização pré-Gold de 27/10/2026.

## Contrato conversacional com a GenAI

A preparação B3 acrescenta `app/services/genai_plan.py::validate_genai_plan` e o schema v1 independente em `app/schemas/genai_plan.py`. O Backend recalcula o fingerprint do plano validado, com defaults/nulos e canonicalização acordada, e rejeita plano inválido ou hash divergente. Vetores sintéticos compartilhados verificam compatibilidade com a GenAI. A função ainda não é chamada pelo fluxo HTTP atual; sua conexão à futura coordenação, junto de autorização, catálogo e lote, permanece pendente. Veja o [contrato B3](../contracts/genai-query-execution.md#revalidação-b3-no-backend--preparação).

Para a implantação Gold, a preparação B4 acrescenta `validate_gold_genai_plan`: além da B3, exige `source_id: gold.local` e `profile_id: v-energy-grid-360-gold`, alinhado ao catálogo do PR #73. A futura coordenação Gold deve usar esse validador e construir o escopo autorizado com o mesmo par. A composição HTTP atual permanece sem ativação Gold; veja os [limites da B4](../contracts/genai-query-execution.md#identidade-b4-da-integração-gold--preparação).

A preparação B1/B7 acrescenta `app/services/genai_publication.py::GoldPublicationContext`: captura publicação validada no servidor, fornece `batch_ref` ao planejamento e `expected_batch_ref` à síntese e disponibiliza um bloco PostgreSQL `REPEATABLE READ READ ONLY` para o futuro executor. Confere publicação antes e depois da consulta e antes da síntese, usando leitura nova fora do snapshot; a coordenação também deve conferir após a síntese antes de devolver resposta/cache. `GoldPublicationInvalid` não permite nova tentativa; `GoldPublicationChanged` permite reiniciar a requisição com captura e planejamento novos, sem repetição automática. Ambos mantêm a classe-base `GoldPublicationUnavailable`. O fluxo HTTP atual não utiliza esses controles; veja a [sequência e os limites](../contracts/genai-query-execution.md#publicação-b1b7-no-backend--preparação).

O Backend expõe `POST /api/v1/ai/questions` para o portal e encaminha a solicitação v1 ao `POST /api/v1/questions` do serviço GenAI. O endpoint antigo `/api/v1/ai/query` permanece separado e não é usado como rota de chat ou executor.

O Backend valida pergunta/contexto, aplica timeout, encaminha token interno e correlação, e valida o envelope de resposta antes de devolvê-lo. Não acessa SQL nem Gold nessa jornada. O contrato completo, limites, exemplos e erros estão em [genai-chat-api.md](../contracts/genai-chat-api.md). A integração é stateless e demonstrativa: não persiste sessão, não autentica usuário do portal e não concede escopo Gold. O token interno autentica Backend → GenAI; autorização real de usuário e retenção precisam ser decididas antes da implantação.

HTTP 503 da GenAI mantém indisponibilidade no contrato público. Envelope v1 válido e correlacionado preserva a política `retryable`; resposta genérica de proxy permite retentativa manual. Envelopes declarados inválidos continuam em 502 e detalhes privados não são encaminhados.

### Insight contextual do Panorama — IA-04

O portal envia filtros aplicados e `loteVersao` a `POST /api/v1/ai/insights`; nunca envia observações numéricas. O Backend valida o recorte com `build_panorama`, recalcula energia faturada na fonte corrente e deriva a variação percentual e, quando os filtros permitem, o município ou a classe que mais contribuiu para a mudança. Em seguida, encaminha o contexto estruturado a `POST /api/v1/insights` com o token de serviço e correlação. Antes de devolver um insight `answered`, confere se a GenAI retornou o mesmo período, filtros, métrica, unidade e observações calculados no servidor. Lote desatualizado retorna HTTP 409 `invalid_context`; indisponibilidade, timeout e resposta inválida têm envelopes v1 estáveis. Veja o [contrato Portal → Backend → GenAI](../contracts/panorama-insight-api.md).

Recorte sem registros retorna `no_evidence` com observações vazias antes da chamada à GenAI; zero observado em registros existentes continua elegível para interpretação. Os controles de filtro, lote e fonte são aplicados antes da decisão de ausência.

Na versão atual, o serviço só gera o contexto com a fonte sintética do Panorama; fonte não compatível falha fechada. Isso conecta o caminho da interface, mas não comprova Gold, autorização de usuário, auditoria persistida ou uma geração ao vivo de provedor. A evolução para Gold precisa revisar a métrica com o dicionário e continuar recalculando os valores no Backend.

O cálculo do Panorama recebe `PanoramaRepository`: a fonte informa `incomplete_periods`, versão, atualização e limitações do lote. O serviço usa essa cobertura para impedir comparação com competências abertas e gera rótulos da série a partir da competência, sem consultar constantes da fixture. O restante do cálculo ainda espera linhas agregadas em memória com o formato demonstrativo e fórmulas provisórias; o modo de implantação `ANALYTICS_SOURCE` aceita apenas `synthetic` ou `unavailable`. Um adaptador Gold precisa homologar grão e fórmulas, oferecer filtros válidos e preservar a mesma versão do lote entre indicadores e insight antes de ser habilitado.

### Envelope conceitual de uma resposta analítica

O contrato final pode variar, mas cada resposta que sustenta um número deve permitir identificar: valor e unidade; período/competências; filtros efetivamente aplicados; população/denominador; versão ou data do lote Gold; indicador de cobertura/qualidade; definição do dicionário; e estado de indisponibilidade. Expor metadados por resposta ou por um contrato comum, conforme decisão da equipe. Não inventar campos da extração para preencher o envelope.

| Caso | Decisão que o contrato precisa explicitar |
| --- | --- |
| Filtro por município/bairro/classe | IDs/nomes válidos, hierarquia de filtros, comportamento para combinação impossível e preservação da granularidade. |
| Competência e comparação | Inclusão dos extremos, janelas incompletas e diferença entre competência de fatura, data de pagamento e momento de atualização. |
| Busca de UC | Identificação estável, autorização para ver dados pessoais, histórico com páginas e resposta quando a UC não existe ou não tem certa fonte. |
| Exportação | Mesmo recorte/ordem da tela, limite de tamanho e metadados de geração, caso WEB-08 seja implementado. |
| Erros | Códigos e mensagens distinguem entrada inválida, ausência legítima, dependência indisponível e falha interna. |

## Regras de segurança e consistência

O contêiner usa `dhi.io/python:3.12-alpine3.24-dev`, base mantida pela Docker com zlib `1.3.2-r1` já corrigida para CVE-2026-85091, conforme a [ADR-0005](../decisions/0005-backend-python312-alpine.md). O CI constrói e testa a imagem com PostgreSQL descartável e aceita autenticação DHI por secrets quando necessária. A varredura é manual e deve examinar tanto a base quanto a imagem construída. Comandos, acesso ao registry e limites ficam no [README](../../backend/README.md#imagem-docker).

- Segredos via ambiente/gerenciador; nunca no frontend ou Git.
- Validação de entradas, parâmetros e escopo de filtros no servidor; consulta ao banco parametrizada.
- Garantir autorização de escrita das ordens; se WEB-10 for implementado, mapear perfis para leitura e ações.
- Separar usuário/credencial de leitura da IA do usuário de escrita operacional.
- Informar competência, atualização e proveniência nas respostas para evitar interpretações falsas.
- Erros não expõem SQL, stack trace, dados de terceiros ou credenciais ao navegador.

## Contenção de segurança e ciclo operacional das ordens

A [ADR-0007](../decisions/0007-contencao-seguranca-ordens-e-entradas.md) registra a contenção implementada após a auditoria: Bearer de serviço com leitura/escrita separadas e negação por padrão; PENDENTE inicia ou cancela, EM_ANDAMENTO conclui ou cancela, estados finais não reabrem. Conclusão exige resultado. ID, strings e prioridade são limitados no servidor, com atualização condicional por status para impedir sobrescrita de transição concorrente.

A API limita corpos a 64 KiB e JSON UTF-8 a 32 níveis, valida hosts e inclui headers defensivos. Essa proteção não substitui identidade de usuário e controle de acesso individual a ordens. WEB-05 permanece `Em validação`: a DEV-07 implementa o ciclo e o histórico operacional descritos a seguir, enquanto homologação e reconciliação com a Gold continuam pendentes. WEB-10 continua pendente. Preservar trilha de criação, alterações e cancelamento. Uma UC pode ser priorizada novamente; a regra para ordens simultâneas e repetição da mesma requisição deve ser explícita. Inspeções históricas do Excel não devem ser tratadas automaticamente como ordens novas do portal.

### DEV-07 — ciclo operacional das ordens

A [ADR-0014](../decisions/0014-integracao-do-ciclo-operacional-dev07.md) concilia o registro inicial do ciclo com a base DEV-06: PENDENTE inicia/cancela; EM_ANDAMENTO conclui com resultado/cancela; estados finais não reabrem. Prioridades BAIXA/MEDIA/ALTA. Repetições idênticas não gravam eventos nem incrementam versão.

A DEV-07 acrescenta histórico persistido com ator/versão, registro dedicado de resultado, cancelamento com confirmação da OS/UC e controle otimista no SQL. Ordem e evento são gravados na mesma transação. Todas as alterações exigem versão (422 se ausente/inválida, 409 se obsoleta); cancelamento via PATCH é recusado e usa rota dedicada. `alembic upgrade head` converge bancos existentes das duas branches sem recriação. Especificação, exemplos e limites estão no [contrato DEV-07](../contracts/inspection-lifecycle-dev07.md); evidências e ambiente estão no [registro da entrega](../plans/2026-10-25-dev07-evidencias.md). A execução de 25/10 validou a interface e a persistência com API real, consultas SQL independentes e PostgreSQL descartável. A fila continua sintética; não há reconciliação Gold nesta entrega.

## Carga da Gold e consistência

O script `backend/scripts/load_gold.py` importa as sete tabelas CSV v1 ou, com seleção explícita, as quinze tabelas analíticas do CSV v2. A migração `goldv2000001` mantém a v1 em `gold` e cria as tabelas v2 em `gold_v2`; as duas versões compartilham o registro de publicação e auditoria, e a carga mantém hashes, contagens e controles em uma transação. O leitor dedicado recebe `SELECT` apenas nas tabelas analíticas v1/v2; o schema do cadastro restrito não é concedido. Nenhuma carga ativa a fonte das rotas da API. O teste com o pacote real v2 em SQLite temporário e os limites estão no [contrato CSV v2](../contracts/gold-csv-v2.md). Postgres/Databricks no ambiente de destino, integração API/portal/GenAI e pacote cadastral continuam pendentes.

## Qualidade

DEV-06 liga a criação de ordens à fila DEV-05: valida versões, preserva UC/motivo e snapshot da suspeita, confirma commit e impede repetição concorrente por chave de idempotência e índice parcial de ordem ativa. Consulta por ID e busca paginada combinam filtros de estado, UC e prioridade; `has_result` opcional seleciona ordens com ou sem resultado antes da contagem e da paginação. A migração `a6d060000001` preserva ordens anteriores com campos novos nulos. Veja o [contrato DEV-06, comandos e evidências](../contracts/inspection-orders-dev06.md). WEB-05 fica `Em validação`: auditoria durável das alterações, homologação e reconciliação Gold continuam pendentes.

Na revisão de integração com DEV-04/develop, a busca passou a projetar `OrderSummary` sem carregar JSON e a retornar páginas além do total antes de executar offset. O detalhe usa snapshot operacional v1 independente dos modelos analíticos, aceitando registros anteriores sem versão explícita. Reenvios que encontram uma gravação concorrente entre as consultas da chave e da suspeita ativa são reconciliados antes de emitir conflito.

A [ADR-0011](../decisions/0011-ordem-ativa-por-uc.md) alinha DEV-06/DEV-07: uma única ordem ativa por UC, inclusive criações manuais e versões distintas da suspeita. A migração `a6d060000002` recusa duplicidades antigas sem cancelamento automático e instala índice parcial por UC. Reenvio confirmado resolve somente o banco operacional, sem exigir fonte analítica; novas intenções continuam dependentes da fonte. Conflitos mantêm `detail` e acrescentam `error.code`, `error.message` e `error.order_id`. Testes de falha antes e depois do commit comprovam rollback ou recuperação sem duplicação conforme o caso.

A [ADR-0012](../decisions/0012-autenticacao-individual-das-ordens.md) acrescenta autenticação OIDC individual, scopes de leitura/escrita e identificação do operador nos eventos, com produção recusando credenciais compartilhadas. O proxy não autentica nem injeta tokens, e o Compose publica portas somente em localhost. `GET /inspections/access` fornece identidade opaca/permissões sem cache. Após a revisão de escopo solicitada pela pessoa usuária, login não é obrigatório na DEV-06: o modo explícito `demo` permite leitura/escrita sem Bearer exclusivamente em desenvolvimento com fonte sintética. Compose e script local selecionam esse modo; o ator `local-demo` não identifica uma pessoa. OIDC fica como preparação futura opcional. Veja o [guia de entrega para o frontend](../contracts/inspection-auth-handoff.md). Perfis das outras áreas e trilha durável completa não são concluídos por essa fatia.

Para DEV-05/WEB-04, o serviço `inspection_analytics` calcula apenas a [regra sintética versionada](../contracts/inspection-dev05.md). A fila aceita direção explícita e retorna opções de filtros; `/api/v1/inspections/queue/{uc_id}` expõe os insumos e limites da prioridade/projeção. Não há gravação, alteração de ordens ou migração. A regra demonstrativa recusa fonte não demonstrativa até homologação dos critérios reais.

Testar filtros combinados, estados vazios, UC inexistente, IDs inválidos, paginação, ordenação, idempotência da carga e transições das ordens. Quando houver alterações em métrica, fazer teste de contrato com amostra Gold reconciliada. Se PostgreSQL for escolhido, consultar a skill local `supabase-postgres-best-practices`; isso não impõe uso da plataforma Supabase.

WEB-11 pede testes automatizados como diferencial; a conclusão dos requisitos obrigatórios ainda requer verificação funcional e numérica reproduzível mesmo que esse diferencial não seja perseguido. Registrar no PRD quais fluxos e contratos foram testados, com comando/resultado e lote de dados.

### Comparação parcial do Panorama — DEV-02, 22/10/2026

`GET /api/v1/panorama` conserva os totais e a série de maio/2024 parcial. Se a competência atual ou de referência estiver incompleta, as oito métricas retornam `valorAnterior`, `variacaoAbsoluta` e `variacaoPercentual` nulos, com `baseZero: false`. A solicitação de comparação permanece em `filtros`; `periodoIncompleto` identifica a limitação da competência atual. Não se compara mês parcial com fechamento mensal completo.

## DEV-08: Operação demonstrativa

O backend amplia a continuidade DEV-01 com série mensal, ranking por DEC/FEC e detalhe paginado de ocorrências. Fórmula, cobertura e denominador são compartilhados com a rota existente; janelas parciais e denominadores ausentes/zero não competem no ranking. As novas respostas incluem definição, numeradores, janela observada e alternativa textual. Veja o [contrato e controles DEV-08](../contracts/operations-dev08.md). O portal integra essas respostas em `/operacao`; não houve alteração de banco. Integração DE-05/Gold e aceite completo WEB-06/WEB-07 permanecem pendentes.

O endpoint `GET /api/v1/operations/summary` consolida apenas alimentadores `available` em toda a janela. DEC e FEC usam numeradores originais agregados e a soma dos denominadores incluídos; arredondam apenas o resultado final. Exclusões deixam o estado `partial`; uma fonte sem alimentadores é `empty`, e sem elegíveis é `unavailable` com numeradores/indicadores/denominador nulos. Apenas essa resposta usa contrato 1.2.0; a continuidade 1.0.0 e as consultas DEV-08 1.1.0 permanecem preservadas.

Na revisão DEV-08, todas as rotas de Operação passaram a recusar parâmetros desconhecidos/duplicados e a devolver `Cache-Control: no-store`, inclusive em erros. O cálculo compartilhado recusa denominador não inteiro positivo e determina cobertura pelas contagens exatas, evitando elegibilidade indevida no ranking por arredondamento. Autorização individual das leituras analíticas permanece pendente para dados reais.

A refatoração de alinhamento DEV-08 move a composição e paginação do detalhe para `build_feeder_detail`, com resposta tipada. As rotas de Operação retornam modelos explícitos; `StrictAnalyticsRoute` fica na fronteira HTTP comum. Receita e Operação compartilham `repeated_query_parameters`, preservando seus contratos e políticas de erro.

## Preparação da identidade de publicação Gold — 28/10/2026

O Backend passa a validar a origem do manifesto e persistir a origem e `publication_id`, derivando deles o `batch_ref`. A identidade permanece em repetição e muda atomicamente em nova publicação. O schema analítico e o papel de leitura seguem a ADR-0017; [manifesto e compatibilidade](../contracts/gold-csv-v1.md#origem-e-publicação) e [migração, permissões e recuperação](../contracts/gold-load-dev12.md#preparação-para-genai-01-schema-origem-e-publicação) descrevem o uso. O campo nos envelopes GenAI, os endpoints de planejar/sintetizar e o executor de consultas de negócio continuam pendentes. Esta preparação não ativa a fonte real nem conclui GENAI-01 ou requisitos IA/DE.


### Preparação B6 de prazo compartilhado

`app/services/genai_deadline.py::GenAIRequestDeadline` oferece prazo monotônico por requisição, limites de etapas pelo tempo restante e cálculo de timeout SQL em milissegundos sem zero. O futuro coordenador deve fornecer os valores acordados e aplicar os limites no transporte e no executor. O componente ainda não está conectado à rota HTTP, não altera os 35 segundos por chamada existentes e não comprova cancelamento de SQL ou prazo ponta a ponta. Veja o contrato de consulta, seção Prazo B6 compartilhado.


### Preparação B9 de despacho da síntese

`app/services/genai_flow.py::should_synthesize` exige seleção explícita da política proposta `completed_lookup`. Lookups concluídos válidos podem seguir à síntese; respostas de planejamento sem plano e falhas de execução encerram o fluxo. Lookup inválido é recusado, sem confundir erro com ausência. Schema de lookup em `app/schemas/genai_evidence.py`; helper sem chamadas HTTP e sem ativação na aplicação. Confirmação com GenAI, validação das demais fronteiras e coordenador permanecem pendentes.


### Preparação B11 de compatibilidade interna

`app/schemas/genai_internal.py` descreve os envelopes internos v1, reutilizando pergunta/resposta públicas, plano B3 e lookup B9. `app/services/genai_contracts.py` confere respostas contra versão, conteúdo e correlação do corpo/cabeçalho. Vetores compartilhados com a suíte GenAI, teste HTTP de recusa de escopo enviado pelo portal e prova do núcleo sem modelo para ausência/esclarecimento verificam as fronteiras preparadas. Clientes e rotas internas, coordenador, executor e teste ponta a ponta continuam pendentes; não ativa a Gold ou confirma B6/B9.


### GENAI-01 — finalização contratual v2

O pacote final usa referências `gold-csv-v2`, independentes do envelope interno v1. As requisições internas de plano e síntese exigem `remaining_timeout_ms` (inteiro estrito de 1 a 35.000). O Backend é a autoridade do prazo global de 35 s e limita SQL a 5 s; o helper `GenAIRequestDeadline.remaining_timeout_ms` fornece o saldo sem renovar o relógio. O contrato de consulta descreve atualização conjunta dos consumidores e despacho `completed_lookup`. Os controles ainda precisam ser ligados ao cliente, executor e coordenador; o endpoint público continua sem consulta Gold nesta fatia.


### Prontidão de atendimento observada no banco — GENAI-02

`observe_attendance_readiness` lê o snapshot v2 e recalcula C14/C15 com aprovação de regra explícita, vinculados à publicação efetiva. `evaluate_attendance_readiness` usa o transporte GenAI existente, valida versão/estados/lote e revalida a publicação após o HTTP. A CLI `scripts/check_gold_readiness.py` executa essa fronteira com credencial de leitura; o chat público ainda não a chama. A migração `goldv2000002` expõe somente IDs de linhagem em `gold.publicacao_linhagem` e o provisionador concede SELECT nessa view, sem abrir a tabela operacional de carga. Controles e cobertura não certificada permanecem distintos. Operação, limites de prazo, parâmetros e evidência privada estão em [gold-readiness.md](../gold-readiness.md).


### Prontidão dos quatro domínios — continuação GENAI-02

`observe_domain_readiness` amplia a observação de atendimento no mesmo snapshot para receita, consumo e continuidade. Os cálculos por controle ficam em `gold_domain_controls`, sem novo orquestrador. `evaluate_domain_readiness` usa a coordenação HTTP e prazo existentes; `check_gold_readiness.py --scope domains` é o chamador operacional. O padrão `attendance` permanece compatível. A ampliação não herda aprovações anteriores: somente os IDs explicitamente aceitos pelo operador são aprovados, e sucesso técnico não certifica a fonte. A [matriz de prontidão](../gold-readiness.md#controles-dos-quatro-domínios-na-publicação-v2) distingue controles internos, cobertura e conferência externa.


Os chamadores de prontidão podem fornecer `expected_batch_ref` para vincular a avaliação à publicação do recorte que já conhecem. O contrato existente valida o formato antes de I/O e distingue referência inválida de publicação trocada; ambos impedem HTTP GenAI. A CLI aceita `GOLD_READINESS_EXPECTED_BATCH_REF` opcional. Omitir a referência apenas fixa a publicação corrente no início; não comprova identidade com uma tela já exibida. A integração de um consumidor real deve obter a referência no servidor e propagá-la.


A publicação v2 acrescenta janelas e estados observados em `gold_carga_atual.manifesto.coverage_windows`, calculados na mesma transação. São metadados internos não certificadores, opcionais em publicações anteriores. O contrato CSV de entrada não mudou; repetição idempotente mantém a identidade e os metadados anteriores. A cobertura que governa a prontidão permanece na tabela detalhada. Testes do importador público cobrem repetição, troca de publicação e falha no último CSV com rollback de todas as tabelas e auditoria persistida.


### Catálogo físico Gold v2 para o executor

`app.services.gold_catalog.load_gold_catalog()` disponibiliza o artefato interno versionado `app/catalogs/gold_v2.json` e o valida contra os modelos Gold v2 instalados. A seleção de fonte confere capacidades, dimensões, granularidade e histórico acumulado sem datas. Onze métricas cobrem a primeira adaptação; o [catálogo](../gold-catalog.md) detalha fórmulas e limites. Não há import do pacote GenAI, endpoint novo ou execução SQL. O coordenador futuro precisa revalidar plano, autorização, publicação e prontidão reais; este carregador não concede acesso por descobrir schema.

O artefato inclui nomes e definições de negócio e operadores por dimensão, iguais aos do perfil lógico. Payload candidato só é aceito quando coincide com a definição distribuída, além de respeitar o schema: trocar um denominador por outra coluna numérica ou remover uma dependência de prontidão é drift semântico. O artefato faz parte do código confiável e versionado, sem substituição por conteúdo do portal/modelo ou descoberta automática de schema. Sua existência não significa que perguntas/insights já o carreguem na composição de produção.

O carregador também confere dimensões e competências textuais, timestamp de atendimento com fuso e precisão/escala das colunas monetárias. `select_catalog_source()` revalida o catálogo recebido antes de usá-lo, evitando confiar em mapas internos que possam ser alterados após o carregamento (`frozen=True` não torna dicionários aninhados imutáveis). Continua sem executar SQL ou substituir a autorização e a conferência de publicação do futuro coordenador.

O artefato declara o limite datado de até 1.830 dias por métrica; a política do planejador ainda pode impor teto menor. DEC/FEC só aceitam mês, e métricas acumuladas recusam janela de calendário. O seletor Backend reproduz o limite antes de devolver a fonte.
