# Serviço: agente de inteligência artificial

**Escopo:** IA-01 a IA-08 do [PRD](../PRD.md). **Estado:** fluxo sintético de perguntas e contrato de insight contextual estão preparados nos endpoints `POST /api/v1/questions` e `POST /api/v1/insights`; o adaptador Gemini é opcional por ambiente. Gold, backend e frontend do portal ainda não estão integrados. **Stack do case:** Python integrado ao FastAPI e banco local Gold; framework de agente à escolha. O código configura `gemini-3.5-flash-lite` como padrão do adaptador e permite escolher outro ID, como `gemini-3.6-flash`; a escolha definitiva do provedor continua aberta pela equipe.

## Duas formas de IA obrigatórias

1. **Agente conversacional Text-to-SQL no portal:** interpreta português cotidiano, consulta Gold e devolve resposta clara, numérica e fundamentada.
2. **Insight embutido em uma tela:** interpreta o dado que o usuário vê e sugere o que investigar, mantendo vínculo explícito com filtros e período da tela.

O mesmo dicionário Gold deve reger a conversa e o insight. A interface precisa mostrar qual parte é dado observado e qual parte é interpretação gerada. Uma sugestão de investigação não deve ser apresentada como causa comprovada.

### Contrato sintético de insight de tela

`POST /api/v1/insights` recebe `screen` com métrica, unidade, intervalo (`start`, `end`, `granularity`), pelo menos um filtro, observações numéricas, referência e limitações. O validador rejeita campos ausentes, período invertido, rótulos de observação repetidos, valores não finitos e referência que não esteja marcada como demonstração nesta etapa. Campos inesperados também são rejeitados, inclusive um campo de pergunta livre; a solicitação ao modelo é uma instrução fixa do serviço, enquanto filtros e observações entram como dados não confiáveis.

A resposta separa `observation.values` (valores enviados pelo consumidor) de `hypothesis`. O modelo seleciona IDs de observações, e o serviço compõe a hipótese pública apenas com valores selecionados, sem publicar a frase livre do modelo. Seleção ausente ou desconhecida gera recusa controlada. O protótipo local rejeita padrões evidentes de texto sensível ou instrucional; isso não valida a origem dos dados. Sem identidade verificada no modo real, o fluxo recusa antes do modelo e omite os filtros e observações do cliente na resposta. Nenhum contexto de tela é prova de Gold nesta etapa.

O contrato também é resumido no [README do serviço](../../ai-agent/README.md), com payload demonstrativo. O contexto estruturado ainda não vem do portal; o endpoint não autentica nem autoriza o consumidor.

### Contratos para revisão com backend e frontend

| Endpoint | Entrada do consumidor | Campos principais da resposta |
| --- | --- | --- |
| `POST /api/v1/questions` | `contract_version` opcional (padrão `v1`; versão nula ou não suportada é rejeitada), `question` (1–1.000 caracteres) e `context` opcional com até três turnos ordenados (`role`: `user` ou `assistant`; `content`: até 1.000 caracteres). Cada chamada deve reenviar o contexto necessário. | Envelope `v1`: `status`, `answer` ou `message`, `evidence`, `limitations`, `analysis_context`, `error`, `correlation_id` e `audit_reference`. Resposta sintética fundamentada inclui o recorte lógico em `analysis_context`. |
| `POST /api/v1/insights` | `screen` com `metric`, `unit`, `period`, `filters`, `observations`, `reference` e `limitations`. A referência deve ter `is_demo: true` durante o protótipo. | Envelope `v1`: `status`, `context`, `observation.values`, `hypothesis` ou `message`, `evidence`, `limitations`, `error`, `correlation_id` e `audit_reference`. Observações recebidas e hipótese gerada ficam em campos separados. |

### Envelope público v1 e erros

As respostas de negócio carregam `contract_version: "v1"`. O serviço gera um identificador hexadecimal de 32 caracteres por requisição, retorna-o em `correlation_id` e no cabeçalho `X-Correlation-ID`; ele não é aceito do cliente como prova de identidade. `audit_reference` é `null`: correlação não equivale a auditoria persistida. Uma referência em `evidence` indica a origem e inclui `is_demo`; nenhum resultado desta etapa é dado real da V-Energy.

Erros de validação de entrada usam HTTP 422 com `status: "error"`, mensagem fixa, código `invalid_request`, `retryable: false` e correlação. Falhas inesperadas usam HTTP 500 com `internal_error`, mensagem genérica e sem detalhe da exceção. Falhas de fonte/provedor durante o fluxo preservam o status de negócio `recoverable_error` e um erro público estruturado. Recusa de segurança ou de escopo preserva `status: "refused"`; esclarecimento e ausência legítima usam `needs_clarification`/`no_evidence` sem objeto de erro. `retryable` é uma indicação para o consumidor: somente indisponibilidades temporárias de fonte/modelo são marcadas como repetíveis. A cadeia de modelos pode avançar ao próximo adaptador apenas nessas falhas, dentro do orçamento; a API não repete a solicitação automaticamente.

| Categoria interna | Código/mensagem públicos | Retry |
| --- | --- | --- |
| Solicitação inválida | `invalid_request` — solicitação fora do contrato | Não |
| Tema não suportado | `out_of_scope` — tema fora do escopo | Não |
| Tentativa de escrita, injeção ou dado sensível | `security_violation` — ação/dado não permitido | Não |
| Acesso negado pela fonte | `access_denied` — escopo não autorizado | Não |
| Fonte ou provedor indisponível | `service_unavailable` — serviço temporariamente indisponível | Sim |
| Provedor rejeitou a chamada definitivamente | `service_unavailable` — provedor não aceitou a solicitação | Não |
| Limite excedido | `limit_exceeded` — solicitação excede os limites | Não |
| Resposta inválida da fonte/modelo | `invalid_upstream_response` — resultado upstream inválido | Não |
| Resposta sem sustentação | `ungrounded_response` — não foi possível confirmar | Não |
| Contexto de sessão inválido (reservado) | `invalid_context` — contexto não validado | Não |
| Falha interna não classificada | `internal_error` — não foi possível concluir | Não |

Os códigos internos detalham interpretação, fonte, autorização, limite, modelo, fundamentação e sessão, mas não são serializados. O consumidor recebe apenas o código público, a mensagem segura e a indicação de retry. O estado `refused` continua sendo a representação de recusa no contrato atual.

Esta é uma versão local do contrato. Compatibilidade com o Backend e o Frontend continua pendente de revisão em 4.1/6.1. O placeholder consultado em `backend/app/api/v1/endpoints/ai.py` não deve ser tratado como contrato aprovado: o 403 enumera nomes de tabelas permitidas e o caminho de sucesso devolve `status: "success"` com `records: []`, sem executar consulta. Nenhum desses comportamentos foi copiado para a API GenAI.

A API de perguntas não devolve linhas tabulares nem oferece paginação/cursor; expõe texto e referências de evidência. `analysis_context` é preenchido apenas após a fonte declarar recorte compatível com o plano aprovado; a janela demonstrativa ainda pode ser uma frase de catálogo, sem datas Gold. O endpoint de insights recebe no máximo 20 filtros, 20 observações e 20 limitações, além dos limites individuais de texto; entradas acima dos limites são rejeitadas com HTTP 422. Evidência interna usa por padrão 100 registros e 16 KiB serializados antes da minimização, com limites configuráveis, sem expor linhas na resposta pública. O ingresso HTTP ainda não tem um teto agregado em bytes.

Estados de sucesso e de falha têm campos de texto mutuamente exclusivos: perguntas respondidas usam `answer`; perguntas em esclarecimento, recusa, sem evidência ou erro usam `message`. Insights respondidos usam `hypothesis`; os outros estados usam `message`. Essa normalização do contrato local deve ser comunicada aos consumidores que porventura tenham lido texto de recusa em `answer`.

No chat, o contexto é transitório: o serviço não mantém sessão nem histórico entre chamadas. A continuação usa a última pergunta completa da pessoa usuária apenas quando a nova mensagem é reconhecida como continuação; campos explícitos atuais substituem os valores herdados. Mensagem anterior ambígua leva a esclarecimento. Os turnos são conteúdo fornecido pelo consumidor, não prova de identidade: o serviço os trata como não confiáveis e aplica o safety gate antes de chamar ferramenta ou modelo. O backend precisa enviar somente o histórico autorizado para aquela pessoa/sessão e lidar com autenticação, autorização e retenção.

Este contrato ainda é local e sintético; não há autenticação nesta API nem acordo de integração aprovado pelo backend/frontend. Veja também os exemplos JSON do [README](../../ai-agent/README.md).

## Contrato de uma resposta confiável

Cada resposta quantitativa deve conter: conclusão direta; métrica e unidade; competência/janela; filtros e geografia/classe; valor e comparação quando solicitados; fonte Gold e trilha auditável da consulta ou parâmetros; ressalvas relevantes. Se não há coluna, histórico ou granularidade para responder, dizer isso. Distinguir inferência de dado observado. Não executar ferramentas com efeito de escrita.

## Fluxo sintético implementado

- O interpretador usa regras explícitas e recebe um perfil de domínio pela raiz de composição. O mecanismo preserva frases de métrica/período/geografia/classe e aplica as ambiguidades e os vocabulários declarados no perfil.
- Uma correção explícita na própria pergunta pode substituir um filtro anterior (“em Olinda, não, em Jaboatão”). Várias localidades sem marca de correção interrompem o fluxo para esclarecimento.
- `POST /api/v1/questions` usa o planner: recusa primeiro pedidos detectados como escrita, exposição de dados pessoais, injeção explícita ou tema fora do escopo; em seguida interpreta, pede esclarecimento ou consulta a ferramenta sintética.
- A geração recebe pergunta, contexto limitado e observações estruturadas já minimizadas. Respostas `answered` são identificadas como demonstração; limitações aprovadas no catálogo e referência `is_demo` sobrevivem ao contrato HTTP.
- O modelo seleciona até dez IDs de observação. O serviço valida a seleção e compõe os valores, unidade, métrica e período a partir da evidência e do plano; o texto livre do modelo não é publicado como resposta quantitativa. Não há cálculo nem arredondamento implícito: só se exibem os valores fornecidos pela fonte. Comparações não representadas são esclarecidas ou recusadas; a ferramenta aritmética sintética trata base zero e unidades/grãos incompatíveis, sem fórmula Gold.
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

Este recorte protege a leitura demonstrativa e não constitui autenticação do portal, autorização do banco, validador de SQL ou permissão Gold. O endpoint de insight local ainda recebe observações sintéticas do cliente; elas não são evidência verificada contra o Backend. Textos livres da fonte são removidos antes do modelo, e a saída quantitativa é formada pelo serviço a partir de observações selecionadas. Em ambiente real, a implantação deve permanecer fechada até a borda receber identidade verificada e a fonte concreta impor suas próprias permissões.

### Plano lógico de leitura

`ReadPlanBuilder` transforma a intenção do interpretador em `LogicalReadPlan`: operação `read`, IDs lógicos de perfil, fonte, domínio, métrica e dimensões, unidade, janela, filtros com operador e valores tipados, ordenação opcional, limite de linhas e versão do catálogo. Frases como “Olinda” são resolvidas para o valor canônico do catálogo; a frase original não é enviada como filtro livre. A janela do protótipo pode continuar como uma frase aprovada pelo catálogo, sem inventar datas. Um período comparativo que não esteja representado ou um filtro lexical como “queda acima de 30%” gera esclarecimento antes da fonte; o plano não descarta o recorte para obter outro resultado.

`ReadPlanValidator` revalida inclusive planos construídos sem validação e propostas externas ao interpretador, verifica catálogo, operação, IDs, unidade, granularidade quando definida, tipos, operadores, valores, ordenação, janela e limites. `ReadAccessPolicy` confere o escopo autorizado do plano. O planner passa à porta de evidência o mesmo objeto imutável que foi aprovado, e `execute_plan` é a fronteira para uma eventual proposta de plano por LLM. Planos de escrita, de outra fonte ou fora do escopo não chegam à porta. Dois perfis sintéticos exercitam o mesmo mecanismo. O contrato usa Pydantic 2.13.4 no ambiente verificado, seguindo a [documentação de modelos e validação](https://docs.pydantic.dev/latest/concepts/models/).

Um plano aprovado **não autoriza SQL textual arbitrário**. Se a equipe escolher geração de SQL, o parser/validador de AST e dialeto ficará no caminho concreto de execução definido após 5.0; a credencial e as permissões somente leitura do banco terão de ser verificadas na integração. A frase de período ainda precisa ser resolvida para janela e grão reais antes de uma consulta Gold. Nenhum nome de tabela, coluna ou fórmula oficial foi colocado no validador lógico.

### Proteção da evidência e da resposta

`EvidenceProvenance` declara fonte, referência, impressão do plano aprovado, versão do catálogo, métrica, unidade, janela, dimensões e filtros aplicados. `EvidenceGuard` confere esses campos, a versão do resultado, finitude da medida, limite de linhas do próprio plano e tamanho serializado (16 KiB por padrão). O contrato aceita no máximo 100 linhas; a configuração pode reduzir esse teto. Resultado sem proveniência ou com recorte diferente vira erro controlado antes do modelo. A impressão é um identificador local do plano; não prova que um banco executou aquela consulta. O adaptador real precisará fornecer proveniência verificável e aplicar permissões próprias.

O perfil classifica os campos de evidência por papel, tipo e sensibilidade. Apenas a medida numérica classificada e a unidade aprovada chegam ao provedor, com IDs `row_N`; campos desconhecidos, pessoais, notas e descrições da fonte são removidos. Limitações devem corresponder a textos aprovados no catálogo e são preservadas na resposta junto de `is_demo`. Mensagens livres de ausência ou esclarecimento vindas da fonte são substituídas por mensagens fixas. Logs de falha não incluem pergunta, payload, exceção ou texto da fonte.

`GeneratedAnswer.observation_ids` permite ao modelo escolher até dez observações existentes. O orquestrador confirma os IDs e escreve a resposta quantitativa com métrica, período, valor e unidade do plano/evidência; ignora o texto livre retornado pelo modelo em `answered`. No insight local, o modelo escolhe observações da tela e o serviço compõe a hipótese pública sem copiar a narrativa do modelo. Não se calcula comparação nem se arredonda valor neste fluxo; base zero, falta de dados e incompatibilidade de unidade/grão são tratados como ausência/esclarecimento na ferramenta sintética. Isso evita atribuir significado a números só por coincidirem como tokens, mas não confirma a veracidade de observações fornecidas pelo navegador ou fórmulas Gold.

### Orçamento, cache e fallback da execução sintética

`ExecutionController` mantém um prazo total por chamada, prazos separados para fonte e modelo, contadores de chamadas e semáforos compartilhados pela instância do serviço. A espera por vaga consome o prazo. Os padrões são 30 s por solicitação, 10 s para fonte e 20 s para modelo, uma consulta à fonte, até três tentativas de modelo na cadeia, 16 solicitações, 8 fontes e 8 modelos simultâneos por processo. Todas essas opções têm limites de configuração em `Settings` e aparecem no `.env.example`. Prazo ou contagem excedidos geram `limit_exceeded` com `retryable: false`; cancelamento externo propaga para a chamada assíncrona em andamento e libera a vaga. O SDK Gemini recebe timeout próprio e desativa suas tentativas implícitas. Cancelar uma coroutine não comprova que um cliente síncrono ou operação remota interrompeu trabalho; isso deve ser verificado na integração concreta.

O fallback avança somente após `ModelProviderUnavailable`, até o máximo configurado e dentro do prazo total. A pausa entre tentativas pode ser configurada e é limitada a cinco segundos; recusa, resposta inválida e erro inesperado não abrem outro caminho. O cache em memória continua desligado por padrão. Quando ativado, só guarda resposta `answered` após autorização, proveniência validada e criação de um escopo que inclui chamador, permissões, perfil, fonte, plano e catálogo; pergunta, histórico, evidência, prompt e sequência de modelos entram na chave. A autorização e a validação da evidência são repetidas em cada solicitação antes de consultar o cache, e a saída é validada novamente depois do cache/fallback. Sem escopo confiável, como no insight sintético enviado pelo navegador, a chamada ignora o cache. Se todos os solicitantes de uma geração compartilhada desistirem, o trabalho assíncrono pendente é cancelado.

### Dependências atuais e direção desejada

A composição do núcleo está em `app/agent/composition.py`: recebe perfil/catálogo, política, fonte de evidência, adaptador de modelo, limites e destino de eventos por injeção. O fluxo completo mantém interpretação determinística, autorização do plano, validação e redução da evidência antes da geração, além da validação da saída. A API apenas recebe o request e traduz a resposta. Instruções genéricas de geração ficam em `app/generation/prompts.py`; vocabulário, exemplos e regras de negócio ficam no perfil. Gemini, modelo falso e fallback usam o mesmo protocolo e os mesmos controles do orquestrador. Eventos internos por estágio dão correlação e códigos seguros; o destino padrão não persiste dados. Autenticação verificada ainda precisa ser implementada. A validação lógica e a classificação de campos foram exercitadas com Grid 360 sintético e um segundo perfil artificial fora do domínio elétrico; a prova integrada de reuso com dois adaptadores ainda está pendente.

Os mecanismos podem ser implementados e testados sem Gold usando catálogos, identidades e fontes de teste. A porta de evidências é assíncrona. `ExecutionController` aplica prazo total e limites por fonte/modelo, conta chamadas e compartilha semáforos por processo. Testes com fontes falsas verificam concorrência e propagação de cancelamento; uma implementação concreta ainda precisa evitar trabalho bloqueante no event loop. Adaptadores para clientes síncronos precisam delegar o trabalho bloqueante a um executor e definir como timeout e cancelamento chegam ao cliente. Autenticação efetiva, catálogo oficial, execução/validação SQL, permissões do banco e reconciliação continuam na integração específica da plataforma. O núcleo valida operações e planos lógicos; a segurança da consulta concreta também precisa ser imposta pelo componente que a executa. Esta direção preserva a proposta ainda aberta da ADR-0001.

O fluxo de perguntas segue esta direção: `app/api/routes.py` valida/encaminha os schemas HTTP para o caso de uso composto; `app/agent/orchestrator.py` aplica segurança, chama `QuestionAnalysisPlanner` e usa a porta de geração `ModelAdapter`; o planner interpreta a pergunta, monta e valida o plano lógico, autoriza o escopo e só então chama `EvidenceSource`; o adaptador sintético traduz o plano para os cenários de demonstração. O fluxo de insights também entra por `routes.py`, recebe o `ScreenInsightOrchestrator` e usa `ModelAdapter`. Importar e chamar `compose_core` não inicializa FastAPI, SDK de modelo, fixture ou cliente de banco.

| Parte | Dependências observadas | Regra para a integração futura |
| --- | --- | --- |
| `app/api/` | Rotas FastAPI e schemas públicos; obtém os orquestradores de `app.state`. | A borda HTTP conhece os casos de uso e contratos públicos, sem importar adaptador Gold ou SDK de modelo. |
| `app/agent/` | Planner, interpretador, schemas de interpretação, perfil/catálogo, porta de evidência e protocolo do modelo. | Núcleo coordena contratos e regras; vocabulário vem do perfil; não importa fixture, driver SQL/ORM nem SDK de provedor. |
| `app/agent/composition.py` e `app/ports/events.py` | Montagem dos casos de uso por injeção e destino de eventos substituível. | Eventos por estágio são operacionais; persistência durável, retenção e coleta distribuída pertencem à integração/8.6. |
| `app/generation/prompts.py` | Instruções genéricas de seleção e fundamentação. | Glossário, exemplos e regras de negócio continuam no perfil, sem código de fornecedor. |
| `app/tools/synthetic_analytics.py` e `app/scenarios.py` | `SyntheticScenarioTool` implementa a porta `EvidenceSource` e usa o catálogo de demonstração. | O adaptador de saída importa o contrato que implementa; o núcleo chama o contrato sem importar essa implementação. |
| `app/providers/` | `ModelAdapter` é o protocolo; Gemini e outros adaptadores implementam-no. A fábrica os constrói. | O adaptador implementa o protocolo e encapsula o SDK. O núcleo importa o protocolo, nunca o adaptador concreto ou seu SDK. |
| `app/main.py` | Borda FastAPI e escolha das implementações locais antes de chamar `compose_core`. | A fixture e o perfil atuais permanecem explicitamente demonstrativos. |

Na resposta pública de perguntas, `answered` exige texto em `answer`; esclarecimento, recusa, ausência de evidência e falha exigem texto em `message`. Os campos são mutuamente exclusivos. Em insight, `answered` exige `hypothesis`; os outros estados exigem `message`. Hipótese e mensagem de insight exigem texto não vazio e têm limite de 4.000 caracteres. Adaptadores de modelo são validados novamente na fronteira do orquestrador mesmo quando a anotação declara `GeneratedAnswer`; um retorno inválido vira `recoverable_error` genérico.

`AnalysisIntent` vive em `app/schemas/analysis.py`, separado dos modelos de fixture; `app/schemas/scenarios.py` mantém `SyntheticScenario`. O contrato usa um ID lógico de domínio, sem enumeração fixa. Os nomes, métricas e frases específicos do Grid 360 ficam no perfil demonstrativo de `app/profiles/grid360_demo.py`.

Os contratos de intenção, solicitação (`QuestionRequest`) e evidência têm versão interna `v1`; no endpoint, a versão do request pode ser omitida para compatibilidade e assume `v1`, mas `null` e versões não suportadas são rejeitadas. Os modelos `EvidenceResult`, `EvidenceLookupResult` e seus estados vivem em `app/schemas/evidence.py`; a porta `EvidenceSource` e as exceções de indisponibilidade/acesso negado vivem em `app/ports/evidence.py`. O pacote `app/tools/` contém implementações, não os contratos compartilhados. `AnalysisIntent` preserva as frases e recebe IDs lógicos de métrica/dimensões do perfil selecionado, sem fixar nomes físicos. Ausência de filtro é representada por campo omitido; `null` explícito é inválido; filtro desconhecido deve pedir esclarecimento; consulta válida sem linhas é `no_evidence`; indisponibilidade e acesso negado são falhas tipadas distintas. O perfil Grid 360 v1 é demonstrativo, não catálogo Gold. A inspeção dos imports em 18/10/2026 não encontrou driver de banco, ORM ou conexão Gold no módulo GenAI.

### Limites e dados de auditoria da fonte

O contrato interno aceita no máximo 100 registros por resultado e o guard impõe também o limite configurado do plano e o teto configurado de bytes serializados (16 KiB por padrão); uma resposta inválida é convertida em erro recuperável genérico antes da geração. Referência com `source` e `description` é obrigatória, mas a descrição livre da fonte é substituída por texto fixo antes do modelo e da API. A fixture sinaliza filtros não representados como `no_evidence`, sem chamar o modelo.

Este limite é uma proteção de payload, não autorização nem timeout de consulta. A identidade e o escopo autorizado precisam vir de contexto confiável da integração, nunca do texto da pergunta; o adaptador/fonte proprietária deve impor timeout, allowlist, limite de execução e auditoria. A API GenAI atual não autentica consumidores e não registra uma trilha de consulta Gold; correlação, versão do lote e formato final de auditoria dependem do contrato conjunto com Backend e Engenharia de Dados. Esses controles da integração Gold ainda não estão implementados nem verificados.

Para qualquer fonte futura, o contrato operacional deve exigir: identidade e autorização derivadas de credenciais/contexto serviço-a-serviço confiáveis; escopo de métricas e dimensões validado no servidor; timeout aplicado na fonte e também limitado pela chamada entre serviços; teto de linhas e de tamanho do payload antes de entregar evidências ao modelo; e referências estáveis que permitam identificar a origem e as limitações do resultado. A pergunta, o histórico enviado pelo consumidor e qualquer conteúdo retornado pela fonte são dados não confiáveis e não podem conceder acesso. O limite de 100 registros em `EvidenceResult` é apenas uma validação de contrato/payload: não interrompe consulta lenta nem substitui limites no executor.

Uma trilha interna mínima para a integração real deve registrar, quando disponíveis, identificador de correlação, identificador/versão do adaptador, estado e código interno estável, origem/versão do lote, filtros aplicados já normalizados, contagem de registros e duração. Registrar esses campos depende de contrato com Backend/Dados e de uma política de retenção e acesso. Não registrar por padrão pergunta ou histórico em texto bruto, identificadores pessoais, linhas detalhadas, SQL, prompts completos, credenciais, stack traces ou conteúdo de exceção. Para falhas da fonte, o núcleo mapeia exceções inesperadas para `EvidenceToolUnavailable`, devolve a mensagem recuperável genérica e emite somente um aviso fixo sem pergunta nem detalhe da exceção; isso evita vazamento acidental, mas ainda não constitui auditoria operacional completa.

**Estado verificado no protótipo:** fonte sintética e fontes falsas passam pelo mesmo contrato; retorno `None`, objeto de tipo incorreto e modelo Pydantic construído sem validação são rejeitados antes do uso. Resultado acima dos limites, sem proveniência ou com recorte divergente é rejeitado. Um `EvidenceResult` vazio pode existir como fixture interna, mas não pode ser devolvido com estado `available`; a fonte deve responder `no_evidence`. A porta é async, e testes com fontes falsas cobrem concorrência e propagação de cancelamento. Falhas da fonte resultam em estado recuperável, e acesso negado em recusa genérica, sem expor detalhes internos. Eventos estruturados por estágio existem localmente; persistência durável, retenção, autorização efetiva, timeout no cliente real e conexão somente leitura pertencem à integração futura e não foram implementados nem verificados. O cancelamento só chega ao executor real se o adaptador e o cliente subjacente cooperarem.

### Eventos internos seguros

`EventTrace` em `app/ports/events.py` produz eventos de solicitação, política, plano, fonte, evidência, modelo e resposta. O contrato fechado `CoreEvent` aceita somente fluxo, estágio, código, resultado, correlação gerada pelo serviço, duração em milissegundos, contagens de chamadas/linhas, versões `v1` e fingerprints hexadecimais do plano e da referência. Valores do plano e `source` fornecido por adaptador ou cliente não são serializados no evento. Pergunta, histórico, prompt, linhas, SQL, identidade pessoal, credencial, descrição livre e exceção não são campos permitidos. A referência é um hash para correlação interna, não prova independente de execução da Gold.

O `EventSink` é injetado e, por padrão, é `NoopEventSink`. Falha do destino opcional gera apenas aviso fixo e jamais muda uma recusa para autorização. Se a composição solicitar `require_durable_audit=True`, um destino sem declaração explícita de durabilidade ou que falhe no registro interrompe o fluxo com erro recuperável; a emissão inicial ocorre antes de consultar fonte ou modelo. Declarar `durable=True` é apenas um contrato para o adaptador: a implementação real ainda precisa comprovar confirmação de gravação, disponibilidade, retenção e acesso antes de habilitar essa política em produção. Uma falha em evento posterior também bloqueia a próxima etapa ou a resposta, mas não desfaz consultas já executadas. A correlação no HTTP é gerada pela borda inclusive nas recusas sem identidade. Coleta distribuída, dashboards e alertas ficam para 8.6.

### Segurança demonstrada e limites

- `QuestionSafetyGate` aplica regras explícitas antes de qualquer ferramenta para os padrões cobertos no conjunto sintético. Um padrão lexical não reconhecido ainda pode exigir revisão; esta camada não substitui autenticação, autorização ou controles do executor real.
- Resposta quantitativa exige IDs de observação válidos; a API monta o texto a partir da evidência aprovada. O modelo não escolhe unidade, período nem número livremente na saída. Fórmulas, causalidade e reconciliação numérica com Gold continuam pendentes.
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
