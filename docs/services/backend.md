# Serviço: backend e banco local

**Escopo:** sustenta WEB-01 a WEB-11 e IA-01 a IA-06 do [PRD](../PRD.md). **Estado:** API FastAPI, conexão SQLAlchemy, modelos ORM e migração Alembic existem. A DEV-01 acrescenta contratos analíticos e uma fonte sintética explícita; os requisitos funcionais seguem pendentes de Gold e aceite integrado conforme o PRD. **Stack atual:** Python 3.12 no Docker/CI, FastAPI, SQLAlchemy e PostgreSQL com driver psycopg 3; os testes HTTP usam SQLite.

## Responsabilidade

Importar tabelas Gold exportadas, servir recortes consistentes ao portal, manter estado das ordens de inspeção e disponibilizar acesso controlado ao agente. Gold é a fonte analítica; ordens/status/resultados digitados no portal são dados operacionais e devem ter modelo e trilha separados para não sobrescrever a extração.

As ordens têm persistência operacional inicial, separada da tabela `gold_indicadores`. As rotas analíticas têm contratos de consumo e podem consultar registros sintéticos relacionados, por interface injetável; ainda não leem Gold. `/ai/query` continua um placeholder e não comprova execução segura. A carga CSV não insere linhas nem implementa idempotência. O health check preserva a resposta atual e sinaliza falha de conexão no corpo. Swagger UI e ReDoc estão em `/docs` e `/redoc`.

## DEV-01: contratos antes da Gold

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

Para a fronteira com a GenAI, há uma proposta pendente de revisão para o Backend controlar as consultas Gold por um contrato estruturado, sem SQL livre do agente ([ADR-0002](../decisions/0002-genai-gold-query-owner.md)). A rota `/api/v1/ai/query` existente é apenas scaffold e ainda não consulta dados.

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

A API limita corpos a 64 KiB e JSON UTF-8 a 32 níveis, valida hosts e inclui headers defensivos. Essa proteção não substitui identidade de usuário e controle de acesso individual a ordens. WEB-05 ainda exige a jornada completa, vínculo com a versão da fila e auditoria durável; WEB-10 continua pendente. Preservar trilha de criação, alterações e cancelamento. Uma UC pode ser priorizada novamente; a regra para ordens simultâneas e repetição da mesma requisição deve ser explícita. Inspeções históricas do Excel não devem ser tratadas automaticamente como ordens novas do portal.

## Carga da Gold e consistência

O script `backend/scripts/load_gold.py` é um esqueleto: não carrega linhas CSV nem garante idempotência. Quando a ingestão for implementada, registrar lote, esquema e contagens por tabela; só disponibilizar consultas após validar consistência entre tabelas. A segunda execução do mesmo lote deve produzir os mesmos totais. Alterações na fórmula Gold exigem atualização coordenada do dicionário, API, portal, IA e diagnóstico. Testar o mesmo recorte no Databricks, banco local e resposta da API. Se o banco escolhido não suportar separação robusta de permissões, documentar controles compensatórios para o agente de IA antes de afirmar que consultas são somente leitura.

## Qualidade

DEV-06 liga a criação de ordens à fila DEV-05: valida versões, preserva UC/motivo e snapshot da suspeita, confirma commit e impede repetição concorrente por chave de idempotência e índice parcial de ordem ativa. Consulta por ID e busca paginada combinam filtros de estado, UC e prioridade. A migração `a6d060000001` preserva ordens anteriores com campos novos nulos. Veja o [contrato DEV-06, comandos e evidências](../contracts/inspection-orders-dev06.md). WEB-05 fica `Em validação`: auditoria durável das alterações, jornada completa do frontend e reconciliação Gold continuam pendentes.

Na revisão de integração com DEV-04/develop, a busca passou a projetar `OrderSummary` sem carregar JSON e a retornar páginas além do total antes de executar offset. O detalhe usa snapshot operacional v1 independente dos modelos analíticos, aceitando registros anteriores sem versão explícita. Reenvios que encontram uma gravação concorrente entre as consultas da chave e da suspeita ativa são reconciliados antes de emitir conflito.

A [ADR-0011](../decisions/0011-ordem-ativa-por-uc.md) alinha DEV-06/DEV-07: uma única ordem ativa por UC, inclusive criações manuais e versões distintas da suspeita. A migração `a6d060000002` recusa duplicidades antigas sem cancelamento automático e instala índice parcial por UC. Reenvio confirmado resolve somente o banco operacional, sem exigir fonte analítica; novas intenções continuam dependentes da fonte. Conflitos mantêm `detail` e acrescentam `error.code`, `error.message` e `error.order_id`. Testes de falha antes e depois do commit comprovam rollback ou recuperação sem duplicação conforme o caso.

A [ADR-0012](../decisions/0012-autenticacao-individual-das-ordens.md) acrescenta autenticação OIDC individual, scopes de leitura/escrita e identificação do operador nos eventos, com produção recusando credenciais compartilhadas. O proxy não autentica nem injeta tokens, e o Compose publica portas somente em localhost. `GET /inspections/access` fornece identidade opaca/permissões sem cache. Após a revisão de escopo solicitada pela pessoa usuária, login não é obrigatório na DEV-06: o modo explícito `demo` permite leitura/escrita sem Bearer exclusivamente em desenvolvimento com fonte sintética. Compose e script local selecionam esse modo; o ator `local-demo` não identifica uma pessoa. OIDC fica como preparação futura opcional. Veja o [guia de entrega para o frontend](../contracts/inspection-auth-handoff.md). Perfis das outras áreas e trilha durável completa não são concluídos por essa fatia.

Para DEV-05/WEB-04, o serviço `inspection_analytics` calcula apenas a [regra sintética versionada](../contracts/inspection-dev05.md). A fila aceita direção explícita e retorna opções de filtros; `/api/v1/inspections/queue/{uc_id}` expõe os insumos e limites da prioridade/projeção. Não há gravação, alteração de ordens ou migração. A regra demonstrativa recusa fonte não demonstrativa até homologação dos critérios reais.

Testar filtros combinados, estados vazios, UC inexistente, IDs inválidos, paginação, ordenação, idempotência da carga e transições das ordens. Quando houver alterações em métrica, fazer teste de contrato com amostra Gold reconciliada. Se PostgreSQL for escolhido, consultar a skill local `supabase-postgres-best-practices`; isso não impõe uso da plataforma Supabase.

WEB-11 pede testes automatizados como diferencial; a conclusão dos requisitos obrigatórios ainda requer verificação funcional e numérica reproduzível mesmo que esse diferencial não seja perseguido. Registrar no PRD quais fluxos e contratos foram testados, com comando/resultado e lote de dados.

### Comparação parcial do Panorama — DEV-02, 22/10/2026

`GET /api/v1/panorama` conserva os totais e a série de maio/2024 parcial. Se a competência atual ou de referência estiver incompleta, as oito métricas retornam `valorAnterior`, `variacaoAbsoluta` e `variacaoPercentual` nulos, com `baseZero: false`. A solicitação de comparação permanece em `filtros`; `periodoIncompleto` identifica a limitação da competência atual. Não se compara mês parcial com fechamento mensal completo.
