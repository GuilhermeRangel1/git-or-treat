# GENAI-12 — Insight do Panorama Gold v2

Estado: dez critérios técnicos comprovados na entrega local de 01/11/2026. Branch `feat/genai-insights-panorama`, base independente `develop` em `b804b58`; sem depender do PR GENAI-11. Alterações ainda sem commit/push. IA-03, IA-04 e IA-05 mantêm seus estados oficiais no PRD; este registro não certifica produção.

## Caminho integrado

Portal → Backend `/api/v1/ai/insights` → sessão individual/prontidão → leitor Gold restrito/snapshot → cálculo financeiro comum do Panorama → GenAI `/api/v1/internal/insight-syntheses` → núcleo existente → confirmação de auditoria → revalidação → cartão e painel.

Dados: `schema_version=gold-csv-v2`, schema `gold_v2`, catálogo `gold-catalog-v2`, perfil `v-energy-grid-360-gold`, fonte `gold.local`. A receita é a soma de `diagnostico_receita.receita_base_comparavel_reais`, conforme dicionário; não é receita paga nem receita total. Nenhum CSV ou amostra identificável foi incluído nesta mudança.

`read_gold_panorama_financials`/`gold_panorama_revenue_metric` produzem o mesmo cálculo para o KPI e o insight. O executor usa as credenciais restritas e os controles de publicação existentes do chat, sem SQL livre ou leitura de cadastro individual. O modelo recebe observações minimizadas; não recebe valores livres de filtros nem linhas brutas. O texto livre do provedor não é publicado: o núcleo escolhe IDs autorizados e compõe uma sugestão de investigação sem causalidade.

## Critérios e evidências

| Item do cartão | Resultado local |
| --- | --- |
| Contexto no servidor | Pedido público aceita apenas filtros/lote; métricas são recalculadas no repositório autorizado. |
| Origem externa confiável | Entrada interna com token, escopo e referência exclusivamente v2; rota pública GenAI demonstrativa não aceita contexto real. |
| Observação/comparação/contribuições | KPI e insight compartilham cálculo; SQL independente confere valores reais. PostgreSQL artificial confere decomposição, precisão e denominador. |
| Interpretação separada | Cartão/painel distinguem dado observado, leitura calculada, hipótese e recomendação; sem causa comprovada. |
| Contexto e visual | Período, filtros, origem, lote, definição, fórmula, limitações, correlação/auditoria presentes; revisão em claro/escuro e 1440/390 px. |
| Vazio/parcial/falhas | Zero, ausência e parcial distintos; falta de comparação não elimina valor atual; testes preservam indicadores após falha. |
| Autorização/snapshot | Revalidação antes da leitura/modelo/entrega e após confirmação; leitor restrito, sem credenciais no portal/modelo. |
| Controle independente | Receita real atual/anterior e variação conferidas por SQL; contribuições +30/+10/−20 conferem 75% das altas e compensação de 100% das quedas em fixture controlada. |
| Erro após sucesso | Jornada real seguida de 409 controlado ocultou hipótese antiga e manteve KPIs; testes cobrem falha de serviço e cache. |
| Corrida/acessibilidade | Teste de resposta atrasada; chave inclui origem/lote/fingerprint/atualização; navegador confere abertura/fechamento, fundamento, Escape, retorno de foco e ausência de overflow. |

## Verificações reproduzíveis

Em `ai-agent/`, Python 3.12:

```powershell
python -m pytest -q tests/test_gold_insights.py tests/test_insight_api.py tests/test_core_composition.py tests/test_external_source_composition.py --tb=short
```

Resultado: **51 passaram**. Inclui negação de escopo, token inválido, rota pública, auditoria indisponível, rejeição v1, timeout recuperável e minimização do contexto enviado ao modelo.

Em `backend/`, com `TEST_GOLD_ANALYTICS_POSTGRES_URL` e `TEST_POSTGRES_URL` apontando para bancos descartáveis distintos e papel sem superusuário:

```powershell
python -m pytest -q tests/test_ai_insights.py tests/test_gold_panorama_coordination.py tests/test_gold_analytics_postgres.py tests/test_gold_panorama_money.py tests/test_migrations.py --tb=short
```

Resultado: **64 passaram**, incluindo ciclo de migração e drift. Em prova isolada adicional, um papel com nome personalizado, autorizado somente na view de publicação anterior, recebeu a nova view de metadados sem receber a tabela operacional. Migrações revertidas no banco descartável.

Em `frontend/`: `npm test -- src/features/panorama` → **36 passaram**; build, fronteiras e formatação passaram; lint sem erros, com aviso preexistente em `AuthProvider.tsx`. Ruff nos arquivos GenAI e serviços novos, verificações F nos arquivos Backend afetados, compilação e `git diff --check` passaram.

### Jornada autenticada e reprodução

Processos host desta branch: Backend 8006, GenAI 8007, portal 5182; PostgreSQL local `genai11-gold-db` em localhost:5433. `create_gold_app` usa Gemini já configurado e auditoria real. Conta temporária somente leitura, senha mantida em memória, removida com suas sessões ao final; processos temporários encerrados.

Dois recortes reais da mesma publicação v2 foram exercitados: classe selecionada sem comparação e todas as classes com competência anterior. Observações atuais/anteriores e variação fecharam com SQL independente. Não foi alterado o lote para simular erro: a etapa de conflito usa interceptação HTTP 409 controlada, identificada separadamente da prova real de dados/provedor.

O script versionado `frontend/scripts/check-panorama-gold.mjs` (`npm run test:panorama-gold`) reproduz a jornada contra serviços locais. Playwright **1.64.1**, mesma versão usada no GENAI-11; Chromium headless. Forneça credenciais de teste por `GENAI_BROWSER_USERNAME`/`GENAI_BROWSER_PASSWORD`, origem por `GENAI_BROWSER_BASE_URL` e caso JSON por `GENAI_BROWSER_CASE`: `filters`, `expected`, `expectedAll` e `previousAll` devem vir de controle SQL independente, não da resposta de insight. O script também aceita configuração privada por stdin para orquestração e só admite localhost/127.0.0.1. Não cria contas, não registra credenciais e só grava capturas se `GENAI_BROWSER_ARTIFACT_DIR` for informado. Diretório de capturas deve permanecer privado/ignorado. Instale Chromium com `npx playwright install chromium` quando necessário.

A referência pública foi reproduzida com a mesma sessão individual ainda válida e leitor restrito; mudar o contexto fez a verificação retornar divergência. O comando versionado está no [contrato](../contracts/panorama-insight-api.md#auditoria-implantação-e-reprodução-gold). Capturas privadas de desktop/mobile e claro/escuro ficam em `work/`, fora dos commits. A revisão visual conferiu também moeda brasileira e legibilidade do fundamento.

Documentação Playwright consultada via Context7 em 01/11/2026: [APIRequestContext](https://github.com/microsoft/playwright/blob/main/docs/src/api/class-apirequestcontext.md). Login por `context.request` compartilha cookies com a página; não há injeção de sessão simulada nessa jornada.

## Implantação e limites

Aplicar `alembic upgrade head` antes do consumidor: `genai12000001` cria `gold.publicacao_contexto` com metadados mínimos, replica SELECT dos papéis explicitamente autorizados na view anterior e não expõe a tabela operacional. Scripts de provisionamento atual e legado contemplam a view.

A retenção continua a política existente de 30 dias. O digest de contexto não guarda números/filtros em claro e exige publicação corrente para reprodução. Comparações sem fechamento mensal são observações do publicado, sem certificação de cobertura completa. Não há causalidade, fallback sintético ou ampliação automática para outros domínios. Cancelamento assíncrono não prova cancelamento imediato de trabalho SQL em thread; permanecem orçamento SQL de 5 s e prazo total de 35 s.

Revisão separada por especificação e padrões: achados sobre 409, competência comparativa ausente, referência v1, timeout, ACL de metadados, tipos e tupla posicional foram corrigidos e reconferidos; sem achado crítico remanescente na releitura.
