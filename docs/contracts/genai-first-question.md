# GENAI-09 — primeira pergunta real: evidência local

## Resultado em 01/11/2026

GENAI-09 concluído tecnicamente em 10/10 nesta branch. Jornada real comprovada: login no portal → Assistente → POST /api/v1/ai/questions → planejamento HTTP GenAI → prontidão PostgreSQL → executor restrito → síntese Gemini → resposta answered na tela com referência durável. Número exibido conciliado por SQL independente e replay da referência efetivamente mostrada no navegador. O histórico abaixo registra a progressão e seus limites na época.

Base de código: 8274009 com alterações locais na branch feat/genai-primeira-pergunta-real. Backend usa app.main:app; GenAI usa app.gold_runtime:create_gold_app, perfil Gold v2 e fonte gold.local. PostgreSQL 16: container genai08-gold-v2-postgres e volume genai08-gold-v2-data, previamente carregado pelo importador oficial. C01/C02/C04 passaram e foram aprovados pela pessoa usuária apenas para esta entrega local. Nenhuma aprovação foi inferida para os demais controles.

## Reprodução privada

A amostra privada fica em work/genai09-local, ignorado pelo Git. result.json contém a pergunta, controle independente e envelope público, sem senha ou cookie. model-result.json contém a saída do modelo e evidência minimizada para diagnóstico autorizado; não publicar esses arquivos. O roteiro smoke.py cria identidade temporária orders:read, faz login HTTP e remove a conta em finally. Credenciais ficam no ambiente privado.

Pergunta: receita de um município em mês explícito coberto pelo lote. O recorte é escolhido deterministicamente pela competência mais recente e município ordenado com receita não nula. Controle independente, separado do compilador de planos:

```sql
SELECT competencia, municipio, SUM(receita_total_reais) AS total
FROM gold_v2.diagnostico_receita
WHERE municipio IS NOT NULL
GROUP BY competencia, municipio
HAVING SUM(receita_total_reais) IS NOT NULL
ORDER BY competencia DESC, municipio
LIMIT 1;
```

Comando privado observado: docker exec -e PYTHONPATH=/repo/backend -w /repo/backend genai09-local-backend-direct python /repo/work/genai09-local/smoke.py. Resultado: login 200, pergunta 200, answered, sem erro e com audit_reference. Conta removida ao final. O total Decimal do controle confere com a observação; a representação numérica e unidade dessa observação aparecem na resposta. Período, filtros e referência de origem conferem entre evidência e contrato público. O identificador do lote permanece na trilha interna autorizada; não é publicado no documento.

## Correções e verificações

- Criado entrypoint Gold implantável que reutiliza create_app; auditoria obrigatória e execução exclusivamente no Backend.
- Prompt genai-grounding-v3 esclarece que filtro de município não vira dimensão da linha agregada. A v2 produziu claims com dimensão ausente na observação e foi corretamente recusada; a v3 respondeu sem relaxar o guard.
- Backend aceita eventos de prompts v1/v2/v3; referência opaca fica visível no Assistente.
- GenAI: 99 testes de runtime/claims/adaptador e 25 de EvidenceGuard passaram. Backend: 3 de auditoria passaram, com aviso preexistente Starlette/httpx. Interface: 12 testes, tipos/build e fronteiras passaram; lint sem erros, com aviso preexistente AuthProvider.
- Prontidão pela rede host levou 32,94 s e uma chamada pública encerrou com 504. A ligação direta entre containers permitiu completar o fluxo dentro do prazo existente. Não foi aumentado o limite de 35 s.

## Limites

A conclusão cobre a primeira fatia de receita do GENAI-09. Não conclui a cobertura dos quatro domínios IA-01, todos os recortes Gold, insights ou requisitos oficiais do produto. Dataset, payloads privados, captura da jornada e chaves não entram no Git. Instrumentação diagnóstica local não integra o runtime de produção. A conclusão não efetua merge dos PRs empilhados; publicação e revisão final do PR permanecem passos do fluxo Git.

## Continuação — falhas pela API real

Em 01/11/2026, `docker exec -e PYTHONPATH=/repo/backend -w /repo/backend genai09-local-backend-direct python /repo/work/genai09-local/failures.py` comprovou:

- Pergunta sem período: HTTP 200, needs_clarification, sem answer.
- Município não reconhecido: HTTP 200, needs_clarification, sem answer.
- Revogação de orders:read após login: HTTP 403, sem answer.

O roteiro cria conta temporária e a remove em finally; senha e cookie ficam em memória. Resultado sanitizado em work/genai09-local/failure-results.json. Município desconhecido não comprova recorte autorizado vazio. Permanecem vazios legítimos, fonte/modelo/auditoria indisponíveis e jornada visual. Nenhum novo critério composto foi marcado por estes três subcasos.

## Contrato de falhas de autorização e auditoria

A rota de chat traduz HTTPException 401/403 das dependências Gold para o envelope público v1: access_denied, retryable false e correlação. Detalhes privados da identidade não são refletidos. OpenAPI documenta ambos os estados. Isso permite ao consumidor Assistente reconhecer a recusa em vez de exibir uma falha genérica fora do contrato.

`tests/test_ai_chat.py` acrescenta casos de 401/403 e falha SQLAlchemy da auditoria na coordenação Gold pelo endpoint: resposta 503/service_unavailable, retryable false, sem answer ou detalhe privado. A dependência de recurso é controlada; a rota e o coordenador são os reais. Não é um ensaio de queda do PostgreSQL de produção.

Verificação Linux: ANALYTICS_SOURCE=synthetic, removendo GENAI_AUDIT_WRITE_TOKEN e GENAI_GOLD_DATABASE_URL apenas do processo pytest, `python -m pytest -q -p no:cacheprovider tests/test_ai_chat.py`: 15 passaram, aviso preexistente Starlette/httpx. Uma execução anterior herdou configuração Gold e falhou nos casos sintéticos; não foi contabilizada como sucesso. Sem novo aceite composto por essa seleção.

### Falha de publicação no contrato público

A rota agora traduz GoldPublicationUnavailable/GoldPublicationInvalid para HTTP 503, code service_unavailable e retryable false, com correlação e mensagem fixa. Publicação alterada preserva o tratamento específico HTTP 409. A indisponibilidade deixa de escapar como erro interno fora do envelope do chat.

Verificação: `docker exec -e ANALYTICS_SOURCE=synthetic -w /repo/backend genai09-local-backend-direct env -u GENAI_AUDIT_WRITE_TOKEN python -m pytest -q -p no:cacheprovider tests/test_ai_chat.py`: 17 passaram, aviso preexistente Starlette/httpx. A primeira execução herdou configuração Gold e falhou em seis casos demonstrativos; a execução limpa acima resolveu a interferência. Novos testes injetam falha na fronteira do coordenador: comprovam o contrato HTTP, não simulam queda real do PostgreSQL.

## Reprodução da referência pública real

Em 01/11/2026, o roteiro privado replay-smoke.py repetiu a pergunta pela API real com Gemini e chamou `backend/scripts/genai_audit.py::_verify_reference` sobre o audit_reference público. Plano privado reconstruído a partir do plano estrutural auditado e dos filtros originais da evidência minimizada; nenhum SQL livre foi fornecido ao replay. A sessão individual foi mantida apenas em memória. Leitura da trilha pela credencial de operador e reexecução pelo leitor restrito, com revalidação da sessão, plano, catálogo e publicação.

Comando: `docker exec -e PYTHONPATH=/repo/backend -w /repo/backend genai09-local-backend-direct python /repo/work/genai09-local/replay-smoke.py`.

Resultado observado: login 200; pergunta 200/answered; administrative_replay true; both_services true. Conta temporária removida em finally. O prompt efetivamente usado é v3, o catálogo lógico v1 sobre schema Gold v2, e a referência concreta do lote/controle permanece nos artefatos privados. O controle independente SUM está documentado acima. Não houve jornada visual nem preenchimento interativo do CLI: o roteiro chamou o consumidor administrativo com getpass substituído pela sessão em memória.

## Configuração executada e separação das evidências

A prova real usou o commit 2f71fcac0346b563e7d363894dff06ce0a3cfa9c com as alterações locais de tratamento de erros documentadas nesta continuação.

| Processo | Entrada executada | Versões observadas |
| --- | --- | --- |
| Backend local | app.main:app, container genai09-local-backend-direct, porta 8010 | Python 3.12.16; FastAPI 0.162.0; SQLAlchemy 2.1.6; psycopg 3.3.6 |
| GenAI local | app.gold_runtime:create_gold_app, fábrica Gold, porta 8011 | Python 3.12.6; FastAPI 0.136.3; google-genai 2.31.0 |
| Banco | genai08-gold-v2-postgres, volume persistente genai08-gold-v2-data | PostgreSQL 16; publicação Gold CSV v2 |

As versões foram obtidas por importlib.metadata nos processos/ambientes executados. A imagem Backend requereu instalação da dependência pwdlib[argon2], já declarada em requirements.txt. Não representa revisão da imagem final de implantação.

Configuração Backend: ANALYTICS_SOURCE=gold, ORDERS_AUTH_MODE=session, AI_AGENT_BASE_URL apontando para a GenAI local, GENAI_GOLD_DATABASE_URL com papel venergy_genai_reader, GENAI_AUDIT_DATABASE_URL com operador dedicado e GENAI_GOLD_APPROVED_CONTROLS=[C01,C02,C04]. Segredos não constam aqui. Conexão operacional usa v_energy_app com a leitura analítica local explicitamente autorizada. A conexão quantitativa permanece separada.

Configuração GenAI: perfil Gold v2, demonstração e roteamento demonstrativo desligados, provedor Gemini, token técnico e destino durável de auditoria. A instrumentação privada envolve o adaptador para guardar sua saída original, sem modificar a resposta ou substituir fonte/modelo. Essa instrumentação não integra a aplicação versionada.

Conectividade do modelo: chamada Gemini concluída. Cálculo: observação e representação pública conciliadas com SUM independente e replay da referência. Experiência do portal: testes de componente passaram, mas navegação real ainda não comprovada; controle de navegador indisponível nas configurações atuais do Work. Esses resultados permanecem distintos.

A busca privada por combinação vazia na competência mais recente não encontrou ausência entre município/classe nem município/classe/subgrupo observados. Isso não é um teste aprovado de vazio nem autoriza remover dados para fabricar um aceite.

## Regressão pelo entrypoint Gold oficial

`ai-agent/tests/test_gold_runtime.py::test_official_gold_runtime_preserves_first_question_outcomes` exercita create_gold_app, planejamento e síntese internos com a pergunta de receita municipal/classe/mês. Casos: answered com valor controlado 12 R$, no_evidence, indisponibilidade do modelo e indisponibilidade da auditoria. Modelos e persistência de eventos são controlados para determinismo; os handlers, fábrica, contratos e núcleo são reais. Ausência e auditoria indisponível impedem chamada ao modelo; erros não retornam answer nem evidência e não refletem detalhes privados. Não comprova queda real dos serviços, PostgreSQL ou navegador.

Verificação em container descartável baseado em review-dev13-merge-ai-agent: `python -m pytest -q -p no:cacheprovider tests/test_gold_runtime.py tests/test_gold_planning_http.py`: 11 passaram. Ruff do arquivo alterado e git diff --check passaram. Uma asserção inicial lia evidence no envelope de planejamento em vez da response interna; corrigida sem mudança de produção. O container antigo de testes estava encerrado; dependências de teste foram instaladas apenas no container descartável, sem dataset/credenciais.

A regressão adiciona a primeira fatia à composição implantável. A liberação para ampliação de catálogo ainda requer revisão dos contratos/consumidores; esse critério composto não é concluído somente por testes locais.

## Matriz integrada de falhas — critérios concluídos em 01/11/2026

Os critérios «Exercitar a mesma fatia com recorte sem registros, pergunta ambígua, acesso negado e fonte indisponível» e «Repetir a fatia […] com falha do modelo/auditoria» foram conferidos. GENAI-09: 8/10. A prova abaixo combina o vazio no lote privado real com regressão de falhas determinísticas sobre PostgreSQL 16 descartável; não declara uma indisponibilidade física dos serviços de produção.

### Vazio legítimo no lote real

Encontrada combinação de município e bairro que existem separadamente na tabela Gold v2 `consumo_receita_bairro`, mas sem linhas para o cruzamento na competência escolhida. Consulta independente com parâmetros comprovou COUNT(*)=0 e existência de cada dimensão. Não houve exclusão ou alteração dos dados Gold para produzir esse caso.

`docker exec -e PYTHONPATH=/repo/backend -w /repo/backend genai09-local-backend-validation python /repo/work/genai09-local/empty-real-smoke.py`: login 200; pergunta 200/needs_clarification; sem answer ou evidence, com audit_reference. Mensagem: falta de cobertura no recorte e ausência não equivale a zero. Pergunta e controle permanecem privados em work/genai09-local/empty-real-result.json. Conta temporária removida em finally. Planejamento recusou o recorte antes da síntese e do modelo.

O Backend passou a usar alias Docker `gold-db` no ambiente privado local, pois o IP anterior mudou após reinicialização. Não é alteração do contrato ou de credencial. O processo GenAI foi iniciado pela fábrica oficial sem a instrumentação diagnóstica anterior.

### Regressão pelo endpoint público e PostgreSQL

`tests/support/genai_failure_matrix.py::assert_first_question_failures` estende o teste existente `tests/test_genai_session_postgres.py`. Usa login/sessão, app.main:app, coordenador, plano, executor PostgreSQL restrito, operações HTTP do núcleo em subprocesso e auditoria persistida entre os serviços. O fixture mantém seu selo de prontidão controlado e provedor determinístico; não equivale a repetir todos os cenários com Gemini e lote privado.

| Caso | Resultado observado | Garantia |
| --- | --- | --- |
| Recorte vazio no fixture: município e mês existentes, cruzamento sem linhas | 200/needs_clarification, sem erro | Sem síntese; não transforma ausência em zero |
| Pergunta sem período | 200/needs_clarification | Sem answer/evidência |
| Falha DBAPI injetada somente no SQL quantitativo do leitor | 503/service_unavailable, retryable true | Planejamento real concluído; síntese não é chamada |
| Provedor indisponível injetado no adaptador do subprocesso | 200/recoverable_error, service_unavailable, retryable true | SQL e síntese reais; sem answer/evidência |
| Ingresso durável GenAI rejeitado por token de teste inválido | 200/recoverable_error, retryable true | Falha antes da consulta quantitativa |
| Confirmação final de auditoria Backend falha após síntese pronta | 503/service_unavailable, retryable false | Nenhum sucesso Backend persistido, nenhuma referência final ou resposta publicada |
| Permissão retirada após login | 403/access_denied, retryable false | Bloqueia antes do planejamento GenAI |
| Recuperação após restaurar falhas e permissão | 200/answered, 12.0 R$, referência durável | Sem fallback demonstrativo e sem contaminação entre requests |

Todas as falhas conferem mensagem não vazia, correlação no cabeçalho/corpo, ausência de answer/evidência e ausência de detalhe privado. Injeções pertencem exclusivamente a suporte de teste; não foram adicionadas chaves de falha ao runtime de produção.

### Comandos e resultado final

PostgreSQL exclusivo: container `genai09-failure-matrix-db`, bancos descartáveis preparados por `backend/scripts/prepare_test_postgres.sql`, sem montagem do volume Gold privado. Runner `genai09-failure-matrix-runner` recebeu TEST_GOLD_READER_ADMIN_URL e TEST_POSTGRES_URL somente para esses bancos. Na pasta backend: `python -m pytest -q -p no:cacheprovider tests/test_genai_session_postgres.py`: 1 teste integrado passou em 27,40 s, com a matriz acima dentro dele e aviso preexistente Starlette/httpx. O fixture executa upgrade, prova e downgrade; limpeza da função auxiliar agora ocorre também após falha.

Contratos complementares: `python -m pytest -q -p no:cacheprovider tests/test_ai_chat.py tests/test_genai_audit.py` em ambiente de fixture (ANALYTICS_SOURCE=synthetic; sem credenciais Gold/auditoria): 20 passaram, mesmo aviso preexistente. Ruff dos três arquivos Backend alterados, compileall e git diff --check passaram.

Antes da aprovação final houve uma asserção incorreta de texto (12 em vez de 12.0) e resíduo da função auxiliar no banco descartável após a falha; expectativa corrigida, função temporária limpa e teardown reforçado. Execuções falhas não contam como aceite.

Pendências atuais: jornada real do portal e revisão integrada dos consumidores/contratos antes de ampliar catálogo. As pendências históricas de vazio e falhas descritas acima ficam substituídas por esta evidência. Estados oficiais IA continuam inalterados; sem novo commit/push.

## Conclusão técnica — 10/10 em 01/11/2026

### Jornada visual real e referência da tela

O navegador acessou http://127.0.0.1:5180, efetuou login individual com conta de leitura temporária autorizada e navegou pelo menu até /assistente. A mesma pergunta de receita reconciliável foi digitada e enviada na tela. O Assistente mostrou answered, número/unidade, mês, filtro municipal, evidência Gold sem selo sintético e referência de conferência. Captura privada: work/genai09-local/portal-gold-proof.png. A amostra não integra o Git/Trello.

O roteiro privado ui-reconcile.py usou a referência efetivamente exibida no navegador, conferiu a cifra da tela contra SUM independente e chamou o consumidor administrativo de replay com nova sessão da mesma identidade. Resultado: portal_total_matches_independent_sql=true, portal_reference_reproduced=true, both_services=true. Resultado sanitizado em work/genai09-local/ui-reconciliation.json. A aba não estava mais disponível ao tentar logout; a conta temporária foi removida via Backend/banco e a ausência de suas sessões foi confirmada. Nenhuma credencial de teste foi preservada no Git.

Configuração de rede visual: portal genai09-local-frontend-review2 com API_PROXY_TARGET=http://backend:8000 e alias Docker backend para o processo desta branch. O primeiro proxy usava host.docker.internal, que não está no TrustedHost permitido: foi corrigido o destino, sem ampliar a allowlist de hosts. Portas públicas permanecem somente em loopback. Processo GenAI pela fábrica oficial, sem instrumentação, usando provedor Gemini configurado no ambiente privado.

### Revisão dos consumidores e contratos

Base fixa 8274009, comparando os commits de GENAI-09 e as alterações locais. Contratos revisados: GENAI-01 execução interna e ADR-0002; GENAI-03 catálogo Gold v2; GENAI-07 coordenação; GENAI-08 auditoria; envelope público e consumidor Assistente. A revisão técnica da primeira fatia não é aprovação global dos domínios ou funcionalidades futuras.

#### Standards

Reconferência sem achados acionáveis remanescentes. Corrigidos: limpeza do fixture pela PK exata, documentação vigente de sessão/Gold e distinção entre propostas históricas e implementação atual. Nenhuma refatoração adicional foi indicada pelos padrões para esta fatia.

#### Spec

Reconferência sem bloqueio para a primeira fatia. Corrigido isolamento do histórico: RequireSession usa chave por identidade confirmada, descartando estado local do consumidor na troca A→B. A regressão com AuthProvider real falhou antes da correção e passou depois, comprovando que mensagens antigas desaparecem e a pergunta de B envia context vazio. O texto inicial do Assistente não declara mais todas as respostas como fictícias; apenas os exemplos demonstrativos são identificados assim. Origem e is_demo continuam vindos do contrato da resposta.

Contrato público continua v1. Documentos de execução distinguem versão lógica v1 de schema Gold v2, estados atuais, históricos e compatibilidade de implantação. Backend que aceita eventos v1/v2/v3 deve ser publicado antes de GenAI com prompt v3; ordem de rollback registrada. Não foi adicionada outra abstração ou caminho de execução.

### Verificações finais e estado

- Frontend: 26 testes de autenticação, isolamento do Assistente e consumidores passaram. Tipos TypeScript, Vite build e fronteiras passaram; lint sem erros, com aviso preexistente AuthProvider.
- Matriz PostgreSQL após restringir a limpeza do fixture à PK completa: 1 teste integrado passou em 28,52 s, com aviso preexistente Starlette/httpx. Banco descartável encerrado após a prova; volume Gold preservado.
- Ruff dos arquivos Backend alterados, compileall e diff-check passaram. Links locais conferidos em 132 documentos versionados do projeto, sem links quebrados (exclusões .agents/.claude equivalentes ao gate documental).
- Revisões técnicas independentes de padrões e especificação reconferiram as correções sem bloqueios remanescentes; liberação restrita à primeira fatia.

Os dez critérios do GENAI-09 estão comprovados por estes registros, testes e artefatos privados, substituindo as pendências históricas deste documento. IA-01/03/05/06 mantêm os estados oficiais do PRD; completar um cartão técnico não conclui esses requisitos por consequência. Código/documentação desta continuação ainda locais, sem commit/push.
