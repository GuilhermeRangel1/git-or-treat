# TSQL-07 — integração HTTP E1

Data: 06/11/2026. Branch: `feat/genai-text-to-sql`.

## Implementação

`POST /api/v1/ai/sql-analyses` requer sessão individual com `ai:ask`, `ANALYTICS_SOURCE=gold`, `GENAI_SQL_EXECUTION_ENABLED=true` e métrica `billing.revenue` no perfil atual. A flag permanece `false` por padrão no Settings e no Compose. O Backend reduz o escopo em cada revalidação a faturamento e às dimensões F1 permitidas. A rota consulta metadados/cobertura sob a publicação atual e chama `run_sql_question`, que compõe geração, revisão, admissão, execução e evidência sob o prazo compartilhado. A resposta fechada publica evidência, esclarecimento ou motivo de não suporte; SQL e parâmetros não fazem parte do envelope.

## Prova local

O teste HTTP usa login por sessão com perfil comercial, dependência Gold de teste e cliente GenAI substituído. A chamada real da rota executa SQL por `venergy_genai_reader` em PostgreSQL 16 descartável, snapshot READ ONLY, schema completo de faturamento Gold v2 e dados artificiais. `SELECT SUM(...)` independente no engine proprietário confere o resultado da evidência. Nenhum agregado esperado é injetado na resposta da rota.

Comando em `backend/`, `TEST_TEXT_TO_SQL_URL` apontando somente para `text_to_sql_f1_test`:

```powershell
python -m pytest tests/test_genai_sql_executor_postgres.py tests/test_genai_sql_public_route.py tests/test_genai_sql_public_contract.py -q -p no:cacheprovider --tb=short
python -m ruff check app/api/v1/endpoints/ai.py app/schemas/sql_analysis.py app/services/genai_sql_pipeline.py app/services/genai_sql_live_catalog.py tests/test_genai_sql_public_route.py tests/test_genai_sql_executor_postgres.py tests/test_genai_sql_admission.py
python -m compileall -q app/api/v1/endpoints/ai.py app/schemas/sql_analysis.py app/services/genai_sql_pipeline.py app/services/genai_sql_live_catalog.py tests/test_genai_sql_public_route.py tests/test_genai_sql_executor_postgres.py tests/test_genai_sql_admission.py
```

Resultado: 19 testes passaram em 6,29 s, com JUnit privado `work/tsql07-backend.xml`; a suíte cobre executor PostgreSQL, autenticação, desligamento padrão e contrato sem SQL/parâmetros. O caso HTTP percorre os sete oráculos numéricos F1 e o esclarecimento de ano incompleto, com execução PostgreSQL sintética e comparação com o SQL independente do fixture. A suíte GenAI do EvidenceGuard/contrato passou 27 testes em 1,32 s, JUnit privado `work/tsql07-genai.xml`; Ruff e compileall passaram.

Na publicação Gold v2 ativa, uma conferência separada usou `BEGIN READ ONLY` e `SET ROLE venergy_genai_reader`. O recorte de seis competências mais recente e sua janela comparável anterior tinham cobertura; totais por competência e classe reconciliaram, comparação passou e ranking retornou cinco grupos. Foram emitidos apenas estados e contagens (6 meses, 5 classes, 5 posições); sem valores financeiros. Impressão digital sanitizada da publicação: `0efb887c4bd7f24a0c29e5e3555c69c0`. A execução foi SQL direto de controle, não pela rota HTTP.

## Fechamento da TSQL-07 e limites explícitos

- A execução HTTP cobriu os sete oráculos numéricos do fixture e o esclarecimento para cobertura anual incompleta. A conferência Gold ativa usou SQL direto sob papel restrito, sem expor valores.
- O envelope e `EvidenceGuard.validate_sql_evidence` preservam composição de comparação, período, filtros, unidade, catálogo, publicação e digests sem criar um `LogicalReadPlan`. A F1 não admite participação; derivadas futuras permanecem explicitamente fora de TSQL-07.
- Estado `empty`, `all_measures_null` e zero legítimo permanecem distinguidos pela suíte de contrato/materialização; ainda não há rota HTTP validada para cada um desses estados.
- A suíte completa dos serviços não foi executada; os comandos de aceite desta etapa foram dirigidos a execução, HTTP e contrato.
- Provedor Gemini e prontidão continuam simulados no teste HTTP. Não houve chamada paga nem conexão do endpoint à Gold ativa; estes limites não invalidam o aceite de execução/evidência F1, mas impedem alegar qualidade Gemini ou aceite HTTP em dados reais.

**Resultado:** TSQL-07 concluída no escopo de execução e evidência da primeira fatia F1. TSQL-08/09/10 continuam necessários para síntese, auditoria durável, conversa no portal, rollout e aceitação do serviço com Gemini real.
