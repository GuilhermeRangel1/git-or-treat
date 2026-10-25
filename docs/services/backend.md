# Serviço: backend e banco local

**Escopo:** sustenta WEB-01 a WEB-11 e IA-01 a IA-06 do [PRD](../PRD.md). **Estado:** API FastAPI, conexão SQLAlchemy, modelos ORM e migração Alembic existem; os requisitos funcionais seguem pendentes conforme o PRD. **Stack atual:** Python 3.12, FastAPI, SQLAlchemy e PostgreSQL com driver psycopg 3; os testes HTTP usam SQLite.

## Responsabilidade

Importar tabelas Gold exportadas, servir recortes consistentes ao portal, manter estado das ordens de inspeção e disponibilizar acesso controlado ao agente. Gold é a fonte analítica; ordens/status/resultados digitados no portal são dados operacionais e devem ter modelo e trilha separados para não sobrescrever a extração.

As ordens têm persistência operacional inicial, separada da tabela `gold_indicadores`. As rotas analíticas têm contratos e adaptador sintético; IA é scaffold. Nenhuma lê dados Gold. A carga CSV não insere linhas nem implementa idempotência. O health check preserva a resposta atual e sinaliza falha de conexão no corpo. Swagger UI e ReDoc estão em `/docs` e `/redoc`.

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

O case não prescreve nomes de rota. As rotas HTTP iniciais já existem, mas seus contratos analíticos são placeholders, não funcionalidades concluídas. Definir e versionar contratos JSON, paginação, erros, tipos, nulidade e exemplos sem dados pessoais junto do frontend e agente.
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

- Segredos via ambiente/gerenciador; nunca no frontend ou Git.
- Validação de entradas, parâmetros e escopo de filtros no servidor; consulta ao banco parametrizada.
- Garantir autorização de escrita das ordens; se WEB-10 for implementado, mapear perfis para leitura e ações.
- Separar usuário/credencial de leitura da IA do usuário de escrita operacional.
- Informar competência, atualização e proveniência nas respostas para evitar interpretações falsas.
- Erros não expõem SQL, stack trace, dados de terceiros ou credenciais ao navegador.

## Ordens de inspeção: DEV-05, DEV-06 e DEV-07

A base do backend DEV-06 (`85a72a0`) foi incorporada nesta branch: fila/detalhe sintéticos DEV-05, criação pela fila com snapshot/fingerprint/idempotência, consulta paginada, controle de acesso e índice único por UC ativa. Analytics têm adaptador sintético explícito e não consultam Gold; IA permanece scaffold.

WEB-05 segue Em validação. A [ADR-0014](../decisions/0014-integracao-do-ciclo-operacional-dev07.md) concilia o registro inicial do ciclo operacional com a base DEV-06: PENDENTE inicia/cancela; EM_ANDAMENTO conclui com resultado/cancela; estados finais não reabrem. Prioridades BAIXA/MEDIA/ALTA. Repetições idênticas não gravam eventos nem incrementam versão.

A DEV-07 acrescenta histórico durável com ator/versão, resultado dedicado, cancelamento com confirmação do ID e controle otimista no SQL. Ordem e evento são uma única transação. Versão é obrigatória em todas as alterações (422 se ausente/inválida, 409 se obsoleta). Cancelamento via PATCH é recusado; a rota dedicada exige confirmação do ID. `alembic upgrade head` converge bancos existentes das duas branches sem recriação. Especificação, exemplos, evidência e limites no [contrato DEV-07](../contracts/inspection-lifecycle-dev07.md). Em 25/10, a interface foi integrada e aprovada, e a persistência conferida após reload/reinício com API real, consultas SQL independentes e PostgreSQL descartável. A suíte backend integrada passou com 320 testes sem ignorados também no alvo Python 3.12.15/container com PostgreSQL 16.13; pip check e compileall aprovados. Consulte [evidências e ambiente da execução](../plans/2026-10-25-dev07-evidencias.md).

## Carga da Gold e consistência

O script `backend/scripts/load_gold.py` é um esqueleto: não carrega linhas CSV nem garante idempotência. Quando a ingestão for implementada, registrar lote, esquema e contagens por tabela; só disponibilizar consultas após validar consistência entre tabelas. A segunda execução do mesmo lote deve produzir os mesmos totais. Alterações na fórmula Gold exigem atualização coordenada do dicionário, API, portal, IA e diagnóstico. Testar o mesmo recorte no Databricks, banco local e resposta da API. Se o banco escolhido não suportar separação robusta de permissões, documentar controles compensatórios para o agente de IA antes de afirmar que consultas são somente leitura.

## Qualidade

Testar filtros combinados, estados vazios, UC inexistente, IDs inválidos, paginação, ordenação, idempotência da carga e transições das ordens. Quando houver alterações em métrica, fazer teste de contrato com amostra Gold reconciliada. Se PostgreSQL for escolhido, consultar a skill local `supabase-postgres-best-practices`; isso não impõe uso da plataforma Supabase.

WEB-11 pede testes automatizados como diferencial; a conclusão dos requisitos obrigatórios ainda requer verificação funcional e numérica reproduzível mesmo que esse diferencial não seja perseguido. Registrar no PRD quais fluxos e contratos foram testados, com comando/resultado e lote de dados.
