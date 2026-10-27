# Desenvolvimento GenAI com a Gold

Este guia orienta a execução dos cartões do quadro [GenAI — Gold real](https://trello.com/b/Vlnppr77/genai-gold-real) sobre o código existente. O [PRD](../PRD.md), os guias de [GenAI](../services/ai-agent.md) e [Backend](../services/backend.md), o [dicionário Gold](../dicionario_gold.md) e as decisões aprovadas continuam canônicos. O quadro de adaptação não altera o aceite obrigatório IA-01 a IA-06; IA-07 e IA-08 continuam diferenciais. Testes de regressão permanecem necessários à qualidade das mudanças.

## Estado e decisões de partida

Referência inspecionada em 24/10/2026: `develop` em `3d1242162ab00d394fa7d15749cbd55f8f818026`. Reconfira os símbolos e o estado dos documentos na branch atual; esta referência não fixa versões futuras.

- Chat, insight e leitura SQL têm implementações demonstrativas integradas. Fonte externa dispõe de composição explícita para perguntas, mas isso não comprova um adaptador Gold operacional.
- Nesta referência, o dicionário oficial ainda é um modelo a preencher. Um dicionário de outra branch só pode ser habilitado após conferir a versão aprovada, o esquema e as capacidades efetivamente executadas.
- A [ADR-0002](../decisions/0002-genai-gold-query-owner.md) propõe o Backend como proprietário da consulta e ainda aguarda revisão. GENAI-01 deve resolver essa decisão antes de habilitar acesso real. O leitor SQL existente é uma base técnica, não aprovação automática de acesso direto da GenAI ao banco.

## Caminhos e pontos de extensão

| Responsabilidade | Código existente a inspecionar | Como evoluir |
| --- | --- | --- |
| Entrada conversacional | [endpoint Backend](../../backend/app/api/v1/endpoints/ai.py), [cliente GenAI](../../backend/app/services/genai_client.py), [rotas GenAI](../../ai-agent/app/api/routes.py) | Preserve Portal → Backend `/api/v1/ai/questions` → GenAI `/api/v1/questions` e valide os envelopes em ambos os serviços. `/api/v1/ai/query` é legado e retorna 503 nesta base. |
| Composição | [create_app](../../ai-agent/app/main.py), [compose_core](../../ai-agent/app/agent/composition.py) | Injete dependências no ponto existente. Um adaptador novo precisa de chamador de runtime, configuração e teste da fábrica/composição efetivamente usada. |
| Intenção e autorização | [interpretador](../../ai-agent/app/agent/interpreter.py), [planner](../../ai-agent/app/agent/planner.py), [plano](../../ai-agent/app/agent/read_plan.py), [política](../../ai-agent/app/agent/access.py) | Amplie perfil e capacidades declaradas; mantenha a interpretação, validação e autorização antes da consulta. |
| Fonte de evidência | [EvidenceSource](../../ai-agent/app/ports/evidence.py), [schemas](../../ai-agent/app/schemas/evidence.py) | Implemente `retrieve(plan, access_context)` preservando estados tipados e proveniência. O acesso via Backend ou banco deve ficar atrás dessa porta, conforme a decisão aprovada. |
| Leitura SQL | [plano SQL](../../ai-agent/app/sql/plan.py), [serviço](../../ai-agent/app/sql/service.py), [validador](../../ai-agent/app/sql/validator.py), [executores](../../ai-agent/app/sql/executors.py) | Reaproveite os controles aplicáveis, adaptando mapeamento, agregação e dialeto ao esquema aprovado. Valide também na execução. |
| Geração e proteção | [orquestrador](../../ai-agent/app/agent/orchestrator.py), [guard de evidência](../../ai-agent/app/agent/evidence_guard.py), [execução](../../ai-agent/app/agent/execution.py), [provedores](../../ai-agent/app/providers/factory.py) | Preserve minimização, fundamentação, orçamento e política de modelos. Alterações de provedor ou roteador devem chegar ao orquestrador composto. |
| Insight e indicadores | [contexto Backend](../../backend/app/services/panorama_insights.py), [repositório](../../backend/app/repositories/panorama.py), [orquestrador de insight](../../ai-agent/app/agent/insights.py), [cartão e painel](../../frontend/src/features/panorama/AIInsightCard.tsx) | Recalcule contexto no servidor a partir do mesmo recorte e lote dos indicadores. Exiba hipótese separada dos números e preserve invalidação e erros na interface. |

O núcleo continua independente de HTTP e de executores concretos; composição e adaptadores conectam essas fronteiras. Backend e GenAI validam seus contratos sem importar internamente um ao outro. O navegador consome a API, sem receber credenciais, SQL interno ou regras de autorização como configuração confiável.

### Restrições que precisam de evolução explícita

- `SqlArtificialEvidenceSource` e sua projeção em [sql/evidence.py](../../ai-agent/app/sql/evidence.py) exigem fonte `synthetic.*`, janela mensal e evidência demonstrativa. Construa a projeção real a partir do dicionário; trocar `is_demo` ou renomear a fonte não adapta fórmulas, grão ou proveniência.
- `create_app(source_mode="external")` exige perfil próprio, `EvidenceSource`, resolvedor de acesso, token interno, demonstração desligada e auditoria durável. Preserve essas condições; token de serviço não substitui identidade e escopo da pessoa usuária.
- O roteamento em `create_app` está restrito a `GRID360_DEMO_PROFILE` / `synthetic.fixture`. Para habilitá-lo na Gold, revise compatibilidade e teste a seleção pelo orquestrador após a redução da evidência, respeitando orçamento, escalada e fallback. A existência de um roteador não significa que esteja ativo para outra fonte.
- A rota GenAI de insights retorna 503 no modo externo e o contexto Backend rejeita fonte não demonstrativa. GENAI-12 deve implementar a origem confiável e a autorização necessárias antes de alterar esses guardas; remover a recusa isoladamente não entrega IA-04.
- O [catálogo SQL demonstrativo](../../ai-agent/app/sql/dictionary.py) não é o dicionário real. Tabela, coluna de período, grão, unidade, agregação e relações devem ser capacidades por métrica. Métrica sem período não deve receber competência inventada; DEC/FEC e razões não devem ser somados como medidas aditivas.

## Execução de um cartão

Comece pelo resultado do cartão e suas dependências, não pela criação de uma nova abstração. Registre antes da implementação: ID(s) do PRD, caminho executado atual, ponto de extensão, dicionário/lote necessários e fronteira que demonstrará o resultado.

Classifique a entrega para que implementação e descrição tenham o mesmo alcance:

| Tipo de entrega | Evidência suficiente para essa etapa | Limite a declarar |
| --- | --- | --- |
| Preparação | Catálogo, contrato ou componente validado com fixture controlada e consumidor previsto identificado | Não afirma acesso real nem integração de runtime; informa cartão/dependência que fará a ligação. |
| Integração executável | Configuração e composição da aplicação carregam o componente; teste pelo caso de uso/endpoint executa a consulta e valida o retorno | Se os dados forem sintéticos, continua sem reconciliação ou aceite Gold. |
| Aceite Gold | Fluxo integrado com lote autorizado, resultado reconciliado por controle independente e permissões comprovadas no banco real escolhido | Documenta cobertura e pendências; aplica o [workflow](workflow.md) antes de concluir o requisito oficial. |

Preparação é uma entrega válida quando esse é o escopo combinado. Um catálogo usado só nos testes deve ser descrito como preparação; a entrega de integração exige uso pela composição da aplicação. Preserve a fatia pequena e declare a dependência em vez de acrescentar um segundo orquestrador, endpoint ou catálogo sem consumidor.

### Fronteiras entre os cartões

| Cartões | Saída que a próxima etapa deve conseguir usar |
| --- | --- |
| GENAI-01 a 04 | Dono da consulta definido; lote e cobertura conferidos; mapeamentos e vocabulário conectáveis ao perfil/plano usados pelo núcleo. |
| GENAI-05 a 08 | Acesso e execução controlados, adaptador composto, evidência rastreável e auditoria durável; consumidor identificado em cada mudança. |
| GENAI-09 e 10 | Primeira pergunta integrada e depois cenários dos quatro domínios reconciliados; uma pergunta funcional não comprova cobertura completa. |
| GENAI-11 a 13 | Assistente e insight exibem respostas da fonte real com o mesmo contrato e recorte; erro, troca de lote ou resposta atrasada não mantém interpretação antiga como atual. |
| GENAI-14 a 16 | Verificação integrada, execução/desempenho observados e entrega reproduzível. A validação começa durante as fatias, não apenas ao final. |

Responsável e revisor são definidos pelo time no cartão; o guia se aplica igualmente a qualquer pessoa ou agente. Mudanças no contrato entre componentes exigem revisão dos consumidores afetados. Consulte as dependências específicas no quadro, sem transformar a ordem das colunas em execução estritamente serial.

## Validação por fronteira

Use dados sintéticos controlados para desenvolvimento e CI; eles permitem validar arquitetura e controles sem publicar dados privados. Mantenha uma verificação privada com lote Gold autorizado para reconciliação. O modelo pode ser falso para testes determinísticos; um teste com leitor falso não comprova SQL ou permissões do banco.

| Mudança | Verificação que demonstra integração |
| --- | --- |
| Perfil, catálogo ou interpretação | Pergunta em português pelo orquestrador composto gera o plano esperado e chega à fonte com recorte correto. Inclua ambiguidade que altera resultado; não valide só leitura do TOML. |
| Leitor ou adaptador | Banco sintético com esquema/dialeto representativo, consulta executada pelo caminho público afetado, valores esperados independentes, unidade, janela, filtros e versão reconciliados. Inclua vazio, zero, nulo e ausência de cobertura. |
| Acesso e segurança | Teste pela aplicação e conexão com papel restrito no banco escolhido. Demonstre escrita e leitura fora do escopo bloqueadas, parâmetros, limite, timeout e comportamento da auditoria. Strings e instruções consultadas são dados não confiáveis. |
| Composição e configuração | Use `create_app` e o entrypoint realmente implantado; demonstre que o modo configurado escolhe o adaptador correto, recusa configuração incompleta e não faz fallback silencioso para demonstração. |
| Provedor ou roteador | Passe pelo orquestrador usando a composição normal; confira seleção, escalada, fallback e orçamento. Smoke de provedor real é separado e autorizado por ambiente, sem dados privados. |
| Chat e contratos HTTP | Exercite os endpoints e o consumidor alterado com os estados `answered`, `needs_clarification`, `refused`, `no_evidence` e `recoverable_error`, além de falha de transporte. Preserve contrato e sanitização entre serviços. |
| Insight | Teste o contexto calculado no Backend e a tela: hipótese e observação separadas, mesmos filtros/lote dos indicadores, 409 com cache antigo, corrida entre recortes e falha de IA mantendo indicadores disponíveis. |

Pontos de partida existentes: [composição externa](../../ai-agent/tests/test_external_source_composition.py), [núcleo reutilizável](../../ai-agent/tests/test_reusable_core.py), [SQL pelo HTTP](../../ai-agent/tests/test_sql_demo_http.py), [permissões PostgreSQL](../../ai-agent/tests/test_sql_postgres_permissions.py) e [tela de insight](../../frontend/src/features/panorama/PanoramaInsight.test.tsx). Evolua essas fronteiras quando corresponderem ao comportamento alterado. Quando forem necessários testes novos, siga a skill TDD e as regras do módulo.

Execute os gates dos módulos afetados conforme seus manifests e guias. Registre comandos, resultados, skips e dependências indisponíveis; não reaproveite contagens antigas como evidência da mudança. Testes verdes com mock não comprovam Gold, e um relatório com limitações conhecidas não equivale à cobertura integral do case.

## Evidência para revisão

No resumo da mudança ou descrição do PR, preencha apenas o que se aplica, com arquivos/símbolos e resultados observados:

```text
Escopo: GENAI-xx; IA-xx; preparação / integração executável / aceite Gold.
Caminho: entrada → composição → caso de uso → fonte/executor → consumidor.
Reuso e mudança: ponto existente estendido; novos componentes e seus chamadores.
Dados e contrato: dicionário, grão, fórmulas/unidades, filtros, cobertura e versão do lote.
Controles: autorização, execução somente leitura, limites, auditoria e exposição pública.
Verificações: comandos/resultados; teste que percorre o caminho; controle independente.
Limites: capacidades não cobertas, dependências bloqueadas e próximo cartão.
```

Faça a revisão procurar o chamador de runtime e a configuração, além da definição do componente. Para preparação, identifique o consumidor futuro sem afirmar que já existe. Para integração, exija teste que atravesse a ligação nova. Para aceite, reconcilie contra o lote real e revise os critérios do PRD.

O harness orienta o trabalho; não é uma trava automática de arquitetura nem prova de conformidade de commits anteriores. Descoberta da skill e carregamento das regras dependem do cliente. Mudanças funcionais atualizam guias, registro do PRD e cartões conforme o workflow; a instalação destas instruções, por si só, não conclui requisitos nem cartões.
