# Serviço: backend e banco local

**Escopo:** sustenta WEB-01 a WEB-11 e IA-01 a IA-06 do [PRD](../PRD.md). **Estado:** API FastAPI, conexão SQLAlchemy, modelos ORM e migração Alembic existem. A DEV-01 acrescenta contratos analíticos e uma fonte sintética explícita; os requisitos funcionais seguem pendentes de Gold e aceite integrado conforme o PRD. **Stack atual:** Python 3.12 no Docker/CI, FastAPI, SQLAlchemy e PostgreSQL com driver psycopg 3; os testes HTTP usam SQLite.

## Responsabilidade

Importar tabelas Gold exportadas, servir recortes consistentes ao portal, manter estado das ordens de inspeção e disponibilizar acesso controlado ao agente. Gold é a fonte analítica; ordens/status/resultados digitados no portal são dados operacionais e devem ter modelo e trilha separados para não sobrescrever a extração.

As ordens têm persistência operacional inicial, separada da tabela `gold_indicadores`. As rotas analíticas têm contratos de consumo e podem consultar registros sintéticos relacionados, por interface injetável; ainda não leem Gold. `/ai/query` continua um placeholder e não comprova execução segura. A carga CSV não insere linhas nem implementa idempotência. O health check preserva a resposta atual e sinaliza falha de conexão no corpo. Swagger UI e ReDoc estão em `/docs` e `/redoc`.

## DEV-01: contratos antes da Gold

O [catálogo](../contracts/analytics-api.md), [desenho](../design/2026-10-20-dev01-design.md) e [ADR-0002](../decisions/0002-contratos-analiticos-e-fonte-sintetica.md) definem a fronteira entre fonte, serviços e HTTP. `ANALYTICS_SOURCE=synthetic` ativa explicitamente a demonstração; o padrão indisponível falha com 503. Os contratos incluem disponibilidade, unidade, competências, filtros efetivos, origem/versão e limitações. Zero legítimo não equivale a ausência.

O adaptador sintético não depende de PostgreSQL e não altera ordens. A implementação Gold futura precisa mapear os conceitos e reconciliar números; contratos provisórios da aplicação não definem colunas reais. Os contratos operacionais existentes e os endpoints de perguntas/insights do serviço IA permanecem preservados.

Nas ordens, endpoints HTTP validam os schemas de entrada/saída e delegam operações ao serviço, que recebe a sessão SQLAlchemy e usa os modelos ORM. `app/db/base.py` declara `Base` sem importar conexão; `app/core/database.py` configura engine, pooling, `SessionLocal` e `get_db`. Os modelos importam `Base` do módulo neutro, e Alembic carrega esses modelos para compor `target_metadata`. O import compatível `app.core.database.Base` permanece disponível.

## Requisitos de produto e contratos ainda pendentes

| Domínio | Operações necessárias | Condições de aceite |
| --- | --- | --- |
| Indicadores | Métricas agregadas, comparação temporal, filtros geográficos e por classe | Resposta inclui unidade, janela, filtros e metadados de atualização; reconcilia com Gold |
| Receita | Série e decomposição preço-volume | Valor total fecha com componentes; recortes não duplicam fatos |
| UC | Busca e resumo 360 | Histórico de consumo, fatura, medidor, GD, interrupções e chamados, com paginação e ausências claras |
| Inspeção | Listar fila, detalhar evidência, criar/alterar/cancelar ordem, registrar resultado | Prioridade explicável; validação e trilha de transições; idempotência para repetição |
| Operação | DEC/FEC por alimentador/período e ocorrências | Mesma fórmula da Gold, sem rótulo de conformidade regulatória |
| IA | Consulta controlada às Gold e trilha da resposta | Credencial somente leitura, allowlist de tabelas, limite/timeout de consultas |

O case não prescreve nomes de rota. A DEV-01 versiona contratos JSON, paginação, erros, tipos, nulidade e exemplos sem dados pessoais. A demonstração desses contratos não conclui as funcionalidades reconciliadas com Gold.

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

- Segredos via ambiente/gerenciador; nunca no frontend ou Git.
- Validação de entradas, parâmetros e escopo de filtros no servidor; consulta ao banco parametrizada.
- Garantir autorização de escrita das ordens; se WEB-10 for implementado, mapear perfis para leitura e ações.
- Separar usuário/credencial de leitura da IA do usuário de escrita operacional.
- Informar competência, atualização e proveniência nas respostas para evitar interpretações falsas.
- Erros não expõem SQL, stack trace, dados de terceiros ou credenciais ao navegador.

## Ordens de inspeção: ciclo operacional a decidir

WEB-05 exige criar, atualizar status, registrar resultado e cancelar. Antes de implementar, definir estados permitidos, transições, quem pode executá-las, campos mínimos e vínculo com a versão da fila que motivou a ordem. Preservar trilha de criação, alterações e cancelamento. Uma UC pode ser priorizada novamente; a regra para ordens simultâneas e repetição da mesma requisição deve ser explícita. Inspeções históricas do Excel não devem ser tratadas automaticamente como ordens novas do portal.

## Carga da Gold e consistência

O script `backend/scripts/load_gold.py` é um esqueleto: não carrega linhas CSV nem garante idempotência. Quando a ingestão for implementada, registrar lote, esquema e contagens por tabela; só disponibilizar consultas após validar consistência entre tabelas. A segunda execução do mesmo lote deve produzir os mesmos totais. Alterações na fórmula Gold exigem atualização coordenada do dicionário, API, portal, IA e diagnóstico. Testar o mesmo recorte no Databricks, banco local e resposta da API. Se o banco escolhido não suportar separação robusta de permissões, documentar controles compensatórios para o agente de IA antes de afirmar que consultas são somente leitura.

## Qualidade

Testar filtros combinados, estados vazios, UC inexistente, IDs inválidos, paginação, ordenação, idempotência da carga e transições das ordens. Quando houver alterações em métrica, fazer teste de contrato com amostra Gold reconciliada. Se PostgreSQL for escolhido, consultar a skill local `supabase-postgres-best-practices`; isso não impõe uso da plataforma Supabase.

WEB-11 pede testes automatizados como diferencial; a conclusão dos requisitos obrigatórios ainda requer verificação funcional e numérica reproduzível mesmo que esse diferencial não seja perseguido. Registrar no PRD quais fluxos e contratos foram testados, com comando/resultado e lote de dados.
