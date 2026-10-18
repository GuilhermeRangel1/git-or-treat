# Serviço: agente de inteligência artificial

**Escopo:** IA-01 a IA-08 do [PRD](../PRD.md). **Estado:** fluxo sintético de perguntas e contrato de insight contextual estão preparados nos endpoints `POST /api/v1/questions` e `POST /api/v1/insights`; o adaptador Gemini é opcional por ambiente. Gold, backend e frontend do portal ainda não estão integrados. **Stack do case:** Python integrado ao FastAPI e banco local Gold; framework de agente à escolha. O código configura `gemini-3.5-flash-lite` como padrão do adaptador e permite escolher outro ID, como `gemini-3.6-flash`; a escolha definitiva do provedor continua aberta pela equipe.

## Duas formas de IA obrigatórias

1. **Agente conversacional Text-to-SQL no portal:** interpreta português cotidiano, consulta Gold e devolve resposta clara, numérica e fundamentada.
2. **Insight embutido em uma tela:** interpreta o dado que o usuário vê e sugere o que investigar, mantendo vínculo explícito com filtros e período da tela.

O mesmo dicionário Gold deve reger a conversa e o insight. A interface precisa mostrar qual parte é dado observado e qual parte é interpretação gerada. Uma sugestão de investigação não deve ser apresentada como causa comprovada.

### Contrato sintético de insight de tela

`POST /api/v1/insights` recebe `screen` com métrica, unidade, intervalo (`start`, `end`, `granularity`), pelo menos um filtro, observações numéricas, referência e limitações. O validador rejeita campos ausentes, período invertido, rótulos de observação repetidos, valores não finitos e referência que não esteja marcada como demonstração nesta etapa. Campos inesperados também são rejeitados, inclusive um campo de pergunta livre; a solicitação ao modelo é uma instrução fixa do serviço, enquanto filtros e observações entram como dados não confiáveis.

A resposta separa `observation.values` (cópia do resultado enviado pelo consumidor) de `hypothesis` (texto gerado pelo modelo), e repete métrica, unidade, período, filtros, referência e limitações. Uma hipótese numérica com valor ausente do contexto é recusada. Isso é só uma checagem lexical; não prova que a interpretação é verdadeira nem que o contexto foi autorizado pelo backend. Durante a Etapa 3, a referência sintética impede apresentar o fluxo como resultado real da V-Energy.

O contrato também é resumido no [README do serviço](../../ai-agent/README.md), com payload demonstrativo. O contexto estruturado ainda não vem do portal; o endpoint não autentica nem autoriza o consumidor.

### Contratos para revisão com backend e frontend

| Endpoint | Entrada do consumidor | Campos principais da resposta |
| --- | --- | --- |
| `POST /api/v1/questions` | `contract_version` opcional (padrão `v1`; versão nula ou não suportada é rejeitada), `question` (1–1.000 caracteres) e `context` opcional com até três turnos ordenados (`role`: `user` ou `assistant`; `content`: até 1.000 caracteres). Cada chamada deve reenviar o contexto necessário. | Envelope `v1`: `status`, `answer` ou `message`, `evidence`, `limitations`, `analysis_context`, `error`, `correlation_id` e `audit_reference`. `analysis_context` é nulo até a fonte retornar período, unidade e filtros efetivamente aplicados. |
| `POST /api/v1/insights` | `screen` com `metric`, `unit`, `period`, `filters`, `observations`, `reference` e `limitations`. A referência deve ter `is_demo: true` durante o protótipo. | Envelope `v1`: `status`, `context`, `observation.values`, `hypothesis` ou `message`, `evidence`, `limitations`, `error`, `correlation_id` e `audit_reference`. Observações recebidas e hipótese gerada ficam em campos separados. |

### Envelope público v1 e erros

As respostas de negócio carregam `contract_version: "v1"`. O serviço gera um identificador hexadecimal de 32 caracteres por requisição, retorna-o em `correlation_id` e no cabeçalho `X-Correlation-ID`; ele não é aceito do cliente como prova de identidade. `audit_reference` é `null`: correlação não equivale a auditoria persistida. Uma referência em `evidence` indica a origem e inclui `is_demo`; nenhum resultado desta etapa é dado real da V-Energy.

Erros de validação de entrada usam HTTP 422 com `status: "error"`, mensagem fixa, código `invalid_request`, `retryable: false` e correlação. Falhas inesperadas usam HTTP 500 com `internal_error`, mensagem genérica e sem detalhe da exceção. Falhas de fonte/provedor durante o fluxo preservam o status de negócio `recoverable_error` e um erro público estruturado. Recusa de segurança ou de escopo preserva `status: "refused"`; esclarecimento e ausência legítima usam `needs_clarification`/`no_evidence` sem objeto de erro. `retryable` é uma indicação para o consumidor: somente indisponibilidades temporárias de fonte/modelo são marcadas como repetíveis; a API não faz retry automático.

| Categoria interna | Código/mensagem públicos | Retry |
| --- | --- | --- |
| Solicitação inválida | `invalid_request` — solicitação fora do contrato | Não |
| Tema não suportado | `out_of_scope` — tema fora do escopo | Não |
| Tentativa de escrita, injeção ou dado sensível | `security_violation` — ação/dado não permitido | Não |
| Acesso negado pela fonte | `access_denied` — escopo não autorizado | Não |
| Fonte ou provedor indisponível | `service_unavailable` — serviço temporariamente indisponível | Sim |
| Limite excedido | `limit_exceeded` — solicitação excede os limites | Não |
| Resposta inválida da fonte/modelo | `invalid_upstream_response` — resultado upstream inválido | Não |
| Resposta sem sustentação | `ungrounded_response` — não foi possível confirmar | Não |
| Contexto de sessão inválido (reservado) | `invalid_context` — contexto não validado | Não |
| Falha interna não classificada | `internal_error` — não foi possível concluir | Não |

Os códigos internos detalham interpretação, fonte, autorização, limite, modelo, fundamentação e sessão, mas não são serializados. O consumidor recebe apenas o código público, a mensagem segura e a indicação de retry. O estado `refused` continua sendo a representação de recusa no contrato atual.

Esta é uma versão local do contrato. Compatibilidade com o Backend e o Frontend continua pendente de revisão em 4.1/6.1. O placeholder consultado em `backend/app/api/v1/endpoints/ai.py` não deve ser tratado como contrato aprovado: o 403 enumera nomes de tabelas permitidas e o caminho de sucesso devolve `status: "success"` com `records: []`, sem executar consulta. Nenhum desses comportamentos foi copiado para a API GenAI.

A API de perguntas não devolve linhas tabulares nem oferece paginação/cursor; expõe texto e referências de evidência. `analysis_context` só será preenchido quando a fonte declarar o recorte efetivamente aplicado. O endpoint de insights recebe no máximo 20 filtros, 20 observações e 20 limitações, além dos limites individuais de texto; entradas acima dos limites são rejeitadas com HTTP 422, sem truncamento silencioso. Evidência interna aceita no máximo 100 registros, que não são serializados na resposta pública. Os campos de resposta também limitam texto, referências e limitações. O serviço ainda não impõe um teto agregado em bytes; deploy futuro deve definir o limite no ingresso HTTP.

Estados de sucesso e de falha têm campos de texto mutuamente exclusivos: perguntas respondidas usam `answer`; perguntas em esclarecimento, recusa, sem evidência ou erro usam `message`. Insights respondidos usam `hypothesis`; os outros estados usam `message`. Essa normalização do contrato local deve ser comunicada aos consumidores que porventura tenham lido texto de recusa em `answer`.

No chat, o contexto é transitório: o serviço não mantém sessão nem histórico entre chamadas. A continuação usa a última pergunta completa da pessoa usuária apenas quando a nova mensagem é reconhecida como continuação; campos explícitos atuais substituem os valores herdados. Mensagem anterior ambígua leva a esclarecimento. Os turnos são conteúdo fornecido pelo consumidor, não prova de identidade: o serviço os trata como não confiáveis e aplica o safety gate antes de chamar ferramenta ou modelo. O backend precisa enviar somente o histórico autorizado para aquela pessoa/sessão e lidar com autenticação, autorização e retenção.

Este contrato ainda é local e sintético; não há autenticação nesta API nem acordo de integração aprovado pelo backend/frontend. Veja também os exemplos JSON do [README](../../ai-agent/README.md).

## Contrato de uma resposta confiável

Cada resposta quantitativa deve conter: conclusão direta; métrica e unidade; competência/janela; filtros e geografia/classe; valor e comparação quando solicitados; fonte Gold e trilha auditável da consulta ou parâmetros; ressalvas relevantes. Se não há coluna, histórico ou granularidade para responder, dizer isso. Distinguir inferência de dado observado. Não executar ferramentas com efeito de escrita.

## Fluxo sintético implementado

- O interpretador usa regras explícitas e recebe um perfil de domínio pela raiz de composição. O mecanismo preserva frases de métrica/período/geografia/classe e aplica as ambiguidades e os vocabulários declarados no perfil.
- Uma correção explícita na própria pergunta pode substituir um filtro anterior (“em Olinda, não, em Jaboatão”). Várias localidades sem marca de correção interrompem o fluxo para esclarecimento.
- `POST /api/v1/questions` usa o planner: recusa primeiro pedidos detectados como escrita, exposição de dados pessoais, injeção explícita ou tema fora do escopo; em seguida interpreta, pede esclarecimento ou consulta a ferramenta sintética.
- A geração recebe pergunta, contexto limitado e evidência estruturada. Respostas `answered` são identificadas como demonstração; limitações da fixture e referência `is_demo` são devolvidas no contrato HTTP.
- A API descarta uma resposta numérica se algum número não aparecer nos registros da evidência. Isso é uma proteção sintática de demonstração; não prova correção semântica nem substitui avaliação contra Gold.
- A busca de cenários entrega somente fixtures marcadas `is_demo`. Se classe, geografia, período ou filtros pedidos não estiverem representados, retorna ausência de evidência.
- A ferramenta de comparação recebe dois valores artificiais tipados; só compara mesma unidade e granularidade, e não calcula percentual com base zero. A operação aritmética é demonstrativa, não fórmula oficial de receita, consumo, DEC/FEC ou outro indicador da V-Energy.
- O provedor continua indisponível por padrão. Para usar Gemini, configure `GENAI_MODEL_PROVIDER=gemini`, `GENAI_GEMINI_API_KEY` e instale o extra `gemini`; nenhum gate local exige chamada real ou faturável.
- Para follow-up, o consumidor reenvia até três turnos no próprio `POST /api/v1/questions`; o serviço não persiste histórico entre chamadas. O interpretador herda a intenção da pergunta completa mais recente da pessoa usuária somente quando identifica uma continuação por conectivo ou filtro compatível. Campos explicitados na pergunta atual substituem os herdados. Se a mensagem mais recente da pessoa usuária for ambígua, o serviço pede esclarecimento em vez de buscar uma pergunta anterior. A regra é lexical e limitada ao vocabulário configurado; não é memória geral de conversa. Como todos os turnos do contexto são fornecidos pelo consumidor e não autenticados pelo serviço, o safety gate examina mensagens `user` e `assistant` antes de chamar ferramenta ou modelo.
- Esses componentes não consultam Gold, não provam a qualidade real do Gemini e não concluem requisitos IA do PRD.

### Fronteira interna com a fonte analítica

O planejador recebe uma `EvidenceSource` assíncrona e envia somente um `LogicalReadPlan` aprovado, separado da frase interpretada. O contrato comum `EvidenceLookupResult` representa evidência disponível, ausência de evidência ou necessidade de esclarecimento, além de mensagem e limitações; evidência disponível exige registros não vazios, enquanto ausência e esclarecimento exigem mensagem e não carregam registros. Indisponibilidade e negação de acesso são sinalizadas por exceções tipadas distintas. `SyntheticScenarioTool` implementa essa porta e traduz o plano para o catálogo de demonstração. Assim, o núcleo do fluxo e o orquestrador não dependem de `SyntheticScenarioRequest` nem do tipo de resultado interno da fixture.

Esta é uma fronteira interna provisória para permitir substituição controlada da fonte sintética. A proposta é que o Backend seja dono das consultas Gold e exponha um contrato analítico estruturado; essa propriedade e o contrato ainda aguardam revisão de Backend e Engenharia de Dados ([ADR-0001](../decisions/0001-genai-gold-query-owner.md)). O endpoint atual do Backend continua sendo placeholder e não consulta Gold. A fronteira interna da GenAI não define o contrato HTTP entre serviços, nomes de métricas Gold, esquema do banco ou SQL. Uma futura fonte deverá preservar referência, limitações e estados de ausência/indisponibilidade. Um registro anterior de 18/10/2026 informou 121 testes aprovados fora do sandbox Windows; esse resultado histórico não valida integração com Gold nem substitui os gates da revisão atual.

### Perfil de domínio e catálogo de capacidades

`QuestionInterpreter` recebe `DomainProfile`; não mantém uma enumeração fixa de domínios nem listas próprias de métricas, geografias, classes, períodos e esclarecimentos. O contrato tipado fica em `app/schemas/domain_profile.py`, e a configuração demonstrativa do Grid 360 fica em `app/profiles/grid360_demo.py`. `create_app(domain_profile=...)` é a fronteira de injeção; a aplicação local usa o perfil demonstrativo como padrão.

O perfil v1 declara IDs lógicos, aliases, unidades e granularidades demonstrativas, dimensões compatíveis, tipos e operadores de filtro, sensibilidade, frases de período, exemplos e ambiguidades. A validação rejeita versão ou operação não suportada, IDs duplicados, alias ambíguo e referências inexistentes; quando uma pergunta reconhece mais de uma métrica do mesmo domínio, o interpretador pede esclarecimento. Os valores atuais são demonstração, não catálogo Gold, política de autorização nem plano executável. `AnalysisIntent.domain` agora é um identificador lógico validado; `metric_id` e `dimension_ids` são preenchidos pelo perfil quando a frase é reconhecida. O texto original da pessoa continua preservado nos campos de frase.

### Contexto interno e política de acesso da demonstração

`AccessContext` carrega identificador opaco do chamador, perfil, fonte, correlação e permissões de leitura para métricas e dimensões. Ele é produzido na borda pelo serviço, separado de `QuestionRequest`, histórico e contexto de tela. O cliente não pode enviá-lo no JSON para obter acesso. A dependência FastAPI `resolve_access_context` cria somente um principal fictício em `GENAI_ENVIRONMENT=local`; nos demais ambientes retorna ausência de identidade, e perguntas e insights são recusados antes de qualquer consulta ou chamada ao modelo. A autenticação real e a derivação do escopo a partir de identidade verificada dependem da integração com o Backend. A composição segue o mecanismo de [dependências do FastAPI](https://fastapi.tiangolo.com/tutorial/dependencies/) (FastAPI 0.136.3 no ambiente de verificação).

`ReadAccessPolicy` usa o perfil injetado e o ID lógico da fonte para negar por padrão leituras fora do escopo. Após a interpretação e antes de `EvidenceSource.retrieve`, ela valida o contexto, a fonte, a operação `read`, a métrica, o domínio, as dimensões e a sensibilidade pessoal. A política é independente de nomes físicos de tabela e não recebe autorização da pergunta, do histórico ou da saída do modelo. O filtro lexical anterior à interpretação recusa pedidos explícitos de escrita e dados pessoais, mas a verificação na fronteira da fonte é a proteção para pedidos que escapem ao filtro textual. Limites públicos de pergunta e histórico são validados antes dos adaptadores.

Este recorte protege a leitura demonstrativa e não constitui autenticação do portal, autorização do banco, validador de SQL ou permissão Gold. O endpoint de insight local ainda recebe observações sintéticas do cliente; elas não são evidência verificada contra o Backend. O tratamento de conteúdo malicioso em metadados/evidências e a fundamentação da saída continuam no recorte de proteção da evidência e resposta. Em ambiente real, a implantação deve permanecer fechada até a borda receber identidade verificada e a fonte concreta impor suas próprias permissões.

### Plano lógico de leitura

`ReadPlanBuilder` transforma a intenção do interpretador em `LogicalReadPlan`: operação `read`, IDs lógicos de perfil, fonte, domínio, métrica e dimensões, unidade, janela, filtros com operador e valores tipados, ordenação opcional, limite de linhas e versão do catálogo. Frases como “Olinda” são resolvidas para o valor canônico do catálogo; a frase original não é enviada como filtro livre. A janela do protótipo pode continuar como uma frase aprovada pelo catálogo, sem inventar datas. Um período comparativo que não esteja representado ou um filtro lexical como “queda acima de 30%” gera esclarecimento antes da fonte; o plano não descarta o recorte para obter outro resultado.

`ReadPlanValidator` revalida inclusive planos construídos sem validação e propostas externas ao interpretador, verifica catálogo, operação, IDs, unidade, granularidade quando definida, tipos, operadores, valores, ordenação, janela e limites. `ReadAccessPolicy` confere o escopo autorizado do plano. O planner passa à porta de evidência o mesmo objeto imutável que foi aprovado, e `execute_plan` é a fronteira para uma eventual proposta de plano por LLM. Planos de escrita, de outra fonte ou fora do escopo não chegam à porta. Dois perfis sintéticos exercitam o mesmo mecanismo. O contrato usa Pydantic 2.13.4 no ambiente verificado, seguindo a [documentação de modelos e validação](https://docs.pydantic.dev/latest/concepts/models/).

Um plano aprovado **não autoriza SQL textual arbitrário**. Se a equipe escolher geração de SQL, o parser/validador de AST e dialeto ficará no caminho concreto de execução definido após 5.0; a credencial e as permissões somente leitura do banco terão de ser verificadas na integração. A frase de período ainda precisa ser resolvida para janela e grão reais antes de uma consulta Gold. Nenhum nome de tabela, coluna ou fórmula oficial foi colocado no validador lógico.

### Dependências atuais e direção desejada

A evolução planejada inclui um núcleo reutilizável executável: o perfil injetável, a política sintética e a validação do plano lógico já têm uma primeira versão; autenticação verificada, proteção de evidência/saída, limites de execução e eventos seguros ainda precisam ser implementados. A extração de tipos e a porta de fonte existentes são preparação. A validação lógica foi exercitada com Grid 360 sintético e um segundo perfil artificial fora do domínio elétrico; a prova integrada de reuso com dois adaptadores ainda está pendente.

Os mecanismos podem ser implementados e testados sem Gold usando catálogos, identidades e fontes de teste. A porta de evidências é assíncrona. Testes com fontes falsas verificam concorrência e propagação de cancelamento; uma implementação concreta ainda precisa evitar trabalho bloqueante no event loop. Adaptadores para clientes síncronos precisam delegar o trabalho bloqueante a um executor e definir como timeout e cancelamento chegam ao cliente. Autenticação efetiva, catálogo oficial, execução/validação SQL, permissões do banco e reconciliação continuam na integração específica da plataforma. O núcleo valida operações e planos lógicos; a segurança da consulta concreta também precisa ser imposta pelo componente que a executa. Esta direção preserva a proposta ainda aberta da ADR-0001.

O fluxo de perguntas segue esta direção: `app/api/routes.py` valida/encaminha os schemas HTTP para o orquestrador já montado; `app/agent/orchestrator.py` aplica segurança, chama `QuestionAnalysisPlanner` e usa a porta de geração `ModelAdapter`; o planner interpreta a pergunta, monta e valida o plano lógico, autoriza o escopo e só então chama `EvidenceSource`; o adaptador sintético traduz o plano para os cenários de demonstração. O fluxo de insights também entra por `routes.py`, recebe o `ScreenInsightOrchestrator` e usa `ModelAdapter`.

| Parte | Dependências observadas | Regra para a integração futura |
| --- | --- | --- |
| `app/api/` | Rotas FastAPI e schemas públicos; obtém os orquestradores de `app.state`. | A borda HTTP conhece os casos de uso e contratos públicos, sem importar adaptador Gold ou SDK de modelo. |
| `app/agent/` | Planner, interpretador, schemas de interpretação, perfil/catálogo, porta de evidência e protocolo do modelo. | Núcleo coordena contratos e regras; vocabulário vem do perfil; não importa fixture, driver SQL/ORM nem SDK de provedor. |
| `app/tools/synthetic_analytics.py` e `app/scenarios.py` | `SyntheticScenarioTool` implementa a porta `EvidenceSource` e usa o catálogo de demonstração. | O adaptador de saída importa o contrato que implementa; o núcleo chama o contrato sem importar essa implementação. |
| `app/providers/` | `ModelAdapter` é o protocolo; Gemini e outros adaptadores implementam-no. A fábrica os constrói. | O adaptador implementa o protocolo e encapsula o SDK. O núcleo importa o protocolo, nunca o adaptador concreto ou seu SDK. |
| `app/main.py` | Composição concreta de FastAPI, configuração, perfil demonstrativo, adaptadores do modelo, fixture e orquestradores. | É a raiz de composição: recebe ou seleciona o perfil e injeta as implementações nos consumidores das portas. A fixture e o perfil atuais permanecem explicitamente demonstrativos. |

Na resposta pública de perguntas, `answered` exige texto em `answer`; esclarecimento, recusa, ausência de evidência e falha exigem texto em `message`. Os campos são mutuamente exclusivos. Em insight, `answered` exige `hypothesis`; os outros estados exigem `message`. Hipótese e mensagem de insight exigem texto não vazio e têm limite de 4.000 caracteres. Adaptadores de modelo são validados novamente na fronteira do orquestrador mesmo quando a anotação declara `GeneratedAnswer`; um retorno inválido vira `recoverable_error` genérico.

`AnalysisIntent` vive em `app/schemas/analysis.py`, separado dos modelos de fixture; `app/schemas/scenarios.py` mantém `SyntheticScenario`. O contrato usa um ID lógico de domínio, sem enumeração fixa. Os nomes, métricas e frases específicos do Grid 360 ficam no perfil demonstrativo de `app/profiles/grid360_demo.py`.

Os contratos de intenção, solicitação (`QuestionRequest`) e evidência têm versão interna `v1`; no endpoint, a versão do request pode ser omitida para compatibilidade e assume `v1`, mas `null` e versões não suportadas são rejeitadas. Os modelos `EvidenceResult`, `EvidenceLookupResult` e seus estados vivem em `app/schemas/evidence.py`; a porta `EvidenceSource` e as exceções de indisponibilidade/acesso negado vivem em `app/ports/evidence.py`. O pacote `app/tools/` contém implementações, não os contratos compartilhados. `AnalysisIntent` preserva as frases e recebe IDs lógicos de métrica/dimensões do perfil selecionado, sem fixar nomes físicos. Ausência de filtro é representada por campo omitido; `null` explícito é inválido; filtro desconhecido deve pedir esclarecimento; consulta válida sem linhas é `no_evidence`; indisponibilidade e acesso negado são falhas tipadas distintas. O perfil Grid 360 v1 é demonstrativo, não catálogo Gold. A inspeção dos imports em 18/10/2026 não encontrou driver de banco, ORM ou conexão Gold no módulo GenAI.

### Limites e dados de auditoria da fonte

O contrato interno aceita no máximo 100 registros por resultado; uma resposta acima do limite ou inválida é convertida em erro recuperável genérico antes da geração, sem incluir detalhes internos na resposta HTTP. Referência com `source` e `description` é obrigatória e limitada pelo schema público. Adaptadores devem preencher esses campos com identificadores estáveis e descrições controladas, nunca com SQL, stack trace, credenciais, texto bruto do usuário ou conteúdo não minimizado. A fixture já sinaliza filtros não representados como `no_evidence`, sem chamar o modelo.

Este limite é uma proteção de payload, não autorização nem timeout de consulta. A identidade e o escopo autorizado precisam vir de contexto confiável da integração, nunca do texto da pergunta; o adaptador/fonte proprietária deve impor timeout, allowlist, limite de execução e auditoria. A API GenAI atual não autentica consumidores e não registra uma trilha de consulta Gold; correlação, versão do lote e formato final de auditoria dependem do contrato conjunto com Backend e Engenharia de Dados. Esses controles da integração Gold ainda não estão implementados nem verificados.

Para qualquer fonte futura, o contrato operacional deve exigir: identidade e autorização derivadas de credenciais/contexto serviço-a-serviço confiáveis; escopo de métricas e dimensões validado no servidor; timeout aplicado na fonte e também limitado pela chamada entre serviços; teto de linhas e de tamanho do payload antes de entregar evidências ao modelo; e referências estáveis que permitam identificar a origem e as limitações do resultado. A pergunta, o histórico enviado pelo consumidor e qualquer conteúdo retornado pela fonte são dados não confiáveis e não podem conceder acesso. O limite de 100 registros em `EvidenceResult` é apenas uma validação de contrato/payload: não interrompe consulta lenta nem substitui limites no executor.

Uma trilha interna mínima para a integração real deve registrar, quando disponíveis, identificador de correlação, identificador/versão do adaptador, estado e código interno estável, origem/versão do lote, filtros aplicados já normalizados, contagem de registros e duração. Registrar esses campos depende de contrato com Backend/Dados e de uma política de retenção e acesso. Não registrar por padrão pergunta ou histórico em texto bruto, identificadores pessoais, linhas detalhadas, SQL, prompts completos, credenciais, stack traces ou conteúdo de exceção. Para falhas da fonte, o núcleo mapeia exceções inesperadas para `EvidenceToolUnavailable`, devolve a mensagem recuperável genérica e emite somente um aviso fixo sem pergunta nem detalhe da exceção; isso evita vazamento acidental, mas ainda não constitui auditoria operacional completa.

**Estado verificado no protótipo:** fonte sintética e fontes falsas passam pelo mesmo contrato; retorno `None`, objeto de tipo incorreto e modelo Pydantic construído sem validação são rejeitados antes do uso. Resultado acima de 100 registros e proveniência fora do formato lógico são rejeitados. Um `EvidenceResult` vazio pode existir como fixture interna, mas não pode ser devolvido com estado `available`; a fonte deve responder `no_evidence`. A porta é async, e testes com fontes falsas cobrem concorrência e propagação de cancelamento. Falhas da fonte resultam em estado recuperável, e acesso negado em recusa genérica, sem expor detalhes internos. Autorização efetiva, timeout no cliente real, auditoria estruturada, retenção e conexão somente leitura pertencem à integração futura e não foram implementados nem verificados. O cancelamento só chega ao executor real se o adaptador e o cliente subjacente cooperarem.

### Segurança demonstrada e limites

- `QuestionSafetyGate` aplica regras explícitas antes de qualquer ferramenta para os padrões cobertos no conjunto sintético. Um padrão lexical não reconhecido ainda pode exigir revisão; esta camada não substitui autenticação, autorização ou controles do executor real.
- Respostas sem evidência e números ausentes na evidência não são aceitos como respostas quantitativas. A checagem atual compara tokens numéricos, não verifica se cada frase representa corretamente a métrica ou a fórmula.
- O conjunto versionado está em `ai-agent/tests/fixtures/genai_regression.json`; execute `python -m tests.test_genai_regression --output reports/synthetic-regression-report.json` dentro de `ai-agent/` para gerar o relatório. Ele usa um adaptador de linguagem fixo, sem rede, inclui os endpoints de perguntas e insights e identifica versão, escopo e limitações. O relatório não contém horário variável para que duas execuções com o mesmo código e fixtures produzam o mesmo conteúdo.
- Para uma verificação completa, execute dentro de `ai-agent/`: `python -m pytest -q`, `python -m compileall -q app tests` e `python -m ruff check .`; execute `git diff --check` na raiz.

## Fluxo controlado para a futura integração Gold

1. Identificar intenção, entidades, período, filtros e ambiguidades. Reconhecer sinônimos do setor.
2. Validar se há informação no dicionário e permissão para consultar a métrica.
3. Produzir consulta limitada a tabelas/colunas de leitura, com limite de linhas, timeout e validação independente da saída do modelo.
4. Executar com usuário de banco somente leitura e capturar consulta/parâmetros, versão dos dados e resultado agregado.
5. Formular resposta a partir do resultado obtido, com checagem de números e política de “não sei”.
6. No insight de tela, receber contexto estruturado da tela; não confiar apenas em texto livre que possa contradizer os filtros reais.

## Política de respostas e auditoria

| Situação | Resposta esperada |
| --- | --- |
| Pergunta com métrica, período e recorte definidos | Consultar fonte permitida, conferir cálculo e responder com valor, unidade, filtros, período e origem. |
| Termo cotidiano com mapeamento seguro | Explicitar a interpretação, por exemplo “conta de luz” como fatura, antes do número quando houver mais de uma leitura plausível. |
| Ambiguidade que muda o número | Perguntar qual definição/janela usar; não escolher silenciosamente entre faturado e pago ou entre competência e pagamento. |
| Coluna, período ou grão insuficiente | Dizer exatamente qual dado falta e qual parte, se alguma, pode ser respondida com segurança. |
| Pedido de escrever/apagar dados ou acessar fora do escopo | Recusar a ação e manter consulta somente leitura; não transformar o pedido em SQL executável. |
| Consulta válida com zero linhas ou denominador zero | Informar ausência de base, sem fabricar zero ou percentual. |

Para a integração real, registrar internamente identificador de correlação, interpretação normalizada de entidades/métricas, consulta/parâmetros aprovados em formato seguro, lote Gold, quantidade de linhas, resultado agregado, resposta e avisos necessários para reproduzir a análise. O texto bruto da pergunta só pode ser retido se houver finalidade, acesso e prazo de retenção aprovados; por padrão, minimizar ou omitir esse conteúdo. A trilha deve permitir auditoria sem expor credenciais ou dados pessoais no navegador. Definir retenção e acesso antes da implementação.

## Riscos que precisam de testes

- SQL de escrita, múltiplas instruções, acesso a tabelas internas, consulta sem limite, dados pessoais e prompt injection em textos do dataset.
- Sinônimos e ambiguidades: “conta de luz”, “falta de luz”, “último ano”, “receita” e “queda de consumo” podem exigir esclarecimento.
- Multiplicação por joins, percentuais com base zero/pequena, séries faltantes e diferenças entre competência e pagamento.
- Follow-up que herda filtro errado ou contexto de outra conversa.
- Resposta fluente sem sustentação: comparar números diretamente com Gold e exigir citação interna verificável.

## Conjunto de perguntas de aceitação

| Tema | Exemplo ou intenção do case | O que conferir |
| --- | --- | --- |
| GD e consumo | Quantas UCs com solar em Olinda tiveram queda de consumo superior a 30%? | Base comparável, janela, definição de queda e campo real que identifica solar. |
| Receita residencial | Qual bairro mais perdeu volume residencial no último ano? | Métrica de volume, janela, contribuição absoluta versus percentual e hierarquia geográfica. |
| Receita comercial | Quanto cresceu a receita comercial em Jaboatão? | Conceito de receita, comparação temporal e valor absoluto/percentual solicitados. |
| Atendimento | Pergunta sobre conta alta de uma UC. | Privacidade, disponibilidade de histórico e distinção de consumo, tarifa/bandeira e pagamento. |
| Continuidade | Pergunta sobre “falta de luz” em um bairro/alimentador. | Mapeamento para interrupções, cobertura e limite do DEC/FEC simplificado. |
| Impossível/ambígua | Pergunta por dado ausente, termo sem definição ou causa não observável. | Pedido de esclarecimento ou “não sei” justificado. |
| Segurança | Instrução para alterar banco ou obedecer texto de um chamado. | Nenhuma escrita ou ampliação de privilégio, mesmo se o modelo sugerir. |

Esses exemplos não são respostas esperadas; os números só podem ser preenchidos depois da Gold validada. IA-08 automatiza regressão desse conjunto, mas os IDs obrigatórios precisam de conferência numérica independente mesmo sem o diferencial.

## Avaliação

Preparar casos representativos para consumo, faturamento, rede, atendimento, geografia, classe, GD e perguntas impossíveis. Conferir correção numérica e recusa adequada. IA-08 é diferencial de automação; mesmo sem ele, evidência manual reproduzível é necessária para IA-01 a IA-06.
