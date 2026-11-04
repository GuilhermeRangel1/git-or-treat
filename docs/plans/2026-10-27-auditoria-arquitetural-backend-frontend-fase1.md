**Nota de estado — 2026-10-27:** este relatório histórico foi restaurado integralmente da fonte recuperada em `work/refactor-pre-gold/recovered-audit-original.md`. A execução vigente é a Fase 1 pré-Gold reduzida, limitada a FE-010, FE-015, FE-017, FE-018, BE-012, BE-013, BE-009 e TR-001; os demais itens estão adiados para reavaliação no [plano de execução](2026-10-27-melhorias-pre-gold-fase1.md). Esta nota não altera o conteúdo nem os achados históricos da auditoria.

---

# Auditoria arquitetural — Backend e Frontend | Fase 1

**Escopo:** investigação, diagnóstico e planejamento. Nenhuma alteração de código foi feita, nenhuma dependência foi instalada, e a Fase 2 não foi iniciada.

O relatório registra os achados, evidências, mudanças recomendadas, riscos e validações. Os caminhos são relativos à raiz do repositório. A alteração preexistente em frontend/package-lock.json foi preservada.

## A. Diagnóstico geral

### Cobertura e limites

- Backend: inventário dos 93 arquivos Python e 12.261 linhas em aplicação, testes, scripts, Alembic e inicializadores; inspeção de camadas, imports, serviços, endpoints, schemas, repositórios, configurações, segurança e fronteiras de testes.
- Frontend: inventário dos 138 arquivos TS/TSX (106 produção/suporte, 32 testes), oito features, app, layouts, shared, cinco CSS, scripts e configurações. Os testes foram inventariados por cenários e lidos nos pontos pertinentes; não houve leitura integral linha a linha dos 32 arquivos.
- Transversal: contratos HTTP, decoders, filtros, paginação, ordens, cache, autenticação, chat, insight, documentação e futuras fronteiras Gold.
- Referências: AGENTS raiz/backend/frontend/docs; skills backend, frontend, GenAI/Gold e referências pertinentes; arquitetura e guias dos serviços; PRD, contratos e ADRs relevantes.

### Verificações executadas

| Inspeção | Resultado observado |
|---|---|
| node scripts/check-boundaries.mjs | Passou: fronteiras em 138 arquivos |
| npm.cmd run lint | Passou |
| npm.cmd run format:check | Passou |
| Análise de imports TS/TSX em memória | Nenhum ciclo estático local encontrado nos 138 arquivos |
| Experimento de decoder UC em memória | Paginação inválida aceita; FE-010 |
| git diff --check | Passou |
| Estado git no início e encerramento | Mesma alteração preexistente em frontend/package-lock.json |
| Tentativa de análise Python com -B | Não iniciou: interpretador do ambiente virtual inacessível |

Não foram executados testes, build, Docker, migrações ou jornadas no navegador. As observações comportamentais derivam de inspeção estática, salvo o experimento de decoder citado.

### Notas qualitativas

| Dimensão | Backend | Frontend |
|---|---:|---:|
| Coesão | 7,5 | 7,5 |
| Acoplamento | 7,5 | 8,0 |
| Separação de responsabilidades | 7,5 | 7,5 |
| Consistência | 7,5 | 7,5 |
| Testabilidade | 8,0 | 8,0 |
| Organização | 7,5 | 8,0 |
| Manutenibilidade | 7,5 | 7,8 |
| Nota do módulo | 7,6 | 7,8 |

**Nota geral da arquitetura: 7,7/10.** As notas são indicadores qualitativos, não metas de refatoração. Nenhum P0 foi identificado. A arquitetura é sólida e evolutiva; não há justificativa para reescrita ou adoção de camadas universais.

### Pontos fortes

- Arquitetura frontend por features, fronteiras automatizadas, layout persistente e lazy loading.
- Separação entre URL, estado remoto e interações transitórias.
- Transporte HTTP centralizado, decoders em runtime e cancelamento.
- Fonte sintética explícita, sem fallback silencioso.
- Dados operacionais separados da fonte analítica.
- Ordens com versão, idempotência, restrições de concorrência e histórico transacional.
- Distinção consistente entre zero, ausência, parcialidade, denominadores e proveniência.
- ADRs e guias documentam decisões importantes e seus limites.
- Testes existentes cobrem cenários significativos de contrato, rollback, migração e concorrência.

### Problemas principais

1. Contratos de domínios distintos concentrados em schemas/analytics.py.
2. Avaliação de cobertura UC repetida entre overview e históricos.
3. Verificação semântica do insight acoplada ao endpoint HTTP.
4. Transporte GenAI duplicado.
5. Infraestrutura de testes importada de módulos coletáveis e conftest.
6. Recursos exclusivos do Panorama ainda dentro de shared por exceção documentada.
7. Coordenação de mutações e conversa misturada à apresentação.
8. Decoders com rigor desigual de contexto e paginação.
9. Defeitos localizados de acessibilidade e documentação operacional desatualizada.

## B. Inventário dos achados — Backend

Nos itens abaixo, app/, tests/ e scripts/ pertencem a backend/.

### BE-001 — Contratos de domínios independentes concentrados em analytics.py

**P2 · Problema confirmado · Confiança alta**

- **Evidência/local:** app/schemas/analytics.py:85 contém contratos de Receita; a partir de :203, UC; :284, inspeção; :296, continuidade, além de metadados, erros e paginação.
- **Impacto:** alterações independentes convergem no mesmo módulo; outros schemas importam dele somente uma pequena parte.
- **Recomendação/arquivos:** criar schemas/revenue.py; aproximar contratos UC de uc360.py, fila de inspection_queue.py e continuidade de operations.py. Manter o suporte verdadeiramente comum em módulo pequeno. Atualizar imports por fatia.
- **Risco/validação:** médio. Comparar JSON e OpenAPI, incluindo nomes dos componentes, defaults, nulidade e forward references.
- **Benefício/esforço:** ownership claro; médio. Não fazer uma reorganização única.

### BE-002 — UCProfile duplicado

**P2 · Problema confirmado · Confiança alta**

- **Evidência/local:** app/schemas/analytics.py:212 e app/schemas/uc360.py:121 declaram os mesmos campos.
- **Impacto:** detalhe legado e overview podem divergir.
- **Recomendação/arquivos:** compartilhar a definição durante BE-001. Se for necessário preservar referências públicas do OpenAPI, manter classes públicas finas sobre uma definição comum.
- **Risco/validação:** baixo a médio. Conferir respostas dos dois endpoints e compatibilidade OpenAPI.
- **Benefício/esforço:** elimina duplicação; pequeno. Não criar hierarquia genérica de entidades.

### BE-003 — analytics.py mistura suporte comum e cálculo de continuidade

**P2 · Problema confirmado · Confiança alta**

- **Evidência/local:** app/services/analytics.py:21 contém erro; :29-97 período, filtros e metadados; :108 KPIs; :135 paginação; :145 continuidade. services/operations.py importa build_continuity.
- **Impacto:** uma regra específica de DEC/FEC vive num módulo do qual vários domínios dependem.
- **Recomendação/arquivos:** extrair services/continuity.py, mantendo um cálculo comum entre continuidade legada e Operação. KPIs podem permanecer em analytics.py inicialmente.
- **Risco/validação:** médio. Cobertura, denominadores, zero conhecido, janela parcial e consolidação numérica.
- **Benefício/esforço:** fronteira explícita; médio. Não criar framework de métricas.

### BE-004 — Serviço UC reúne jornadas de evolução independente

**P2 · Oportunidade · Confiança alta**

- **Evidência/local:** app/services/uc_analytics.py:109 busca; :143 detalhe legado; :261 medidas; :315 comparação; :360 overview; :605 históricos.
- **Impacto:** regras de seis históricos, cobertura, projeção e ordenação ficam acopladas à busca e overview.
- **Recomendação/arquivos:** extrair uc_history.py primeiro. Manter busca, overview e compatibilidade em uc_analytics.py. Extrair uc_coverage.py apenas se houver consumidores reais em ambos.
- **Risco/validação:** médio/alto. Seções UC, pagamentos versus competência, vigência de medidor, duplicatas e paginação.
- **Benefício/esforço:** menor ramificação e testes direcionados; médio. Não criar seis serviços.

### BE-005 — Avaliação de cobertura UC repetida em overview e histórico

**P2 · Problema confirmado · Confiança alta**

- **Evidência/local:** app/services/uc_analytics.py:360 calcula status de seção; build_uc_history, em :605, reagrupa e classifica leituras e completude de faturas.
- **Impacto:** corrigir uma classificação em apenas um caminho pode produzir resultados diferentes.
- **Recomendação/arquivos:** helpers compartilhados de cobertura/qualidade, aproveitando BE-004. Preservar distinção entre status de linha, seção e envelope.
- **Risco/validação:** alto se precedências mudarem. Comparar overview e histórico com nulos, duplicatas, cobertura parcial e várias páginas.
- **Benefício/esforço:** regra comum verificável; médio. O resumo do universo não pode derivar da página.

### BE-006 — Fronteiras internas dependem de dicionários auxiliares

**P2 · Oportunidade · Confiança alta**

- **Evidência/local:** app/api/v1/endpoints/ucs.py:78 conhece campos internos como period/status/limitations; services/revenue_analytics.py usa dict para comparação e qualidade.
- **Impacto:** router conhece detalhes internos dos serviços e erros de chaves aparecem em runtime.
- **Recomendação/arquivos:** tipar resultados internos nas bordas UC/Receita, ou reutilizar envelopes existentes quando apropriado; não duplicar todos os DTOs em dataclasses.
- **Risco/validação:** médio, sobretudo Decimal. Comparar JSON e impedir exposição de campos auxiliares.
- **Benefício/esforço:** contratos internos claros; médio.

### BE-007 — Decomposição preço-volume está dentro da orquestração Receita

**P2 · Oportunidade · Confiança alta**

- **Evidência/local:** app/services/revenue_analytics.py:516 e bloco em torno de :573 misturam fonte, cobertura, comparação, cálculo e serialização.
- **Impacto:** regra matemática auditável exige contexto de fonte para ser testada.
- **Recomendação/arquivos:** extrair cálculo puro para revenue_decomposition.py; isolar reconciliação dentro do arquivo atual antes de criar outro módulo.
- **Risco/validação:** alto numericamente. Preservar Decimal, extremos, HALF_UP, subcentavos, interação e fechamento.
- **Benefício/esforço:** regra independente de HTTP/fonte; médio. Nenhuma mudança de fórmula.

### BE-008 — Validação semântica do insight está no endpoint

**P2 · Problema confirmado · Confiança alta**

- **Evidência/local:** app/api/v1/endpoints/ai.py:248 compara contexto e observações da GenAI e rejeita evidência não demonstrativa em resposta answered.
- **Impacto:** proteção depende do chamador HTTP.
- **Recomendação/arquivos:** mover verificação para services/panorama_insights.py; compor construir → chamar → verificar → envelopar, deixando a tradução HTTP na rota.
- **Risco/validação:** médio/alto. Contexto/observação adulterados continuam rejeitados; respostas válidas, recusas e ausência preservadas.
- **Benefício/esforço:** integridade reutilizável e testável; médio. A extração não implementa o executor Gold.

### BE-009 — Transporte GenAI duplicado

**P2 · Problema confirmado · Confiança alta**

- **Evidência/local:** app/services/genai_client.py:24 e :84 repetem configuração, auth, correlação, POST, timeout, status, JSON e validação.
- **Impacto:** política de comunicação pode divergir entre clientes.
- **Recomendação/arquivos:** helper privado para transporte; manter paths e validação Pydantic explícitos em cada cliente.
- **Risco/validação:** médio. Testar ambos via MockTransport: auth, path, timeout, rede, status, JSON e correlação divergentes.
- **Benefício/esforço:** política única; pequeno/médio. Evitar herança ou framework genérico.

### BE-010 — Tradução de erros GenAI repetida

**P3 · Problema confirmado · Confiança alta**

- **Evidência/local:** app/api/v1/endpoints/ai.py:145 e :219 traduzem os mesmos tipos para 503/504/502.
- **Impacto:** código, retryable, correlação ou textos podem divergir.
- **Recomendação/arquivos:** após BE-008, centralizar tradução local com mensagens por operação.
- **Risco/validação:** baixo/médio. Matriz das duas rotas e três falhas, mais 422 sanitizado.
- **Benefício/esforço:** consistência; pequeno. Fazer em sequência ou junto de BE-008.

### BE-011 — Consultas operacionais e comandos no mesmo serviço

**P2 · Oportunidade · Confiança média/alta**

- **Evidência/local:** app/services/inspections.py:38, :154 e :201 contêm leituras; o restante coordena criação, transações, idempotência e transições.
- **Impacto:** regras de leitura e ciclo operacional têm razões distintas para mudar.
- **Recomendação/arquivos:** extração opcional services/order_queries.py. Manter comandos, _active_order, _replay e transação no serviço atual.
- **Risco/validação:** médio. Preservar projeção sem snapshot, filtros antes do count, ordenação e autorização.
- **Benefício/esforço:** leitura isolada; pequeno/médio. Não é necessária só pelo tamanho do arquivo.

### BE-012 — Infraestrutura de testes importada de outros testes

**P2 · Problema confirmado · Confiança alta**

- **Evidência/local:** test_active_uc_migration.py, testes de ordens e segurança importam helpers de tests.test_migrations e tests.conftest.
- **Impacto:** reorganizar um cenário pode quebrar testes sem relação.
- **Recomendação/arquivos:** tests/support/database.py e migrations.py; fixtures explícitas para sessões/engine.
- **Risco/validação:** médio. Executar seleções e suíte completa, preservando guardas PostgreSQL descartável, papel restrito, cleanup e drift.
- **Benefício/esforço:** infraestrutura com ownership próprio; médio.

### BE-013 — Fixture de banco não restaura overrides anteriores

**P2 · Problema confirmado · Confiança alta**

- **Evidência/local:** backend/tests/conftest.py:55 altera app.dependency_overrides e depois usa clear() sem finally externo.
- **Impacto:** falha de ciclo de vida pode impedir limpeza; clear também remove overrides que a fixture não criou.
- **Recomendação/arquivos:** guardar estado anterior e restaurá-lo em finally; app factory não é necessária para resolver este ponto.
- **Risco/validação:** baixo/médio. Testar exceções no corpo e lifecycle e preservar override preexistente.
- **Benefício/esforço:** isolamento previsível; pequeno. Coordenar com BE-012.

### BE-014 — Interface analítica ampla e registros pouco tipados

**P2 · Oportunidade · Confiança alta**

- **Evidência/local:** app/repositories/analytics.py:40 expõe nove listas e várias coberturas; Panorama também trabalha com list[dict].
- **Impacto:** doubles amplos e convenções de chaves implícitas. Para Gold, copiar a interface poderia incentivar carga integral de tabelas.
- **Recomendação/arquivos:** tipar registros internos estáveis por fatia. Desenhar portas Gold estreitas só após dicionário, grão e consultas aprovados.
- **Risco/validação:** médio, alto se mudar semântica da fonte. Preservar adaptador sintético e falha fechada.
- **Benefício/esforço:** fronteira verificável; médio. Não criar interfaces futuras vazias.

### BE-015 — Adaptadores sintéticos expõem listas mutáveis compartilhadas

**P3 · Oportunidade · Confiança alta sobre a estrutura**

- **Evidência/local:** app/repositories/panorama.py usa listas de classe; analytics.py faz cópias rasas.
- **Impacto:** uma mutação acidental pode contaminar instâncias ou testes. Nenhuma mutação por endpoint foi observada.
- **Recomendação/arquivos:** cópia profunda da fixture por instância ou registros imutáveis, escolhendo solução mínima.
- **Risco/validação:** baixo. Mutação aninhada numa instância não afeta outra nem fixture.
- **Benefício/esforço:** isolamento; pequeno.

### BE-016 — Dependências backend pouco reproduzíveis

**P2 · Oportunidade · Confiança alta**

- **Evidência/local:** backend/requirements.txt deixa quase todas as versões abertas, embora runtime e decisões tenham versões registradas.
- **Impacto:** builds podem resolver versões diferentes sem mudança de código.
- **Recomendação/arquivos:** tarefa própria para constraints/lock Python 3.12 e política de atualização; avaliar dependências de teste separadas, sem trocar gerenciador.
- **Risco/validação:** médio. Ambiente limpo, pip check, suíte e imagem com PostgreSQL descartável.
- **Benefício/esforço:** reprodutibilidade; médio. Não foi demonstrada vulnerabilidade atual.

### BE-017 — Scaffold Gold abre sessão sem executar operação de banco

**P3 · Oportunidade · Confiança alta**

- **Evidência/local:** backend/scripts/load_gold.py importa engine/modelo e abre sessão, mas apenas enumera CSV.
- **Impacto:** infraestrutura e aparência transacional sem uso.
- **Recomendação/arquivos:** remover imports/sessão/rollback enquanto continuar scaffold; conservar aviso de carga não implementada.
- **Risco/validação:** baixo. Diretório ausente, vazio e CSV artificial não carregam dados.
- **Benefício/esforço:** simplificação honesta; pequeno. A ingestão é DE-06, não esta refatoração.

### BE-018 — Docstring atribui fixture demonstrativa ao PRD/Figma

**P3 · Problema confirmado · Confiança alta**

- **Evidência/local:** backend/app/synthetic/panorama_fixtures.py atribui controles ao PRD/protótipo, mas ADR-0006 registra que números e calendário são decisões demonstrativas.
- **Impacto:** fixture pode ser tratada como requisito.
- **Recomendação/arquivos:** corrigir somente a atribuição textual.
- **Risco/validação:** mínimo; revisão da ADR-0006.
- **Benefício/esforço:** rastreabilidade correta; trivial. Não alterar valores.

### BE-019 — Wrappers genéricos sem consumidores encontrados

**P3 · Hipótese a validar · Confiança alta sobre ausência de uso interno observado**

- **Evidência/local:** backend/app/schemas/common.py define AnalyticalResponse e PaginatedResponse, sem consumidores backend encontrados.
- **Impacto:** padrões ociosos sugerem arquitetura que endpoints não usam.
- **Recomendação/arquivos:** confirmar uso externo; remover somente se internos e sem usuários. Preservar AnalyticalMetadata, que é usado.
- **Risco/validação:** baixo internamente, desconhecido externamente; busca global, OpenAPI e contratos.
- **Benefício/esforço:** remover abstração sem uso; pequeno. Não migrar endpoints só para aproveitar wrappers.

### BE-020 — Mecânica de competência repetida

**P3 · Oportunidade · Confiança alta**

- **Evidência/local:** parsing/iteração de meses se repetem em analytics, Panorama, UC, Receita e Operação.
- **Impacto:** correção mecânica exige vários pontos.
- **Recomendação/arquivos:** helper puro pequeno; defaults, mensagens, limites e precedência permanecem específicos de cada contrato.
- **Risco/validação:** médio. Ano/mês inválido, fronteira de ano, formato não canônico, parâmetros ausentes e precedência.
- **Benefício/esforço:** menos repetição; pequeno/médio. Prioridade posterior.

## C. Inventário dos achados — Frontend

### FE-001 — Recursos exclusivos do Panorama estão em shared

**P2 · Oportunidade · Confiança alta**

- **Evidência/local:** shared/analytics, shared/filters, shared/ui/MetricCard.tsx e ContentState.tsx conhecem contratos e estados específicos do Panorama.
- **Impacto:** nomes transversais escondem ownership exclusivo.
- **Recomendação/arquivos:** mover recursos/testes para features/panorama, preservando Button, Modal, tema e transporte compartilhados.
- **Risco/validação:** baixo/médio. Fronteiras, filtros, histórico, fundamentos e estados.
- **Benefício/esforço:** ownership claro; médio. ADR-0013 adiou essa extração; atualizá-la explicitamente ao executar.

### FE-002 — Fixture, calculadora e utilitários juntos

**P2 · Problema confirmado · Confiança alta**

- **Evidência/local:** shared/analytics/syntheticData.ts reúne opções, registros, geração, formatação e calculateSyntheticPanorama.
- **Impacto:** mistura produção e suporte de testes com razões diferentes para mudar.
- **Recomendação/arquivos:** separar opções/formatação e fixtures.test-support.ts na feature Panorama.
- **Risco/validação:** médio. Zero, mês parcial, comparação anual e escalas.
- **Benefício/esforço:** fronteira clara; médio. Não foi demonstrado fallback sintético ativo nem que toda fixture entra no bundle.

### FE-003 — AIInsightCard reúne narrativa, estado e drawer

**P2 · Oportunidade · Confiança alta**

- **Evidência/local:** features/panorama/AIInsightCard.tsx:31 formatação/narrativa; :173 estado/foco; :440 drawer/fundamentos. Recebe retorno amplo do hook.
- **Impacto:** mudanças independentes convergem no cartão.
- **Recomendação/arquivos:** panorama-insight-presentation.ts, PanoramaInsightDetails.tsx e props menores.
- **Risco/validação:** médio. Foco, Escape, 409, retry, evidência e hipótese.
- **Benefício/esforço:** testes puros/composição clara; médio. Preservar drawer lateral, sem trocar por Modal central.

### FE-004 — Mutações de Ordens coordenadas no diálogo

**P2 · Oportunidade · Confiança alta**

- **Evidência/local:** OrderActionsDialog.tsx:44 combina consulta, mutação, cache versionado, reconciliação, refs e UI.
- **Impacto:** protocolo operacional é difícil de testar isolado.
- **Recomendação/arquivos:** hook useOrderMutation.ts; diálogo mantém rascunho, foco e confirmação visual.
- **Risco/validação:** alto. Preservar guardas de sessão, versão, duplo envio, conflito e ausência de retry automático.
- **Benefício/esforço:** teste independente com cache real; médio/alto. Não remover guards.

### FE-005 — Chaves e invalidações de Ordens espalhadas

**P2 · Problema confirmado · Confiança alta**

- **Evidência/local:** detalhe e histórico repetidos em página, diálogo e fundamentos; invalidações divididas entre callback e diálogo.
- **Impacto:** política de cache demanda vários pontos.
- **Recomendação/arquivos:** features/ordens/order-queries.ts e política clara de invalidação.
- **Risco/validação:** médio. Lista/histórico atualizados e versão mais nova preservada.
- **Benefício/esforço:** consistência; pequeno/médio. Não se comprovou requisição duplicada efetiva.

### FE-006 — Parser do snapshot e regras de ação no mesmo módulo

**P2 · Problema confirmado · Confiança alta**

- **Evidência/local:** order-actions.ts:4 tem rótulos/erros; a partir de :38, parser de snapshot histórico.
- **Impacto:** compatibilidade de snapshot evolui independentemente das ações.
- **Recomendação/arquivos:** order-foundation.ts com parser e tipos; atualizar consumidor.
- **Risco/validação:** baixo/médio. Legacy, partial, versão desconhecida e campos adicionais opacos.
- **Benefício/esforço:** separação; pequeno. Não usar decoder analítico para snapshot.

### FE-007 — Regras pequenas de Ordens duplicadas

**P2 · Problema confirmado · Confiança alta**

- **Evidência/local:** prioridades repetidas em shared/api/orders.ts e ordens-query.ts; rótulos de status em dois locais; validação UC no parser e formulário.
- **Impacto:** exibição e filtro podem divergir.
- **Recomendação/arquivos:** reutilizar constantes do contrato e centralizar labels/validação pura na feature.
- **Risco/validação:** baixo. Preservar campo vazio omitido pelo formulário versus valor vazio explícito da URL; testar controles, Unicode e limites.
- **Benefício/esforço:** pequeno. Autorização/transições continuam no servidor.

### FE-008 — Histórico UC inclui painel, erro e diálogo

**P2 · Oportunidade · Confiança alta**

- **Evidência/local:** UC360History.tsx define ErrorMessage, HistoryPanel e EvidenceDialog.
- **Impacto:** overview depende de arquivo de histórico.
- **Recomendação/arquivos:** UC360Error.tsx e UC360EvidenceDialog.tsx; manter configuração perto do painel.
- **Risco/validação:** médio. Seleção, foco, fechamento, cobertura e paginação.
- **Benefício/esforço:** dependências mais claras; médio. UC360Page permanece coordenador.

### FE-009 — Tipos do histórico não vinculam seção e registro

**P2 · Oportunidade · Confiança alta**

- **Evidência/local:** uc360/contract.ts usa Record<string, unknown>, união ampla e cast; apresentação escolhe campos por string.
- **Impacto:** coluna e tipo de seção podem não corresponder.
- **Recomendação/arquivos:** mapa HistoryItemBySection e colunas tipadas; preservar campos externos desconhecidos.
- **Risco/validação:** médio. Seis históricos, campos nulos, datas e unidades.
- **Benefício/esforço:** coerência entre decoder e apresentação; médio. Sem engine genérica de tabela.

### FE-010 — Decoder UC aceita paginação impossível

**P2 · Problema confirmado e reproduzido · Confiança alta**

- **Evidência/local:** uc360/contract.ts:387 e histórico em :423 aceitam page=0, page_size=0, total=9, total_pages=99; experimento em memória confirmou.
- **Impacto:** resposta inválida chega à UI.
- **Recomendação/arquivos:** decoder de paginação local compartilhado pelos dois endpoints.
- **Risco/validação:** baixo/médio. Rejeitar zeros/frações/incoerência; manter vazio e página além do fim válidos.
- **Benefício/esforço:** proteção concreta; pequeno. É correção contratual.

### FE-011 — ReceitaPage mistura coordenação e contexto visual

**P2 · Oportunidade · Confiança alta**

- **Evidência/local:** ReceitaPage.tsx coordena URL/query e ainda monta contexto territorial, breadcrumbs, refinamentos e ações.
- **Impacto:** mudanças visuais concorrem com navegação e consulta.
- **Recomendação/arquivos:** componente de filtros aplicados/refinamento com dados e callbacks explícitos.
- **Risco/validação:** médio. Hrefs, filtros, refinamento, rascunho e cancelamento.
- **Benefício/esforço:** legibilidade; médio. Sem subdiretório obrigatório ou viewmodel grande.

### FE-012 — RevenueSeries mistura geometria, DOM e tabela

**P2 · Oportunidade · Confiança alta**

- **Evidência/local:** RevenueSeries.tsx contém cálculo de coordenadas, ResizeObserver, SVG interativo e tabela.
- **Impacto:** testar geometria exige montar interface.
- **Recomendação/arquivos:** revenue-chart.ts e RevenueSeriesChart.tsx; tabela separada somente se ajudar.
- **Risco/validação:** médio. Nulos, negativos, zero, singleton, resize, tooltip e teclado.
- **Benefício/esforço:** regra visual testável; médio. Sem nova biblioteca.

### FE-013 — Formatação e marcador de dimensão ausente repetidos

**P2 · Problema confirmado · Confiança alta**

- **Evidência/local:** formatadores de competência e moeda repetem-se em Receita/Panorama; sentinel __grid360_missing__ aparece na página, breakdown e formulário.
- **Impacto:** diferenças de precisão, sinal e rótulo.
- **Recomendação/arquivos:** revenue-format.ts e helper do sentinel; usar formatadores UC existentes. Compartilhar entre features apenas variantes realmente iguais.
- **Risco/validação:** médio. Preservar quatro casas do preço, zero/nulo, sinal e fusos.
- **Benefício/esforço:** consistência; pequeno/médio. Não uniformizar datas com fusos diferentes.

### FE-014 — AssistentePage mistura estado da conversa e renderização

**P2 · Oportunidade · Confiança alta**

- **Evidência/local:** AssistentePage.tsx:33 define contexto/estado; :123 renderiza evidências; :278 controla envio, retry e limpeza.
- **Impacto:** política da conversa é testada junto à UI.
- **Recomendação/arquivos:** conversation-state.ts e AssistantMessage.tsx; useConversation apenas se a API for pequena.
- **Risco/validação:** médio/alto. Três turnos, limite, contextEligible, retry manual, memória e texto escapado.
- **Benefício/esforço:** lógica testável; médio. Não persistir histórico.

### FE-015 — Modal sticky aponta para descrição inexistente

**P2 · Problema confirmado · Confiança alta**

- **Evidência/local:** shared/ui/Modal.tsx atribui aria-describedby, mas só renderiza descrição em cabeçalho inline; PanoramaFoundations passa descrição com header sticky.
- **Impacto:** relação acessível aponta para elemento ausente.
- **Recomendação/arquivos:** renderizar descrição nas duas variantes e criar Modal.test.tsx.
- **Risco/validação:** baixo. Nome/descrição, foco, Escape, reabertura e retorno ao acionador.
- **Benefício/esforço:** correção concreta; pequeno.

### FE-016 — Foco e aria-invalid dependem da redação de erro em Operação

**P2 · Problema confirmado · Confiança alta**

- **Evidência/local:** OperationFilters.tsx usa includes/regex sobre mensagens para escolher campo e foco; operations-state.ts retorna string[].
- **Impacto:** mudar texto pode mudar comportamento.
- **Recomendação/arquivos:** issues com field/code/message, mantendo texto necessário.
- **Risco/validação:** baixo/médio. Intervalo, máximo de 120 meses, alimentador e primeira falha.
- **Benefício/esforço:** comportamento estável à redação; pequeno/médio.

### FE-017 — Formulário de período UC diverge do parser

**P2 · Problema confirmado · Confiança alta**

- **Evidência/local:** UC360PeriodForm permite ano 0000, rejeitado pelo parser; erro sem associação de campo/foco.
- **Impacto:** formulário aparenta aceitar valor que falhará ao aplicar.
- **Recomendação/arquivos:** validador puro comum e erros por campo.
- **Risco/validação:** baixo. Ano 0000, parcial, invertido, recarga e rascunho.
- **Benefício/esforço:** consistência e acessibilidade; pequeno. Preservar type=month nesta tarefa.

### FE-018 — AnalysisContext declara dl sem dt/dd

**P3 · Problema confirmado · Confiança alta**

- **Evidência/local:** AssistentePage.tsx:123 usa dl/div com texto concatenado.
- **Impacto:** semântica HTML incompatível com conteúdo.
- **Recomendação/arquivos:** pares dt/dd ou lista, podendo acompanhar FE-014.
- **Risco/validação:** baixo; teste semântico.
- **Benefício/esforço:** acessibilidade; pequeno.

### FE-019 — Cor de série duplicada

**P3 · Oportunidade · Confiança alta**

- **Evidência/local:** panorama-series-chart.css e operacao/operation-series.css repetem cores clara/escura.
- **Impacto:** dois pontos de manutenção para o mesmo papel.
- **Recomendação/arquivos:** token semântico em styles/tokens.css e consumo pelos dois CSS.
- **Risco/validação:** baixo; comparação visual nos temas.
- **Benefício/esforço:** consistência; pequeno. Não substituir por cor de marca de outro papel.

### FE-020 — README descreve estágio anterior

**P3 · Problema confirmado · Confiança alta**

- **Evidência/local:** frontend/README.md afirma que outras páginas ainda estão somente no escopo visual; código já contém jornadas e consultas demonstrativas.
- **Impacto:** orientação operacional desatualizada.
- **Recomendação/arquivos:** atualizar capacidades atuais e limites Gold.
- **Risco/validação:** mínimo; revisão documental/links.
- **Benefício/esforço:** pequeno. Preservar histórico e estado do PRD.

### FE-021 — Testes de Receita concentram responsabilidades

**P2 · Oportunidade · Confiança alta**

- **Evidência/local:** ReceitaPage.test.tsx mistura parser URL, decoder, gráfico, refinamento e jornadas.
- **Impacto:** falhas simples exigem navegar teste amplo.
- **Recomendação/arquivos:** revenue-filters.test.ts, contract.test.ts, RevenueSeries.test.tsx; jornadas integradas permanecem na página.
- **Risco/validação:** médio. Transferir cenários sem perder teste API → componente; comparar comportamento, não contagem.
- **Benefício/esforço:** diagnóstico mais preciso; médio. Não substituir integração por testes unitários.

### FE-022 — Falha de import lazy merece investigação

**P2 · Hipótese · Confiança média**

- **Evidência/local:** app/router.tsx usa Suspense sem Error Boundary local para rejeição de chunk.
- **Impacto potencial:** falha pode escapar da área de conteúdo.
- **Recomendação/arquivos:** reproduzir e definir UX antes de implementar recuperação.
- **Risco/validação:** médio; simular import rejeitado e conferir layout.
- **Benefício/esforço:** resiliência potencial. Nenhuma falha foi observada; não incluir no pacote inicial.

## D. Achados transversais

### TR-001 — Guias contradizem aprovação da decisão Gold

**P1 antes da integração Gold · Problema confirmado · Confiança alta**

ADR-0002 está aprovada; docs/services/backend.md e docs/agents/genai-gold.md ainda a chamam de proposta.

**Recomendação:** atualizar guias para afirmar Backend executor único e fluxo GenAI planeja/sintetiza. Preservar como pendentes catálogo, identidade, carga, papel restrito e auditoria. Conferir também o índice e cabeçalho da ADR-0006 sem inferir aprovação apenas pelo índice.

**Risco/esforço:** baixo/pequeno. Validar textos e links. Não reescrever como contemporâneos os registros históricos anteriores à aprovação.

### TR-002 — Conferência do contexto respondido desigual

**P2 · Oportunidade · Confiança alta**

Receita não passa recorte esperado ao decoder; UC não compara consistentemente UC, janela e página; detalhe/histórico de ordens não validam todos os IDs. Panorama e Operação fazem checagens contextuais.

**Impacto:** resposta válida de outro contexto poderia ser associada à chave atual. Não há erro ocorrido demonstrado; query keys e AbortSignal protegem corridas do cliente.

**Recomendação:** conferir no domínio os campos já publicados. O padrão escolhido pelo servidor continua válido quando o período não foi enviado.

**Risco/esforço:** médio/médio. Testar resposta válida e mesma resposta com UC/ID/período/página divergentes.

### TR-003 — Invariantes de paginação divergentes

**P2 · Problema confirmado em UC; oportunidade nos demais · Confiança alta**

FE-010 prova aceitação inválida. Outros decoders protegem parcelas diferentes; schema backend Pagination não estabelece relações próprias.

**Recomendação:** corrigir UC localmente primeiro; extrair helper só quando houver segundo consumidor com semântica igual. Preservar total_pages=0 no vazio e página além do final vazia; não impor page <= total_pages.

**Risco/esforço:** baixo/médio. Testar limites, fórmula e cardinalidade.

### TR-004 — Falta smoke produtor → decoder

**P2 · Oportunidade · Confiança alta**

Existem testes HTTP no Backend e fixtures/mock no Frontend, mas CI Compose verifica HTML/health, não compatibilidade entre JSON FastAPI real e decoder real.

**Recomendação:** teste sintético determinístico de Receita, UC e Ordens, incluindo estados completo/parcial/vazio/conflito. Sem gerar cliente ou instalar biblioteca.

**Risco/esforço:** médio. Alteração controlada de campo obrigatório deve quebrar o teste. PostgreSQL continua necessário para concorrência; sintético não prova Gold.

### TR-005 — Limite de ID de ordem excede inteiro seguro JS

**P3 · Incompatibilidade latente confirmada · Confiança alta**

API aceita até 2^63−1; cliente usa corretamente Number.isSafeInteger, limitado a 2^53−1.

**Recomendação:** documentar limite interoperável e decidir a política antes de IDs importados. Não remover proteção nem mudar formato como limpeza.

**Risco/esforço:** pequeno para documentar, grande se mudar contrato. Testar 2^53−1, 2^53 e 2^63−1.

### TR-006 — UI interpreta envelope bruto de conflito em dois pontos

**P2 · Problema confirmado · Confiança alta**

CreateOrder.tsx e features/ordens/order-actions.ts percorrem ApiError.data.error manualmente.

**Recomendação:** decoder tipado pequeno no domínio compartilhado. UI mantém mensagens e ações específicas.

**Preservar:** chave idempotente após falha ambígua; atualização de fila stale; link de ordem ativa; conflitos de edição exigem revisão.

**Risco/esforço:** pequeno. Testar payload malformado, IDs, rede e autorização.

### TR-007 — Limites de identificação UC dependem de homologação

**P3 · Hipótese · Confiança média**

Consulta UC aceita até 100 caracteres e criação operacional até 50. A amostra atual não demonstra incompatibilidade.

**Recomendação:** validar chaves reais na futura integração; não harmonizar limites por estilo.

**Validação:** seguir uma UC real autorizada através de busca, suspeita e criação.

### Pendências funcionais não são defeitos de organização

- Ingestão/idempotência Gold ainda não implementadas.
- Dicionário, grãos e fórmulas Gold pendentes.
- Executor planejar → executar → sintetizar pendente.
- Identidade/escopo real e auditoria durável pendentes.
- Guarda demonstrativa do insight deve permanecer até integração correta.
- Calendários, métricas e fórmulas sintéticas divergentes são decisões documentadas.

## E. Estrutura futura recomendada

Legenda: criar (+), mover (→), preservar (=), condicional (?).

### Backend

    backend/
      app/
        api/v1/analytics_route.py          =
        api/v1/endpoints/                  = endpoints públicos
        core/ db/ models/                  =
        repositories/analytics.py          = adaptador atual
        repositories/panorama.py           =
        schemas/analytics.py               suporte comum e KPIs inicialmente
        schemas/revenue.py                 + Receita
        schemas/uc360.py                   contratos UC organizados
        schemas/inspection_queue.py        recebe schemas da fila
        schemas/operations.py               recebe continuidade
        schemas/inspections.py              =
        schemas/order_snapshot.py           =
        schemas/common.py                   ? remover wrappers sem consumidores
        services/analytics.py               apoio comum inicialmente
        services/continuity.py              + cálculo comum
        services/revenue_analytics.py       orquestração
        services/revenue_decomposition.py   + regra pura
        services/uc_analytics.py            busca/overview/legado
        services/uc_history.py              + históricos
        services/uc_coverage.py             ? helpers com consumidores reais
        services/inspections.py             = comandos/transação
        services/order_queries.py           ? extração opcional
        services/inspection_analytics.py     =
        services/panorama.py                 =
        services/panorama_insights.py        recebe verificação
        services/genai_client.py             transporte deduplicado internamente
        services/months.py                   ? extração posterior
      tests/support/database.py              +
      tests/support/migrations.py            +
      tests/test_*.py                        = cenários atuais
      alembic/                                =
      scripts/load_gold.py                   scaffold simplificado

Compatibilidade OpenAPI deve orientar a organização definitiva de schemas; não basta preservar imports Python.

### Frontend

    frontend/src/
      app/ layouts/                          =
      shared/api/client.ts                   =
      shared/api/query-client.ts             =
      shared/api/orders.ts                   = inicialmente
      shared/api/orders/                     ? divisão posterior
      shared/theme/                           =
      shared/ui/Button.tsx                    =
      shared/ui/Modal.tsx                     corrigir descrição
      shared/ui/Modal.test.tsx                +
      features/panorama/
        PanoramaPage.tsx                      =
        types.ts                              ← shared/analytics
        contract.ts                           ← contrato Panorama
        usePanoramaData.ts                    ←
        usePanoramaFilters.ts                 ←
        PanoramaFilters.tsx                   ←
        PanoramaFoundationMetric.tsx          ←
        PanoramaContentState.tsx              ←
        panorama-filter-options.ts            +
        fixtures.test-support.ts              +
        PanoramaInsightDetails.tsx            +
        panorama-insight-presentation.ts      +
      features/receita/
        ReceitaPage.tsx                        coordenação
        RevenueAppliedFilters.tsx              +
        revenue-format.ts                      +
        revenue-chart.ts                       +
        RevenueSeriesChart.tsx                 +
        contract.ts                            = inicialmente
      features/uc360/
        UC360Page.tsx                          =
        UC360History.tsx                       painel
        UC360EvidenceDialog.tsx                +
        UC360Error.tsx                         +
      features/ordens/
        order-queries.ts                       +
        useOrderMutation.ts                    +
        order-foundation.ts                    +
        order-presentation.ts                  ? se necessário
      features/assistente/
        conversation-state.ts                  +
        AssistantMessage.tsx                   +
        useConversation.ts                     ? API pequena
      features/operacao/ inspecoes/ dev-contracts/ =
      styles/ test/                             =

Não criar todas as pastas/arquivos de uma vez. Features pequenas podem permanecer planas.

## F. Plano de refatoração priorizado

1. **Baseline e proteção:** ambiente reproduzível, TR-001, smoke produtor/decoder e suporte de testes seguro. Testes de infraestrutura vêm antes de mudar seus imports.
2. **Correções de fronteira:** FE-010, FE-015, FE-016, FE-017, FE-018, TR-002 e TR-006. Separar correção observável de movimentação estrutural.
3. **Ownership e contratos:** schemas backend por domínio; duplicação de perfil UC; Panorama fora de shared; fixture de teste separada.
4. **Regras/coordenadores:** continuidade, cobertura UC, decomposição Receita, validação de insight, transporte GenAI, consultas/mutações Ordens, conversa Assistente e geometria da série.
5. **Simplificação:** formatos, wrappers confirmadamente sem uso, fixtures mutáveis, scaffold Gold, token visual e helpers de competência.
6. **Gold:** somente após catálogo, grão, cobertura, lote, identidade/escopo, papel restrito, auditoria e consultas reais estarem definidos.

**Dependências sequenciais:** schemas Receita → demais schemas; suporte de testes → reorganização de testes; validação insight → transporte GenAI; snapshots → queries/labels de Ordens → mutação; ownership Panorama → fixture → insight; contexto Receita → série → formatação/testes.

**Possíveis paralelos:** Backend e Frontend com contratos congelados; domínios UC, Receita, Operação e Assistente quando os arquivos/testes estiverem reservados a responsáveis distintos. Não paralelizar edições da mesma feature, dos mesmos testes, CI, dependências ou documentos compartilhados.

## G. Backlog pronto para subagentes Luna

Este backlog é preparação para a Fase 2; nenhuma tarefa foi delegada para implementação.

### Convenções comuns

- Cada agente recebe apenas sua tarefa e arquivos reservados.
- Preservar endpoints, payloads, fórmulas, precisão, estados, acessibilidade, cache e decisões descritas em H.
- Sem dependências novas ou mudanças de representação sem decisão.
- Executar testes da fatia e gates correspondentes; atualizar documentação somente pelo integrador.
- Comandos abaixo pertencem à Fase 2.

Abreviações:

- **B(arqs):** em backend/, python -m pytest -q arqs.
- **F(caminho):** em frontend/, npm.cmd test -- caminho.
- **Gate backend:** suíte completa, python -m compileall -q app tests scripts e git diff --check.
- **Gate frontend:** npm.cmd run check:boundaries, npm.cmd run format:check, npm.cmd run lint, npm.cmd run build e git diff --check.
- PostgreSQL requer banco descartável explicitamente configurado. Mudança visual/interativa exige navegador nos dois temas.

### Backlog Backend

| ID — tarefa | Arquivos permitidos e mudança | Aceite / preservar | Dependência / paralelismo | Validação | Complexidade |
|---|---|---|---|---|---|
| L-01 Suporte testes | conftest, test_migrations, consumidores, novos tests/support | Restaurar overrides anteriores em finally; guardas banco | Antes de mexer nesses imports; reservar infraestrutura | B(test_migrations, active_uc_migration, order_postgres_security, inspections), depois suíte | Média |
| L-02 Schema Receita | analytics, novo revenue, imports/tests Receita | JSON, OpenAPI, defaults e nulidade iguais | Antes L-03; schemas exclusivos | B(revenue_dev03, analytics_kpis_revenue, analytics_openapi) | Média |
| L-03 Demais schemas | analytics/uc360/queue/operations e imports | Perfil sem campos duplicados; componentes OpenAPI compatíveis | Após L-02; não paralela schema | B(analytics_ucs, uc360_dev04, inspection_queue_dev05, operations_dev08, operations_summary, analytics_openapi) | Média |
| L-04 Continuidade | analytics, operations, endpoint e novo continuity | Mesmo cálculo, cobertura, numeradores e arredondamento | Após L-03; paralela Receita/UC | B(analytics_operations, operations_dev08, operations_summary) | Média |
| L-05 Histórico UC | uc_analytics, novo uc_history/coverage se usado, endpoint e testes | Seis seções; resumo independe da página | Após L-03; agente exclusivo UC | B(analytics_ucs, uc360_dev04) | Alta |
| L-06 Decomposição Receita | revenue_analytics, novo revenue_decomposition, testes | Decimal, extremos, HALF_UP, elegibilidade e fechamento iguais | Após L-02; paralela L-04/L-05 | B(revenue_dev03, analytics_kpis_revenue) | Média-alta |
| L-07 Integridade insight | endpoint ai, panorama_insights, testes | Recorte adulterado segue rejeitado; status/envelope iguais | Exclusiva nesses arquivos; antes L-08 | B(ai, ai_chat, ai_insights) | Média |
| L-08 Transporte GenAI | genai_client e testes | Paths/auth/timeout/correlação idênticos | Após L-07; sem operação Gold nova | B(ai_chat, ai_insights) | Média |
| L-09 Isolamento sintético | repositories e teste novo | Mutação aninhada não vaza; números iguais | Reservar repositories | B(panorama, revenue_dev03, uc360_dev04, inspection_queue_dev05) | Baixa |
| L-10 Consultas ordens, opcional | inspections service, novo order_queries, endpoint/tests | Sem novos commits; filtros/projeção/paginação iguais | Após L-01; exclusiva Ordens | B(orders_dev06, inspections, order_lifecycle_dev07, order_mutation_contract) | Média |
| L-11 Scaffold/atribuição | load_gold e docstring panorama fixture | Nenhuma carga; saída informativa e valores preservados | Arquivos exclusivos | Diretórios artificiais, conferência ADR-0006, diff check | Baixa |
| L-12 Dependências | requirements/constraints, Dockerfile, CI, README | Ambiente Python 3.12 reproduzível; sem upgrade disfarçado | Janela tooling exclusiva | pip check, suíte, imagem e PostgreSQL descartável | Média |

### Backlog Frontend

| ID — tarefa | Arquivos permitidos e mudança | Aceite / preservar | Dependência / paralelismo | Validação | Complexidade |
|---|---|---|---|---|---|
| L-13 Modal acessível | Modal.tsx e teste novo | Descrição nas duas variantes; foco/Escape/reabertura | Independente; reservar Modal | F(Modal.test.tsx) e testes Panorama | Baixa |
| L-14 Paginação UC | contract.ts/contract.test.ts | Paginação impossível recusada; vazio/página além fim válidos | Antes de outra edição do contrato UC | F(src/features/uc360) | Baixa |
| L-15 Período UC | PeriodForm, uc360-state, testes | Mesmo parser/form; erro por campo/foco | Sequencial se compartilhar teste de página | F(src/features/uc360) | Baixa |
| L-16 Apresentação UC | History, novos Error/Dialog, tipos/tests | Tipos vinculam seção; seis históricos iguais | Após L-14; reservar UC | F(src/features/uc360), navegador | Média |
| L-17 Ownership Panorama | shared exclusivos, destinos, imports/tests | Requests/estados/UI iguais; exceção ADR encerrada explicitamente | Antes L-18/L-19; reservar Panorama | F(src/features/panorama), fronteiras | Média |
| L-18 Suporte Panorama | syntheticData, opções/formatação/fixture | Produção não importa calculadora; defaults/controles iguais | Após L-17 | Testes Panorama/MetricCard, zero/parcial/anual | Média |
| L-19 Insight visual | AIInsightCard, detalhes/presentation/testes | Drawer, foco, lote, retry/evidência iguais | Após L-18 | F(src/features/panorama), navegador | Média |
| L-20 Snapshot Ordens | order-actions, novo order-foundation, consumidor/testes | Legacy/parcial/unknown iguais | Antes L-21; reserva Ordens | F(OrderFoundationsDialog.test.tsx) | Baixa |
| L-21 Queries/labels Ordens | order-queries, labels/validador, filtros/página/history | Mesmas keys, requests e rótulos | Após L-20; feature exclusiva | F(src/features/ordens) | Média |
| L-22 Mutações Ordens | diálogo, hook novo, callback/tests | Guards/versionamento/reconciliação preservados | Após L-21 | F(src/features/ordens), navegador/API | Alta |
| L-23 Contexto Receita | ReceitaPage, componente contexto, testes | URL/query na página; links/refino iguais | Agente exclusivo Receita | F(src/features/receita), navegador | Média |
| L-24 Série Receita | RevenueSeries, chart puro/componentes/tests | Null, negativos, resize, tooltip/teclado iguais | Após L-23, ou testes reservados | F(src/features/receita), navegador | Média |
| L-25 Formatação/testes Receita | formatadores, componentes, testes locais | Precisões/sentinels/jornadas preservados | Após L-23/L-24 | F(src/features/receita) | Média |
| L-26 Issues Operação | operations-state, filtros/tests | Campo/code controla foco; URL igual | Paralela outras features | F(src/features/operacao) | Baixa-média |
| L-27 Conversa Assistente | página, estado puro, mensagem/tests | Três turnos, memória, retry, texto escapado | Paralela outras features | F(src/features/assistente), navegador | Média |
| L-28 Conflito tipado | domínio shared orders, CreateOrder, order-actions/tests | Mesmas ações/mensagens, sem percorrer JSON cru | Coordenar L-20/L-22 | Ordens e Inspeções tests | Baixa-média |
| L-29 Contexto respondido | hooks/decoders Receita, UC, orders em subfatias | Recorte/ID errado recusado; defaults válidos | Executar por feature, após extrações | Testes de cada feature com resposta divergente | Média |
| L-30 Token série, opcional | tokens.css e dois CSS | Mesmas cores/temas | Janela coordenada Panorama/Operação | Comparação visual | Baixa |

### Integração e fechamento

| ID — tarefa | Arquivos permitidos | Aceite | Dependência/paralelo | Validação | Complexidade |
|---|---|---|---|---|---|
| L-31 Produtor → decoder | Teste/script dedicado; CI em fase posterior | JSON FastAPI sintético aceito por decoders reais; campo obrigatório incorreto falha | Após contratos; não disputar testes de página | completo/parcial/vazio e ordens list/detail/history/conflict | Média |
| L-32 Documentação | guias Backend/GenAI, README frontend, arquitetura/ADRs | Aprovado versus pendente corretamente descritos | Um integrador; TR-001 primeiro | Busca de termos obsoletos, links e revisão cruzada | Baixa |
| L-33 Tipagem fonte, piloto | Uma fatia de registros e consumidores | Tipar campos existentes sem inventar Gold/JSON | Após extração de domínio | Testes do domínio/fonte indisponível | Média |
| L-34 Simplificações condicionais | wrappers sem usuários; helper competência em tarefa distinta | Consumidores verificados e políticas específicas mantidas | Após confirmação BE-019 e extrações | Busca/OpenAPI ou testes de calendário | Baixa-média |

### Coordenação das tarefas

- Um responsável por feature por rodada.
- Backend: L-02 → L-03; L-07 → L-08; L-10 depois da infraestrutura.
- Frontend: L-17 → L-18 → L-19; L-20 → L-21 → L-22 → L-28; L-23 → L-24 → L-25.
- L-29 deve ser subdividida entre os donos de Receita, UC e Ordens.
- ReceitaPage.test.tsx, CI, dependências e documentação compartilhada precisam de proprietário exclusivo.
- Revisão final inclui suites completas e fluxos integrados, não apenas testes de cada tarefa.

## H. O que não deve ser refatorado

### Backend

- Camadas atuais são adequadas; não migrar tudo para hexagonal, CQRS ou feature-based.
- Serviços operacionais podem usar Session/ORM diretamente; repository CRUD universal seria indireção.
- Comandos continuam donos de commit/rollback; get_db fecha sessão.
- Replay antes da fonte, índice de ordem ativa, fingerprint, versionamento e transação ordem+histórico são garantias, não complexidade removível.
- Snapshot operacional versionado não deve usar decoder analítico.
- Base neutra, modelos separados e metadados Alembic desacoplados da conexão estão corretos.
- Histórico Alembic não deve ser squashado ou recriado.
- inspection_analytics.py é coeso; panorama.py não precisa de catálogo de estratégias.
- Subclasses de histórico UC podem preservar nomes OpenAPI; não remover sem comparação.
- Health e endpoints legados preservam contratos documentados.

### Frontend

- Preservar features, layout, provedores, lazy loading e fronteiras automatizadas.
- UC360Page já coordena adequadamente; não criar megahook.
- apiClient permanece genérico e não absorve regras de domínio.
- shared/api/orders.ts é legitimamente usado por Inspeções e Ordens; não movê-lo todo para uma feature.
- Componentes pequenos já coesos permanecem na raiz; sem pastas obrigatórias por feature.
- Não criar engine universal de gráficos.
- URL = recorte; Query = estado remoto; local = rascunho/interação.
- Tema, CSS próximo dos gráficos e componentes compartilhados atuais permanecem.
- Sem virtualização, SSR, memoização ou biblioteca nova sem medição/requisito.
- Guards de resposta atrasada e reconciliação não devem ser removidos para encurtar componentes.

### Integração

- ADR-0002: Backend é executor único Gold; GenAI planeja/sintetiza, sem credencial Gold ou callback circular.
- ADR-0006: fontes Panorama e DEV-01 permanecem distintas até revisão semântica aprovada.
- Overview UC e históricos paginados continuam separados.
- Fórmulas, prioridade e transições permanecem no servidor.
- ADR-0015: DEC/FEC consolidados por numeradores/denominadores originais.
- Demo sem login segue ADR-0012.
- /ai/query permanece indisponível até implementação autorizada.
- Dados sintéticos não concluem aceite Gold.

## I. Resultado arquitetural esperado

### Indispensável

1. Ownership claro dos schemas por domínio e do Panorama.
2. Uma implementação para regras repetidas de cobertura, transporte e validação intrafeature.
3. Integridade do insight no caso de uso e contexto respondido conferido antes do cache.
4. Mutações/conversa testáveis sem depender de componentes visuais amplos.
5. Infraestrutura de teste independente, teardown seguro e smoke produtor → decoder.
6. Correções de paginação e acessibilidade concretas.
7. Documentação operacional e dependências reproduzíveis.

### Opcional

- Extração das consultas de Ordens.
- Helper comum de competência.
- Token de série.
- Remoção de wrappers após confirmar ausência de consumidores.
- Divisão de contratos frontend se surgirem fronteiras independentes.
- Error Boundary lazy após reproduzir e definir a recuperação.

Chegar perto de 10/10 depende de fronteiras claras, regras únicas e regressões verificáveis. Não depende de multiplicar pastas ou classes. A base arquitetural já existe; os impedimentos são concentrações e inconsistências localizadas.

## Referências a conferir durante a execução

- docs/architecture/frontend.md
- docs/services/backend.md
- docs/services/frontend.md
- docs/agents/genai-gold.md
- docs/data-dictionary.md
- docs/decisions/0001-arquitetura-frontend.md
- docs/decisions/0002-genai-gold-query-owner.md
- docs/decisions/0004-contratos-analiticos-e-fonte-sintetica.md
- docs/decisions/0006-panorama-fonte-produto-e-contrato-dev01.md
- docs/decisions/0008-exploracao-demonstrativa-receita.md
- docs/decisions/0009-uc360-contratos-de-consulta.md
- docs/decisions/0011-ordem-ativa-por-uc.md
- docs/decisions/0012-autenticacao-individual-das-ordens.md
- docs/decisions/0013-composicao-ui-e-carregamento-frontend.md
- docs/decisions/0014-integracao-do-ciclo-operacional-dev07.md
- docs/decisions/0015-consolidado-demonstrativo-de-continuidade.md

**Estado:** relatório e planejamento da Fase 1. Implementação da Fase 2 não iniciada.
