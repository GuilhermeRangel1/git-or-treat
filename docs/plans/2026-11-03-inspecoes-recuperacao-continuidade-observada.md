# Energia recuperável e Continuidade observada — plano de implementação

> **Execução por agentes:** aplicar `superpowers:executing-plans` tarefa por tarefa. Este documento é planejamento; não autoriza merge nem registra implementação concluída.

**Objetivo:** apresentar a estimativa condicional de energia recuperável da Gold em Inspeções e permitir respostas numéricas de DEC/FEC observados no Assistente sem exigir novo job, exportação ou declaração da equipe de Dados.

**Arquitetura:** estender os consumidores Gold v2 existentes. Backend continua como executor único das consultas; GenAI recebe evidências delimitadas e o portal apresenta números com suas condições. A prontidão certificada continua distinta da elegibilidade para consultar valores observados.

**Stack:** FastAPI, Pydantic, SQLAlchemy/PostgreSQL; núcleo GenAI existente; React, TypeScript, Vite e Tailwind.

**Especificação:** solicitação da pessoa usuária nesta sessão; [PRD](../PRD.md), WEB-04, WEB-06, WEB-10 e IA-01/03/06; seção 5.2 do Case Final fornecida pela pessoa usuária. O time de Dados considera a estimativa por UC, condicionada à confirmação da irregularidade, com faixa nominal de 90% e validação temporal, atendimento do WEB-04. A pessoa usuária escolheu consultar Continuidade como observada, preservando a falta de certificação.

## Contexto confirmado

- Branch atual: `feat/web10-perfis`. Preservar alterações locais dos hooks/configurações e PDFs; não incluí-las nos commits destas entregas.
- Publicação ativa local: `gold-csv-v2`, run `GOLD_20261103T173853Z_76c37784`, banco `v_energy`. Quinze tabelas analíticas validadas pelo carregador e cadastro restrito carregado separadamente, indisponível à GenAI.
- Em `fila_inspecao`, 43.777 UCs têm estimativa e dois limites publicados, estado `ESTIMATIVA_UC_POR_CONSUMO_SE_CONFIRMADA` e método `CONSUMO_CONDICIONAL_V1`; 1.223 permanecem sem estimativa. São contagens observadas nesta publicação, não constantes da implementação.
- O relatório `validacao_recuperacao_json.estimativa_uc` registra `CANDIDATO_PASSOU_VALIDACAO_TEMPORAL`, `criterios.nivel_faixa=0.9` e janela de aplicação. O JSON ainda contém `aceite_web04=PENDENTE`; registrar a aceitação comunicada nesta sessão como decisão de produto, sem editar o conteúdo original da Gold.
- A API já transporta campos de recuperação em `evidence`, mas `GoldInspectionItem.potential_recoverable_energy_kwh`, o decoder e a apresentação ainda impõem indisponibilidade.
- A pergunta de Continuidade chega ao coordenador, onde a prontidão indisponível provoca `GoldCoverageUnavailable` antes de executar/sintetizar. A cobertura geral fechada não certifica automaticamente cada alimentador.

## Restrições e padrões obrigatórios

- Aplicar [backend-coding-standards](../../.agents/skills/backend-coding-standards/SKILL.md), [frontend-coding-standards](../../.agents/skills/frontend-coding-standards/SKILL.md), [genai-gold](../../.agents/skills/genai-gold/SKILL.md) e as regras `AGENTS.md` de cada área. Usar as recomendações React aplicáveis ao Vite de `vercel-react-best-practices`.
- Consultar `supabase-postgres-best-practices` antes de alterar consultas SQL ou persistência. Esta entrega não requer migração nem atualização das linhas da Gold.
- Reutilizar componentes, fontes, tokens, controles, temas e padrões de acessibilidade existentes no sistema. Preservar desktop/mobile e navegação por teclado.
- Não alterar fórmulas, numeradores, denominadores, estados de cobertura, arquivos dos pacotes ou permissões para conseguir aprovar a validação.
- Não criar endpoint, catálogo ou orquestrador paralelo para contornar os controles existentes.
- Ausência, zero observado, valor inválido e cobertura não certificada precisam continuar distintos.
- Somente planejamento nesta rodada. Checks abaixo são passos futuros; nenhum resultado futuro pode ser registrado como executado.

## Decisões de escopo

1. **Recuperação:** consumir a estimativa publicada por UC, com faixa nominal e condição explícita. Calcular recuperação no portal a partir da variação de consumo foi descartado.
2. **Continuidade:** permitir leitura delimitada como `observed_uncertified`. Rerodar o pipeline para certificar ficou fora desta entrega, conforme solicitação. Reclassificar `NAO_CERTIFICADA` como certificada ou ignorar toda falha de prontidão foi descartado.
3. O modo observado poderá ser usado pelos perfis já autorizados a DEC/FEC, incluindo `operations` e `admin`; não amplia o catálogo dos demais perfis.
4. A flexibilização vale somente para as métricas existentes de DEC/FEC. Atendimento, faturamento, consumo e outras capacidades mantêm suas políticas.
5. WEB-10 só poderá avançar após resposta real pelo portal, reconciliação independente e regressão de acesso. Certificação da origem não será declarada como resultado desta mudança.

## Tarefa 1 — Sincronizar a decisão e os contratos

**Arquivos:** novo ADR em `docs/decisions/` com numeração livre; índice de decisões; `docs/PRD.md`; `docs/contracts/inspection-gold-v2.md`; `docs/contracts/genai-query-execution.md`; `docs/agents/genai-gold.md`; guias dos serviços afetados e dicionário/contrato Gold nas seções de consumo.

- [x] Registrar a aceitação da estimativa condicional e a política de leitura observada de DEC/FEC. Preservar o histórico das decisões anteriores e distinguir contrato do produtor de política do consumidor.
- [x] Documentar a exceção específica à regra atual de bloqueio por cobertura insuficiente. A exceção não concede certificação nem dispensa os controles de qualidade e acesso.
- [x] Definir os contratos a seguir antes de alterar seus consumidores. Manter estados WEB/IA em validação até as evidências finais.

**Entrega verificável:** documentos não exigem simultaneamente bloquear e permitir o mesmo caso; limites e critérios de aceite estão alinhados.

## Tarefa 2 — Expor recuperação individual na API

**Arquivos principais:** `backend/app/repositories/gold_inspections.py`, `backend/app/services/inspection_analytics.py`, `backend/app/schemas/inspection_queue.py`, `backend/app/api/v1/endpoints/inspections.py`.

- [x] Selecionar também `validacao_recuperacao_json` na fila/detalhe e interpretar somente os metadados necessários; não enviar o relatório bruto ao navegador/modelo.
- [x] Aceitar estimativa somente com estado e método conhecidos, valores finitos não negativos, limites coerentes contendo a estimativa e validação temporal correspondente. Metadados ausentes/inválidos mantêm indisponibilidade com motivo.
- [x] Alterar `potential_recoverable_energy_kwh` para `float | None` e tornar o motivo de indisponibilidade nulo quando houver estimativa válida. Expor em `evidence` os limites, nível nominal da faixa e os metadados de janela/validação necessários à explicação.
- [x] Calcular `estimated_units` e `unavailable_estimate_units` sobre todo o recorte filtrado antes de paginar, com os mesmos critérios de elegibilidade dos itens. Não somar estimativas/limites como promessa de recuperação.
- [x] Atualizar limitações e descrição HTTP que ainda afirmam que a publicação inteira não fornece estimativas. Preservar posição/categoria e ordenação oficial da fila.
- [x] Cobrir em `backend/tests/test_gold_inspections_v2.py` e `test_gold_inspection_repository.py`: estimativa válida, zero explícito, UC sem histórico, método desconhecido, relatório malformado, limites invertidos e resumo filtrado/paginado consistente.

**Entrega verificável:** fila e detalhe devolvem o valor publicado e sua faixa para UC elegível; uma UC inelegível continua sem número.

## Tarefa 3 — Apresentar recuperação em Inspeções

**Arquivos principais:** `frontend/src/features/inspecoes/contract.ts`, `InspectionQueue.tsx`, `SuspicionDetail.tsx`, `InspectionFoundations.tsx`; revisar `frontend/src/features/ordens/order-actions.ts` e `OrderFoundationsDialog.tsx` para o snapshot das evidências.

- [x] Atualizar o decoder para aceitar números elegíveis e validar faixa, nível nominal, motivo e soma dos contadores do resumo. Preservar compatibilidade explícita com publicações anteriores sem estimativa.
- [x] Exibir energia estimada em kWh na tabela e nos cards mobile; substituir o aviso global de indisponibilidade por explicação condicional. No detalhe mostrar estimativa, faixa nominal de 90% quando fornecida e janela publicada.
- [x] Usar o texto central: **“Estimativa de energia a recuperar se a irregularidade se confirmar.”** Informar que a faixa provém de validação temporal e não garante recuperação na UC.
- [x] Manter “Energia recuperável indisponível” somente para UCs sem estimativa válida, com motivo da API. A variação de consumo continua como contexto separado.
- [x] Conferir fundamentos e evidência congelada nas novas ordens: preservar valor, faixa, condição e publicação; ordens antigas não recebem números retroativamente após recarga. Revisar a exportação existente para evitar informação contraditória.
- [x] Cobrir decoder, detalhe, fila desktop/mobile e snapshot em `contract.test.ts`, `InspecoesPage.test.tsx` e `OrderFoundationsDialog.test.tsx`, incluindo zero e ausência.

**Entrega verificável:** uma UC elegível deixa de mostrar o aviso universal de indisponibilidade e exibe a estimativa publicada com sua condição.

## Tarefa 4 — Autorizar DEC/FEC observados sem certificar a cobertura

**Arquivos principais:** `backend/app/services/genai_coordination.py`, `genai_executor.py`, `gold_domain_controls.py`; repositório/serviço específico de elegibilidade observado se necessário; `backend/app/schemas/genai_evidence.py`; espelho em `ai-agent/app/schemas/evidence.py`; `ai-agent/app/agent/evidence_guard.py` e fluxo de síntese existente.

- [x] Introduzir modo de qualidade explícito `certified | observed_uncertified` no contrato entre os serviços. Distinguir capacidades certificadas disponíveis das capacidades elegíveis apenas para observação; não inserir uma capacidade indisponível na lista atual `available_capability_ids` fingindo aprovação.
- [x] Restringir a elegibilidade observada às métricas DEC/FEC do catálogo e a falha exclusivamente de certificação. O código confere o estado original e o recorte; apenas capturar `GoldCoverageUnavailable` ou aceitar todo `coverage_incomplete` seria insuficiente.
- [x] Conferir na mesma publicação a linha para cada competência solicitada, numeradores utilizáveis, denominadores positivos e cobertura explicitamente não certificada. Testes mantêm bloqueios quando há lacunas; ausência não vira zero.
- [x] Manter bloqueios por tabela/coluna ausente, controles, denominador, publicação, autorização ou timeout; a cobertura global não substitui certificação por alimentador.
- [x] Transportar modo, recorte, publicação e limitação pela execução, evidência, guard, síntese e auditoria. SQL permanece somente leitura, parametrizado, limitado e minimizado.
- [x] Garantir no retorno público, de forma determinística, a informação **“Valores observados; cobertura do alimentador não certificada.”** A omissão desse aviso pelo modelo não pode produzir resposta aparentemente certificada.
- [x] Não anunciar fechamento, conformidade regulatória ou ranking completo a partir desses valores. Preservar fórmulas do catálogo e recusar agregações não suportadas.
- [ ] Completar integração em `test_ai_chat.py`, `test_genai_internal_contract.py` e `test_gold_domain_readiness.py`, incluindo todos os bloqueios de cobertura/controle e a rota até a auditoria. Existem testes dirigidos de elegibilidade, janela completa, capacidade observada, aviso determinístico e contrato/guard; faltam essas provas integradas antes do aceite WEB/IA.

**Entrega verificável:** a pergunta Admin por alimentador/mês chega ao SQL e à síntese quando os controles observados passam; a resposta conserva a falta de certificação e todos os demais bloqueios.

## Tarefa 5 — Validar pelo portal e reconciliar a Gold ativa

- [ ] Backend, dentro de `backend/`: executar `python -m pytest -q tests/test_gold_inspections_v2.py tests/test_gold_inspection_repository.py tests/test_genai_executor.py tests/test_ai_chat.py tests/test_genai_internal_contract.py tests/test_gold_domain_readiness.py` usando o ambiente do projeto; executar checks adicionais requeridos pelo guia e PostgreSQL de teste separado da base ativa.
- [ ] GenAI, dentro de `ai-agent/`: executar testes de contrato/evidência/síntese afetados, `python -m compileall -q app tests` e `python -m ruff check .`; ampliar regressão se houver mudança em contratos compartilhados ou falha relevante.
- [ ] Frontend: testes dirigidos de Inspeções, decoder e fundamentos de Ordens; `npm run lint`, `npm run check:boundaries`, `npm run build` e formatação dos arquivos alterados.
- [ ] No Chromium real, acessar com perfis autorizados; conferir Inspeções com UC estimada e UC indisponível, filtros, paginação, recarga, claro/escuro, desktop/mobile e teclado.
- [ ] Repetir a pergunta Admin de DEC e FEC para `ALM-JAB-015`, junho/2026, com modelo real pela composição de produção. Conferir aviso, unidade, período, alimentador, publicação, auditoria e persistência da conversa após recarga.
- [ ] Comparar API/portal/IA com SQL independente na mesma publicação, usando os numeradores/denominadores originais de DEC/FEC. Para recuperação comparar campos publicados e faixa, sem recalcular a estimativa pela variação.
- [ ] Repetir a matriz HTTP de cinco perfis × sete recursos e conferir isolamento GenAI: Comercial sem DEC/FEC; Operação/admin com acesso permitido; Atendimento/Perdas sem novas capacidades por efeito colateral. Preservar logout/revogação e leitura restrita do banco.
- [ ] Confirmar que `cobertura_dominios` continua `NAO_CERTIFICADA` nos recortes originais e nenhum job, exportação ou escrita na Gold foi usado nesta implementação.

## Tarefa 6 — Preparar a revisão do PR e o merge

- [ ] Atualizar `docs/plans/2026-11-01-web10-perfis-evidencias.md` e Registro de progresso do PRD com comandos/resultados realmente observados, publicação e limitações; registrar a substituição do bloqueio universal pela política observada delimitada.
- [ ] Revisar os critérios WEB-04 e tarefa final de WEB-10 separadamente. A resposta numérica observada pode satisfazer a jornada após reconciliação; não encerra a certificação da origem nem conclui outros requisitos automaticamente.
- [ ] Sincronizar o rastreador quando conectado e autorizado, com evidências sanitizadas. Não publicar dados identificáveis, segredos, CSVs ou PDFs do case.
- [ ] Executar `git diff --check`, gate documental vigente e revisão dos padrões/escopo. Criar commits coesos, em português, separando recuperação de Continuidade, com verificações reais no corpo.
- [ ] Preparar o PR #101 para revisão com comportamento final e evidências; merge em `develop` depende da aprovação final e dos checks requeridos. Não prometer que o simples plano libera o merge.

## Critérios de aceite

- [ ] Inspeções mostra estimativa e faixa da UC quando disponíveis, com condição de confirmação da irregularidade; UCs sem insumos continuam indisponíveis e zero continua zero.
- [ ] O Assistente responde DEC/FEC observados no recorte elegível e mostra a falta de certificação de forma persistente e auditável.
- [ ] Permissões, integridade da publicação, controles de qualidade e consulta somente leitura permanecem comprovados.
- [ ] Valores reconciliados na Gold v2 vigente, documentação alinhada e checks relevantes aprovados; falhas registradas impedem declarar a entrega concluída.
- [ ] Nenhuma alteração dos fatos/metadados Gold ou execução de job da equipe de Dados é necessária para essas duas entregas de aplicação.

## Estado da execução — 03/11/2026

- Recuperação individual e apresentação nas Inspeções/Ordens implementadas; a verificação dirigida passou nos testes Backend de consulta/contrato e Frontend (50 e 30 testes, respectivamente). Fila e detalhe preservam indisponibilidade sem inferir valor; estimativa é condicional à confirmação da irregularidade.
- Continuidade observada implementada no fluxo existente. O conjunto focado posterior à correção passou com 45 testes; a ressalva não certificada permanece determinística. A suíte GenAI completa passou com 4.333 testes e 5 skips.
- Suítes completas: Backend 1.119 passaram/114 skips/6 falhas na rodada inicial; cinco falhas de compatibilidade foram corrigidas e cobertas pelos testes focados, mas a suíte completa ainda não foi repetida. A falha restante é dependência `openpyxl` ausente; instalação bloqueada por rede. Frontend 451 passaram/9 falhas; isoladas, 47 passaram/8 falharam nos arquivos preexistentes de Panorama, roteador, Ajuda contextual e Assistente. Ruff indisponível.
- Lint, fronteiras (205 arquivos), build e formatação frontend passaram; lint mantém dois avisos preexistentes fora das alterações. A verificação runtime GenAI e a jornada real Admin continuam bloqueadas pela falta de URL/token do AI Agent, DSN do leitor Gold e sessão Admin no navegador.
- Permanecem abertos: integração completa da rota até auditoria com a cobertura adicional indicada na Tarefa 4; resposta real Admin DEC/FEC e reconciliação API/portal/IA; validação autenticada no navegador; sincronização do cartão Trello, pois o quadro de requisitos documentado não está acessível nesta conexão. WEB-04/WEB-10 continuam `Em validação`; commits e push não equivalem a aceite nem autorizam merge.