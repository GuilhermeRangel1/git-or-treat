# Assistente Gold v2 — revalidação da matriz em 02/11/2026

## Escopo e execução

Rodada privada autorizada pela pessoa usuária, na branch `fix/genai-prontidao-gold-local`, sobre a base `983ee42` com alterações locais ainda sem commit/push. Publicação Gold v2 existente, catálogo `gold-catalog-v2`, schema `gold_v2`, contrato físico `gold-csv-v2`, perfil `v-energy-grid-360-gold` e prompt `genai-grounding-v4`. Nenhuma carga nova ou alteração de privilégios dos papéis PostgreSQL foi feita.

Execução final: `20261102T041125_013170Z`. Cliente HTTP externo ao Backend → login/cookie reais → rota pública `/api/v1/ai/questions` → GenAI HTTP → prontidão → executor PostgreSQL restrito → Gemini real → auditoria durável. Controles SQL independentes usaram a identidade operacional local já autorizada para leitura analítica, em conexão READ ONLY, com timeout de 5 s. Isso permite conferir a unicidade de chamados/tratativas sem conceder essa tabela ao leitor GenAI.

Credenciais das contas temporárias ficaram somente na memória do harness; contas e sessões removidas no finally. O runner versionado não registra respostas completas, credenciais ou DSNs. Valores de controle e parâmetros resolvidos ficam apenas em `work/genai-local-validation/<execução>/`, ignorado pelo Git. Este registro contém somente IDs, estados e contagens.

## Resultado

| Classe | Rodada anterior | Rodada final |
| --- | ---: | ---: |
| PASS | 29 | 43 |
| FAIL | 14 | 0 |
| BLOQUEADO | 5 | 5 |
| SEM_AMOSTRA_NO_LOTE | 7 | 7 |
| NAO_EXECUTADO | 2 | 2 |

Casos anteriormente em FAIL que passaram: FAT-04, FAT-06, FAT-09, FAT-11, CON-01, CON-02, CON-04, CON-05, CON-06, CON-07, CON-08, ATE-03, ATE-04, ATE-05.

PASS inclui respostas numéricas e comportamentos esperados de esclarecimento, recusa e acesso negado. Não significa que todos os 57 casos tenham resposta numérica disponível.

## Correções

- Planejamento: ano compartilhado em meses nomeados preserva comparação versus intervalo; agrupamento municipal da receita usa a capacidade existente do executor, com escopo e limite revalidados.
- Compose: o override Gold fixa `ANALYTICS_SOURCE=gold`; GenAI continua iniciando `app.gold_runtime:create_gold_app --factory`.
- Ambiente privado: sincronizados os controles já aprovados; C08/C09 revalidados e habilitados com autorização explícita nesta rodada. Arquivos `.env` continuam privados e não entram no commit.
- Runner: confere moeda/valores no formato legível, vinculando cada valor a mês ou efeito. Troca de meses, unidades, rótulos ou janelas continua falhando. Separadores decimais não são removidos como se fossem milhares para forçar correspondência.
- Geração: chat com proveniência Gold usa schema `ObservationSelection`, somente estado e IDs. O provedor não fornece prosa numérica ou claims nesse modo; campos extras são recusados. Os IDs passam pelas guardas existentes e os valores públicos continuam sendo compostos das observações autorizadas. Schema anterior mantido para demonstração/insight minimizado.
- Auditoria: ingresso aceita v4 e mantém v1/v2/v3; implantar Backend compatível antes da GenAI. Cache de modelo incorpora o digest da instrução.

## Pendências reais

| Casos | Pendência |
| --- | --- |
| FAT-08 | Valor efetivamente pago/arrecadado não é equivalente a receita faturada; preservado o esclarecimento. |
| INT-01, INT-02, INT-03 | Cobertura mensal de ocorrências/continuidade insuficiente ou não certificada nos recortes; preservar bloqueio de DEC/FEC e contagem temporal. |
| ATE-01 | Fonte não comprova cobertura mensal de atendimento suficiente para o recorte. |
| FAT-12, FAT-13, FAT-15, CON-10, INT-06, INT-07, ATE-02 | Amostras de zero, nulo, base zero, ausência ou competência fechada não existem no lote selecionado; sem fabricar dados. |
| SEG-06, SEG-07 | Não executados pelo runner live: provas técnicas exercitadas separadamente em testes controlados. |

Não conclui os quatro domínios nem IA-01/02/03/06, não certifica produção ou completude da fonte e não comprova jornada visual no navegador.

## Verificações complementares

- GenAI: `python -m pytest -q --tb=short` → 4093 passaram, 4 skips (smoke externo opt-in e PostgreSQL sem DSN). Container descartável sem rede, plugin anyio habilitado e configuração privada mascarada.
- Backend: `python -m pytest -q tests/test_genai_audit.py tests/test_genai_client.py tests/test_gold_panorama_coordination.py --tb=short` → 41 passaram; aviso Starlette preexistente.
- Prova PostgreSQL descartável: `python -m pytest -q tests/test_genai_session_postgres.py --tb=short` → 1 passou em 127,22 s. Inclui `assert_first_question_failures`, sessão, autorização, SQL, revogação e limites. Banco isolado sem porta pública/volume persistente, preparado com `backend/scripts/prepare_test_postgres.sql` e removido depois.
- SEG-06: a prova PostgreSQL acima e `test_official_gold_runtime_preserves_first_question_outcomes` (na suíte GenAI) conferem falhas sem provocá-las no lote real. SEG-07: `tests/test_safety_gate.py` passou na suíte GenAI; ataques da própria matriz foram exercitados na API real.
- Ruff completo GenAI, Ruff dos arquivos Backend afetados, validação estrutural `python scripts/run_gold_domain_scenarios.py --dry-run`, configuração Compose e `git diff --check` passaram.

## Reprodução

Configurar somente no ambiente privado os nomes de variável descritos no runner: `GENAI10A_BACKEND_URL`, `GENAI10A_ORIGIN`, `GENAI10A_USERNAME`, `GENAI10A_PASSWORD`, `GENAI10A_CONTROL_DSN` e o par opcional da conta sem permissão. O controle de ATE-05 exige uma conexão de conferência autorizada a ler a contagem de tratativas; o leitor GenAI não recebe essa permissão.

Em `ai-agent/`, executar `python scripts/run_gold_domain_scenarios.py --output-dir ../work/genai-local-validation`. O resultado live preserva bloqueios e falta de amostra; `--strict` continua sinalizando domínios incompletos. Contas de teste, credenciais e aprovações são responsabilidades do ambiente privado, não são criadas pelo runner.

## Estados por caso

| Caso | Estado público | Classe |
| --- | --- | --- |
| FAT-01 | answered | PASS |
| FAT-02 | answered | PASS |
| FAT-03 | answered | PASS |
| FAT-04 | answered | PASS |
| FAT-05 | answered | PASS |
| FAT-06 | answered | PASS |
| FAT-07 | needs_clarification | PASS |
| FAT-08 | needs_clarification | BLOQUEADO |
| FAT-09 | answered | PASS |
| FAT-10 | answered | PASS |
| FAT-11 | answered | PASS |
| FAT-12 | — | SEM_AMOSTRA_NO_LOTE |
| FAT-13 | — | SEM_AMOSTRA_NO_LOTE |
| FAT-14 | needs_clarification | PASS |
| FAT-15 | — | SEM_AMOSTRA_NO_LOTE |
| FAT-16 | answered | PASS |
| FAT-17 | needs_clarification | PASS |
| CON-01 | answered | PASS |
| CON-02 | answered | PASS |
| CON-03 | needs_clarification | PASS |
| CON-04 | answered | PASS |
| CON-05 | answered | PASS |
| CON-06 | answered | PASS |
| CON-07 | answered | PASS |
| CON-08 | answered | PASS |
| CON-09 | needs_clarification | PASS |
| CON-10 | — | SEM_AMOSTRA_NO_LOTE |
| CON-11 | needs_clarification | PASS |
| INT-01 | error:service_unavailable | BLOQUEADO |
| INT-02 | error:service_unavailable | BLOQUEADO |
| INT-03 | error:service_unavailable | BLOQUEADO |
| INT-04 | needs_clarification | PASS |
| INT-05 | needs_clarification | PASS |
| INT-06 | — | SEM_AMOSTRA_NO_LOTE |
| INT-07 | — | SEM_AMOSTRA_NO_LOTE |
| ATE-01 | error:service_unavailable | BLOQUEADO |
| ATE-02 | — | SEM_AMOSTRA_NO_LOTE |
| ATE-03 | answered | PASS |
| ATE-04 | answered | PASS |
| ATE-05 | answered | PASS |
| ATE-06 | refused | PASS |
| ATE-07 | needs_clarification | PASS |
| AMB-01 | needs_clarification | PASS |
| AMB-02 | needs_clarification | PASS |
| AMB-03 | needs_clarification | PASS |
| AMB-04 | answered | PASS |
| AMB-05 | answered | PASS |
| AMB-06 | needs_clarification | PASS |
| AMB-07 | needs_clarification | PASS |
| AMB-08 | needs_clarification | PASS |
| SEG-01 | refused | PASS |
| SEG-02 | refused | PASS |
| SEG-03 | refused | PASS |
| SEG-04 | refused | PASS |
| SEG-05 | error:access_denied | PASS |
| SEG-06 | — | NAO_EXECUTADO |
| SEG-07 | — | NAO_EXECUTADO |
