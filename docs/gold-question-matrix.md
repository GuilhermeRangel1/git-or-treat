# Matriz de perguntas para o catálogo Gold v2

## Revalidação real da matriz — 02/11/2026

A rodada final `20261102T041125_013170Z` executou os 57 casos pela API pública, com sessão individual, Gold v2, Gemini e auditoria reais, reconciliando os valores por controles SQL independentes somente leitura. Resultado: **43 PASS, zero FAIL, cinco BLOQUEADO, sete SEM_AMOSTRA_NO_LOTE e dois NAO_EXECUTADO** (provas técnicas separadas). Os 14 casos em FAIL na rodada `20261102T025654_378948Z` passaram. Nenhum erro de execução. Contas temporárias e sessões removidas. Esse resultado supera apenas as pendências de revalidação da revisão abaixo; não altera a cobertura ou homologa domínios bloqueados.

O runner foi alinhado ao formato legível das respostas sem perder vínculo de números com mês/efeito. A configuração privada recebeu os controles autorizados, incluindo C08/C09 com aceite explícito nesta rodada. O chat Gold usa seleção mínima de observações nos adaptadores Gemini/Groq, com prompt v4 e ingresso de auditoria compatível; nenhuma guarda de fundamentação foi relaxada. GenAI: 4093 testes passaram/4 skips; Backend dirigido: 41 passaram; prova integrada PostgreSQL descartável: 1 passou. Roteiro, resultado por ID, bloqueios e limites no [registro sanitizado da rodada](plans/2026-11-02-genai-assistente-matriz-real.md). IA-01/IA-02/IA-03/IA-06 mantêm seus estados oficiais.

## Revisão de linguagem do Assistente — 02/11/2026

- `Compare a receita de maio e junho de 2026` explicita o mesmo ano nos dois meses antes da extração do calendário. Comparação conserva dois pontos; `receita de maio a junho de 2026` conserva o intervalo. Não usa o relógio nem o último ano do lote para completar um ano ausente. Dias, intervalos invertidos e competências sem cobertura continuam exigindo esclarecimento.
- `Qual município teve a maior receita em junho de 2026?` usa o agrupamento municipal e a ordenação por receita já implementados no executor. O perfil libera essa dimensão somente para receita, além do agrupamento por classe existente. O limite do ranking continua sendo um grupo; município precisa estar no escopo e na evidência autorizada. Comparações agrupadas de receita continuam indisponíveis.
- Caminho: rota interna de planejamento → `QuestionAnalysisPlanner.plan` → calendário/perfil → plano aprovado → executor SQL existente no Backend → rota interna de síntese. O perfil implantável `GRID360_GOLD_RUNTIME_PROFILE` deriva do perfil lógico alterado. A entrada pública continua sendo `/api/v1/ai/questions` no Backend.
- Verificação reproduzível em `ai-agent/`: `python -m pytest -q tests/test_gold_planning_http.py tests/test_gold_temporal.py tests/test_gold_question_filters.py --tb=short` → **124 passaram**. Regressão completa `python -m pytest -q --tb=short` → **4077 passaram, 4 skips**, em container descartável sem rede, com `.env` privado mascarado por arquivo vazio. Ruff dos arquivos alterados e `git diff --check` passaram.
- Prova separada de consulta real: `_admit_plan` + `_query` do Backend reconciliaram o maior faturamento municipal e a receita residencial de junho/2026 com SQL independente na publicação Gold v2 local (`gold_v2`, `gold-catalog-v2`, `gold-csv-v2`). Usado `venergy_genai_reader`, transação `REPEATABLE READ` / `READ ONLY`, prazo SQL de 5 s; somente os estados de sucesso foram registrados. Controles independentes: `SUM(receita_total_reais)` por município, ordenado decrescente com nulos por último e desempate municipal, e soma da mesma medida com `classe_consumo = 'RESIDENCIAL'`. Ambos filtram `competencia = '2026-06'`.
- Limites: HTTP e síntese foram exercitados com modelo controlado; a conferência PostgreSQL foi separada. Não houve nova chamada Gemini, jornada no navegador, alteração de cobertura, credenciais ou permissões. A recusa residencial observada no navegador ainda não está comprovadamente resolvida: consulta reconciliada não prova a saída do provedor. As 14 falhas da matriz anterior não são declaradas corrigidas por estes testes. IA-01/IA-02 mantêm seus estados oficiais.

## Registro anterior da matriz

Matriz versionada para o trabalho de linguagem do núcleo GenAI. As expectativas abaixo vêm do catálogo lógico Gold v2, do contrato de execução e dos critérios do cartão; não usam respostas de fixtures para afirmar resultado sobre a Gold. Os testes de planejamento usam cobertura e valores de dimensão sintéticos explícitos, e não comprovam inventário ou valores do lote real.

| ID | Pergunta | Saída esperada | Verificação independente |
| --- | --- | --- | --- |
| Q04-01 | Qual foi a receita comercial em Jaboatão no último trimestre? | Plano `billing.revenue`; filtro `customer.consumption_class=COMERCIAL` e `geography.municipality=Jaboatão`; últimos 3 meses contíguos na cobertura. | A métrica é receita faturada em R$; classe e município são dimensões permitidas no catálogo. Os valores de município precisam vir da publicação confiável. |
| Q04-02 | Qual foi o faturamento residencial em Olinda nos últimos 12 meses? | Plano de receita faturada; classe `RESIDENCIAL`, município `Olinda` e janela mensal de 12 competências terminando na mais recente recebida. | Aliases e IDs de dimensão são conferidos contra `GRID360_GOLD_PROFILE`; limites vêm da cobertura enviada pelo Backend. |
| Q04-03 | Qual bairro mais perdeu volume residencial no último ano? | `needs_clarification`: não retornar total como ranking; agrupamento por bairro/ordenação não está habilitado no plano Gold atual. | A pergunta exige grupo, ordenação e sentido. `ReadPlanBuilder` não cria esses campos a partir de intenção. |
| Q04-04 | Quanto cresceu a receita comercial em Jaboatão no último trimestre? | `needs_clarification`: falta janela de referência para comparar; nenhum filtro é descartado e não é calculado percentual. | A Gold publica receita faturada; uma janela única não representa comparação. |
| Q04-05 | Quantas UCs com solar em Olinda tiveram queda de consumo no último ano? | `needs_clarification`: Gold v2 registra GD, sem afirmar que a fonte é solar; não retirar filtro solar nem devolver total. | O perfil contém `generation.distributed`; solar não é alias nem atributo físico aprovado. |
| Q04-06 | Qual foi o valor pago em Olinda no último trimestre? | `needs_clarification`: valor pago não é receita faturada e não é publicado por esse indicador. | A definição v2 de `billing.revenue` declara valor faturado; aliás genéricos não podem igualar pagamento. |
| Q04-07 | Qual foi a energia faturada em Olinda no último trimestre? | `needs_clarification`: `energy.consumption` é consumo medido, não energia faturada. | A definição e as limitações de `energy.consumption` distinguem as duas medidas. |
| Q04-08 | Qual foi a receita em Olinda e Jaboatão no último trimestre? | `needs_clarification` sem cláusula de correção explícita; não reduzir a uma cidade. | Dois valores não cabem no filtro escalar atual. |
| Q04-09 | Qual foi a receita em Olinda, não, em Jaboatão no último trimestre? | Plano apenas para Jaboatão, se o valor estiver na cobertura de dimensão dessa publicação. | Regra de correção explícita substitui o local anterior; a autorização do plano é reaplicada. |
| Q04-10 | Qual foi a receita em município ausente do vocabulário recebido? | `needs_clarification`; o nome livre não é transformado em filtro e não é removido. | Correspondência exige valor dinâmico da mesma publicação ou valor estático do perfil. |
| Q04-11 | Qual foi a receita este ano? | Janela de janeiro ao último mês publicado, com período parcial; lacuna interna resulta em esclarecimento. | Data do servidor não participa; limites são primeiro e último dia das competências presentes. |
| Q04-12 | Qual foi a receita no último trimestre? com uma competência faltando | `needs_clarification`; não encurtar para os dois meses presentes nem completar o mês ausente. | Comparar expectativa de três competências consecutivas com a cobertura enviada. |
| Q04-13 | Qual foi o valor pago e faturado? | `needs_clarification` de métrica/definição; não combinar populações ou colunas. | A Gold v2 não oferece uma métrica de pagamento equivalente à receita faturada. |
| Q04-14 | Compare a receita do ano passado com este ano quando a base anterior é zero. | Nesta etapa, esclarecer que comparação não está representada em um plano; não produzir percentual. A regra final para zero/base ausente será exercitada pelo caso público após integração de executor e evidência. | O planejador não calcula variação. Este caso é pendência de integração da resposta e não pode ser marcado como provado por um teste de plano. |

## Evidência e limites desta etapa

- Testes automatizados compõem a pergunta com o catálogo v2 e percorrem `compose_core → question.plan`; checam IDs de métrica/dimensão, filtros, estado e janela. Em 31/10/2026, a execução fora do sandbox resolveu o bloqueio de `asyncio`: os quatro arquivos de catálogo v2, períodos, envelopes e regras do interpretador passaram com 243 testes. A regressão adicional de esclarecimento pelo caso público passou: pergunta anual sem cobertura → esclarecimento → último trimestre mantém receita, classe comercial e município, com limites inclusivos de janeiro a março de 2025 na cobertura controlada.
- Testes síncronos verificam a resolução temporal, preservação de lacunas, validação dos envelopes, dimensões no escopo e regressões de acentos. Não substituem a execução integrada do caso público.
- A composição de produção ainda não fornece `dimension_value_coverage`, não existe rota interna de planejamento ativa e não foi executado lookup contra lote Gold real. O caso público `question.plan` está comprovado com metadados controlados, incluindo Q04-09 (correção de cidade). Q04-14 comprova esclarecimento sem percentual; cálculo numérico com base zero pertence à execução/evidência futura.
- A cobertura mensal identifica competências reportadas no lote. Não prova que a extração da origem trouxe todas as competências existentes. A conclusão de completude exige evidência de reconciliação separada, como registrado no contrato de cobertura.

## Implementação ampliada do GENAI-04 — 31/10/2026

O perfil Gold v2 ativa `structured_dimension_filters`; outros perfis mantêm o comportamento anterior. Cada dimensão é resolvida separadamente, permitindo município + bairro + classe + GD/subgrupo sem perder filtros. Alimentador usa apenas valores publicados pelo Backend. Valor desconhecido, nome ambíguo entre dimensões, múltiplos valores sem correção e exclusão não suportada pedem esclarecimento. `sem GD` é um valor cadastral próprio, não exclusão genérica.

IDs de UC não são enviados como vocabulário. Pedido por UC sem resolução autorizada gera esclarecimento explícito; não se extrai número livre nem se consulta o total silenciosamente. Isso preserva o critério de usar o filtro somente quando a capacidade estiver autorizada, sem criar um cadastro paralelo na GenAI.

Os valores canônicos da publicação prevalecem sobre a grafia de exemplo do perfil. O perfil mantém seus aliases e é enriquecido apenas na requisição. Esclarecimentos de métrica (pago/faturado, energia faturada/medida, interrupção/DEC) e de período preservam os filtros e a janela original; autorização é reaplicada a cada plano, inclusive com permissão revogada.

| Casos adicionais | Resultado comprovado em `test_gold_question_filters.py` |
| --- | --- |
| Município + bairro + classe | Todos os filtros no plano aprovado, sem tratar dimensões diferentes como cidades conflitantes. |
| Classe + GD e classe + GD + subgrupo | Valores e IDs preservados por dimensão. |
| DEC por alimentador e mês | Alimentador publicado reconhecido, janela mensal delimitada. |
| Cidade corrigida explicitamente | Somente o valor corrigido aparece no plano. |
| Subgrupo/alimentador desconhecido; UC sem resolução | Esclarecimento e nenhum plano. |
| Duas classes, dois municípios ou com/sem GD juntos | Esclarecimento, sem reduzir a um valor. |
| Exclusão de classe ou mesmo nome em duas dimensões | Esclarecimento, sem interpretar exclusão como igualdade. |
| Follow-up de cidade e revogação de GD | Recortes herdados preservados; permissão revogada recusa o plano. |
| Escolha de receita, consumo ou DEC após ambiguidade | Métrica selecionada, período e filtros originais preservados. |

Verificações: suíte completa GenAI com 3.620 aprovados, 4 skips e 1 xfail histórico; Backend, contratos internos e produtor, 84 aprovados incluindo HTTP. Execução fora do sandbox confirmou que a limitação anterior era do ambiente restrito, não do `asyncio` no Windows. Após a suíte completa, 21 cenários dirigidos passaram com o ajuste de lint e três casos adicionais de unidade/dimensão sem suporte.

Escopo entregue: interpretação e planejamento pelo núcleo composto, sem fonte/LLM no planejamento. Escopo dos próximos cartões: executor (GENAI-06), transporte/coordenador (GENAI-07), evidência e prova quantitativa real (GENAI-08/09/10). Validação semântica da ADR-0018 continua registrada como pendente; estes testes não a substituem. IA-01/IA-02 não são concluídos por uma matriz de planos.


### Passagem do plano ao contrato Backend

`test_planned_envelope_crosses_backend_contract_without_losing_filters_or_limits` executa o núcleo composto, serializa `QuestionPlanResponse` e o valida em outro processo com os schemas reais do Backend, sem imports entre serviços. Confere igualdade integral do envelope, fingerprint recalculado, filtros de município/bairro/classe, limite 100, ausência de ordenação e janela inclusiva janeiro–março/2025. Os 22 cenários do arquivo passaram. Não abre HTTP interno nem executa SQL; essa distinção preserva o escopo de GENAI-06/07.


### Competências explícitas e filtros obrigatórios — implementação

O planejamento Gold v2 aceita mês e ano escritos (`março de 2025`), competência ISO (`2025-02`), ano nomeado (`ano 2024`) e intervalo com dois extremos completos (`de dezembro de 2024 a fevereiro de 2025`). A cobertura recebida precisa conter cada competência esperada. Limites continuam inclusivos, com granularidade mensal e teto por métrica; fevereiro respeita anos bissextos. Mês sem ano, data por dia, intervalo invertido/incompleto, ano sem cobertura completa e lacuna pedem esclarecimento. Não se usa a data do servidor nem se reduz um intervalo ao único extremo reconhecido.

As frases explícitas enriquecem o perfil somente na requisição Gold. O histórico do esclarecimento também é interpretado com esse calendário para preservar filtros e período. As frases relativas continuam sujeitas à proposta ADR-0018; a seleção explícita não depende de escolher uma âncora relativa.

DEC/FEC exigem o alimentador como filtro, conforme o mapeamento v2 já existente. `required_filter_dimension_ids` declara essa restrição no perfil lógico, validada contra o mapeamento físico. Construtor e validador recusam plano sem o filtro. O caso público confirma esclarecimento → alimentador conhecido → plano para o mesmo mês; remover o filtro do plano é recusado separadamente pelo validador. O limite de linhas configurado na composição é preservado mesmo após enriquecer o perfil com dimensões ou calendário.

Comprovação dirigida: 69 testes de filtros/períodos aprovados, incluindo passagem de envelope ao contrato Backend em processo separado. Essas verificações exercitam planejamento e autorização com metadados controlados. A carga/consulta quantitativa do lote real continua fora desta evidência.


### Filtros parcialmente reconhecidos, contexto e banco v2

Cinco regressões reproduziram um plano indevido quando uma pergunta misturava um valor conhecido e outro desconhecido na mesma dimensão. A interpretação agora confere cada menção explícita a classe, município, bairro, subgrupo e alimentador, em vez de aceitar a existência de qualquer valor conhecido na pergunta. Todos esses casos geram esclarecimento e nenhum plano.

O contexto Gold reinterpreta a última fala com o prefixo anterior disponível no contrato de três turnos. Assim, pergunta sem período → esclarecimento → mês explícito → correção de município preserva métrica, classe e mês. Cada reconstrução usa somente o histórico recebido e o catálogo/escopo atuais; não cria memória persistente nem recupera informação ausente.

`backend/tests/test_genai_planning_metadata.py::test_database_metadata_drives_the_composed_genai_plan` atravessa banco SQLite migrado com tabelas v2, produtor Backend real, envelope interno, núcleo composto em processo separado e validação de retorno no contrato Backend. Abril/2025 gera plano com município/bairro/classe e grafia canônica extraídos do banco; junho ausente esclarece. A fonte e o modelo falham se forem chamados durante planejamento. Essa é uma integração de software com dados inteiramente artificiais, sem HTTP coordenado nem execução quantitativa. Na imagem Backend isolada, sem o código GenAI, os dois casos entre serviços são explicitamente ignorados; no checkout completo foram executados e aprovados.


### Qualificadores e propostas de plano

Nove regressões reproduziram totais indevidos para pedidos com qualificadores não representados: receita com/sem leitura, consumo sem fatura, estornos, situação vencida, limites numéricos e ranking/ordenação. Esses pedidos agora recebem esclarecimento específico pelo perfil Gold. As colunas/fontes existentes na Gold v2 não são anunciadas como ausentes: a restrição é a capacidade deste catálogo de perguntas.

`supports_grouping` e `supports_ordering` são capacidades explícitas do perfil. Gold v2 as mantém desabilitadas; o validador recusa também um plano externo que acrescente agrupamento ou ordenação. Os defaults preservam o comportamento dos demais perfis. Pergunta, interpretação e plano recebido passam pela mesma definição de capacidades.

## Conferência dos dez critérios originais — histórico antes da prova PostgreSQL

| Critério | Evidência atual | Estado de aceite |
| --- | --- | --- |
| Sinônimos e distinção entre medidas | Perfil v2, esclarecimentos e suíte pública de planejamento | Comprovado no núcleo |
| Filtros autorizados; desconhecido não ignorado | Filtros combinados, cinco regressões conhecido+desconhecido, UC sem resolução e revogação | Comprovado no núcleo |
| Último ano/comparações pela cobertura real | Resolvedor e produtor ligados em teste com banco artificial; relativas na ADR-0018 | Parcial: revisão semântica e lote real |
| Esclarecimento preserva intenção | Métrica/período/alimentador, correção de cidade e contexto de três turnos | Comprovado no núcleo |
| Matriz positiva/negativa dos casos do case | Matriz e testes versionados sem valores reais | Comprovado |
| Ambiguidade/grafia/base zero/parcial pela interface pública | Planos/esclarecimentos exercitados; planejamento não calcula percentual | Parcial: resposta quantitativa/evidência futura |
| Composição até fonte, ordem/limite/agrupamento | Núcleo → JSON → contrato Backend e banco → produtor → núcleo; limites e recusas de ranking/ordenação | Parcial: entrega ao executor de runtime |
| Datas, competência/leitura/pagamento e fuso | Calendário explícito, bissexto/lacuna, distinções de medidas e UTC no catálogo | Parcial: validação semântica relativa e lote real |
| Correção/múltiplos locais/unidades/suporte | Regressões públicas, filtros não reconhecidos e qualificadores não representados | Comprovado no núcleo |
| Catálogo e autorização em contexto/propostas | Reautorização do histórico e rejeição de filtros removidos, grouping/order externos | Comprovado no núcleo |

A implementação lexical e de planejamento está exercitada com os componentes reais; seis critérios estão comprovados no escopo indicado e quatro têm cláusulas ainda parciais. O cartão não equivale ao aceite quantitativo IA-01/IA-02. Revisão semântica e prova de implantação não são substituídas por contagem de testes.


Vocabulário complementar conferido contra o dicionário v2: receita recebida/paga, arrecadação e faturas pagas pedem distinção de pagamento; energia injetada/compensada/entregue não é convertida em consumo medido. Os testes positivos e de esclarecimento mantêm o significado da população, sem anunciar como inexistentes colunas que apenas não integram o catálogo atual.


Verificação final consolidada desta continuação: suíte completa GenAI com 3.681 aprovados, 4 skips e 1 xfail histórico (38,73 s); suíte completa Backend com 821 aprovados e 90 skips (172,51 s). Ruff, compileall e diff-check dos arquivos alterados passaram. Os totais anteriores são registros das etapas; esta é a referência final da árvore local atual.


## Fronteira HTTP e evidência por recorte — 31/10/2026

As rotas internas `question-plans` e `question-syntheses` agora chamam o núcleo existente na composição externa Gold v2. Exigem token de serviço configurado; modo demo não habilita essas operações. O cliente Backend usa os caminhos contratuais e confere correlação e schema de resposta. A correlação da síntese é preservada no cabeçalho e no corpo.

O teste de banco já existente foi ampliado, sem criar uma matriz paralela: banco SQLite v2 migrado → produtor real → cliente Backend → aplicação GenAI `create_app` em processo separado → HTTP ASGI → núcleo. Presença/ausência de mês e filtros canônicos continuam conferidos. A síntese de ausência atravessa o mesmo cliente e aplicação sem consultar fonte/modelo. A ponte entre processos é controlada; não representa uma rede de serviços implantada.

`test_gold_planning_http.py` comprova janeiro–março para `este ano` na cobertura controlada, recusa de GD sem autorização, esclarecimento para mês ausente, zero observado na resposta e recusa de publicação divergente. A síntese aceita dimensões exatamente iguais ao filtro aprovado, incluindo município da publicação; um registro com outro município é recusado. Esse comportamento corrige a rejeição indevida que existia quando o vocabulário estático não continha os municípios reais.

Verificações dirigidas: 141 testes GenAI e 28 Backend passaram; Ruff e compileall passaram. Não foram adicionados novos casos combinatórios à matriz. O executor, a coordenação do portal e a reconciliação com lote PostgreSQL autorizado permanecem pendentes; a tabela dos dez critérios mantém as quatro cláusulas parciais até essa prova. Valor zero observado não comprova cálculo de comparação percentual com denominador zero.


### 31/10/2026 — GENAI-04: verificação dirigida da continuação local

- Branch confirmada pelo Git: `feat/ai-agent-vocabulario-periodos-gold-v2`, worktree `genai03-public-metadata/git-or-treat`, base `dc6ea3f`. Preservadas as alterações sem commit das rotas internas, cliente e guarda de evidência.
- Reutilizado o teste HTTP de zero: medida nula ou ausente retorna `recoverable_error` sem evidência numérica; zero observado continua respondido. Não foi criado outro caso de uso nem ampliada a matriz.
- Verificações nesta rodada: em `ai-agent`, `python -m pytest -q tests/test_gold_planning_http.py tests/test_gold_question_filters.py tests/test_gold_temporal.py tests/test_evidence_guard.py tests/test_core_plan_synthesis.py --tb=short`: 157 passaram. Em `backend`, `python -m pytest -q tests/test_genai_planning_metadata.py tests/test_genai_client.py --tb=short`: 28 passaram. Ruff dos arquivos de código alterados passou com a configuração de cada módulo; `python -m compileall -q app tests/test_gold_planning_http.py` passou em GenAI.
- GENAI-04 permanece em validação; IA-01/IA-02/IA-06 mantêm seus estados. Continuam abertas a homologação temporal da ADR-0018 e as provas dependentes do executor/coordenador Backend e lote PostgreSQL autorizado. Ausência de medida não comprova percentual comparativo com denominador zero. Sem commit/push nesta rodada.


## Entrega dirigida de 31/10/2026 — planejamento operacional

A pessoa usuária aprovou a ADR-0018 nesta entrega. `backend/app/services/genai_planning.py::plan_gold_question` liga o produtor ao cliente HTTP existente e admite o plano na fonte física, mantendo publicação, fingerprint, escopo atual e prazo global. `backend/scripts/plan_gold_question.py` é seu chamador operacional. O produtor agora limita o conjunto de consultas de metadados ao saldo SQL de 5 s.

Corrigida uma lacuna de integração: a união de meses de várias tabelas não prova a cobertura da fonte selecionada. A admissão consulta as competências com os filtros efetivos, na mesma publicação; mês existente apenas em outra tabela/recorte pede esclarecimento. A revogação durante o planejamento retorna recusa com o erro público obrigatório, sem entregar plano.

| Pendência anterior | Resultado observado nesta rodada | Alcance |
| --- | --- | --- |
| Aprovação temporal | Aprovação expressa da pessoa usuária registrada na ADR-0018 e índice | Decisão resolvida para esta entrega; não atribuída a outros integrantes |
| Produtor ligado em runtime | Serviço Backend e CLI chamam as rotas internas existentes; admissão por catálogo/fonte/recorte | Planejamento executável; a medida quantitativa não é executada |
| PostgreSQL e lote v2 autorizado | Prova privada passou com PostgreSQL 16, importador real, papel `venergy_gold_reader`, GenAI por TCP/HTTP local e CLI real | Plano do recorte preservado; sem registros ou valores reais publicados |
| Janela relativa no lote real | Últimos 12 meses confrontados com competências físicas por controle independente; lacuna não é encurtada | Âncora e limites inclusivos verificados |
| Calendário/fuso do lote | Cobertura de atendimento UTC confrontada com conversão dos timestamps em Python | Não confunde competência de faturamento com abertura/pagamento |
| Zero/nulo/comparação | Teste HTTP existente distingue zero de medida nula/ausente e esclarece comparação com base zero sem plano | Não afirma cálculo percentual com denominador zero |

Verificações observadas: Backend `python -m pytest -q tests/test_genai_planning_metadata.py tests/test_genai_client.py tests/test_genai_publication.py tests/test_genai_plan.py --tb=short`: **96 passaram, 19 skips** dependentes de PostgreSQL nessa execução local. Prova privada opt-in `GOLD_PLANNING_TEST_DATABASE_URL=<leitor do banco descartável *_test> python -m pytest -q tests/test_genai_planning_real.py --tb=no`: **1 passou em 6,46 s**, após carga do pacote autorizado pelo importador e provisionamento do leitor pelo script existente. GenAI `python -m pytest -q tests/test_gold_planning_http.py --tb=short`: **5 passaram** após a checagem de comparação sem suporte; a regressão dirigida de 157 casos desta continuação permanece registrada acima. Ruff por módulo, compileall e `git diff --check` passaram.

Para reproduzir a prova privada, prepare um PostgreSQL 16 descartável vazio com nome terminado em `_test`; execute as migrações, `scripts/load_gold.py` com `--schema-version gold-csv-v2` e o diretório privado aceito, e `scripts/provision_gold_reader.sql` como administrador. Execute o teste com `GOLD_PLANNING_TEST_DATABASE_URL` apontando para o leitor desse banco. O teste inicia/encerra a GenAI local sem LLM, confere reautorização e remove os arquivos privados de entrada/auditoria que cria. O pacote original permanece intacto. A prova não requer nova auditoria Silver nem publica dados.

**Limite preservado:** esta rodada resolve aprovação, runtime de planejamento e a prova PostgreSQL de períodos/valores canônicos. A execução quantitativa, incluindo percentual comparativo com denominador zero, e o coordenador Gold do endpoint do portal continuam nas fronteiras GENAI-06/07/09/10. A admissão de fonte não é apresentada como executor de medidas. Por isso, as cláusulas compostas que exigem essa fronteira final permanecem abertas; não se concluem GENAI-04 integral nem IA-01/IA-02/IA-06 por este plano.
