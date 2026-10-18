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
| `POST /api/v1/questions` | `question` (1–1.000 caracteres) e `context` opcional com até três turnos ordenados (`role`: `user` ou `assistant`; `content`: até 1.000 caracteres). Cada chamada deve reenviar o contexto necessário. | `status`, `answer`, `message`, `evidence` e `limitations`. Estados possíveis no contrato: `answered`, `needs_clarification`, `refused`, `no_evidence` e `recoverable_error`. |
| `POST /api/v1/insights` | `screen` com `metric`, `unit`, `period`, `filters`, `observations`, `reference` e `limitations`. A referência deve ter `is_demo: true` durante o protótipo. | `status`, contexto utilizado, `observation.values`, `hypothesis`, `message`, `evidence` e `limitations`. Observação recebida e hipótese gerada ficam em campos separados. |

No chat, o contexto é transitório: o serviço não mantém sessão nem histórico entre chamadas. A continuação usa a última pergunta completa da pessoa usuária apenas quando a nova mensagem é reconhecida como continuação; campos explícitos atuais substituem os valores herdados. Mensagem anterior ambígua leva a esclarecimento. Os turnos são conteúdo fornecido pelo consumidor, não prova de identidade: o serviço os trata como não confiáveis e aplica o safety gate antes de chamar ferramenta ou modelo. O backend precisa enviar somente o histórico autorizado para aquela pessoa/sessão e lidar com autenticação, autorização e retenção.

Este contrato ainda é local e sintético; não há autenticação nesta API nem acordo de integração aprovado pelo backend/frontend. Veja também os exemplos JSON do [README](../../ai-agent/README.md).

## Contrato de uma resposta confiável

Cada resposta quantitativa deve conter: conclusão direta; métrica e unidade; competência/janela; filtros e geografia/classe; valor e comparação quando solicitados; fonte Gold e trilha auditável da consulta ou parâmetros; ressalvas relevantes. Se não há coluna, histórico ou granularidade para responder, dizer isso. Distinguir inferência de dado observado. Não executar ferramentas com efeito de escrita.

## Fluxo sintético implementado

- O interpretador inicial é baseado em regras explícitas. Reconhece termos configurados, preserva frases de métrica/período/geografia/classe e pede esclarecimento para “conta de luz” sem detalhe, períodos ausentes ou bases de comparação ambíguas, mais de um domínio e locais desconhecidos.
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

O planejador recebe uma `EvidenceSource` e envia a intenção já interpretada. O contrato comum `EvidenceLookupResult` representa evidência disponível, ausência de evidência ou necessidade de esclarecimento, além de mensagem e limitações; evidência disponível exige registros não vazios, enquanto ausência e esclarecimento exigem mensagem e não carregam registros. Indisponibilidade da fonte é sinalizada pela exceção `EvidenceToolUnavailable`. `SyntheticScenarioTool` implementa essa porta e traduz a chamada para o catálogo de demonstração. Assim, o núcleo do fluxo e o orquestrador não dependem de `SyntheticScenarioRequest` nem do tipo de resultado interno da fixture.

Esta é uma fronteira interna provisória para permitir substituição controlada da fonte sintética. A proposta é que o Backend seja dono das consultas Gold e exponha um contrato analítico estruturado; essa propriedade e o contrato ainda aguardam revisão de Backend e Engenharia de Dados ([ADR-0001](../decisions/0001-genai-gold-query-owner.md)). O endpoint atual do Backend continua sendo placeholder e não consulta Gold. A fronteira interna da GenAI não define o contrato HTTP entre serviços, nomes de métricas Gold, esquema do banco ou SQL. Uma futura fonte deverá preservar referência, limitações e estados de ausência/indisponibilidade. Na verificação de 18/10/2026, a suíte local passou com 121 testes fora do sandbox Windows; isso não valida integração com Gold.

### Limites e dados de auditoria da fonte

O contrato interno aceita no máximo 100 registros por resultado; uma resposta acima do limite ou inválida é convertida em erro recuperável genérico antes da geração, sem incluir detalhes internos na resposta HTTP. Referência com `source` e `description` é obrigatória e limitada pelo schema público. Adaptadores devem preencher esses campos com identificadores estáveis e descrições controladas, nunca com SQL, stack trace, credenciais, texto bruto do usuário ou conteúdo não minimizado. A fixture já sinaliza filtros não representados como `no_evidence`, sem chamar o modelo.

Este limite é uma proteção de payload, não autorização nem timeout de consulta. A identidade e o escopo autorizado precisam vir de contexto confiável da integração, nunca do texto da pergunta; o adaptador/fonte proprietária deve impor timeout, allowlist, limite de execução e auditoria. A API GenAI atual não autentica consumidores e não registra uma trilha de consulta Gold; correlação, versão do lote e formato final de auditoria dependem do contrato conjunto com Backend e Engenharia de Dados. Esses controles da integração Gold ainda não estão implementados nem verificados.

Para qualquer fonte futura, o contrato operacional deve exigir: identidade e autorização derivadas de credenciais/contexto serviço-a-serviço confiáveis; escopo de métricas e dimensões validado no servidor; timeout aplicado na fonte e também limitado pela chamada entre serviços; teto de linhas e de tamanho do payload antes de entregar evidências ao modelo; e referências estáveis que permitam identificar a origem e as limitações do resultado. A pergunta, o histórico enviado pelo consumidor e qualquer conteúdo retornado pela fonte são dados não confiáveis e não podem conceder acesso. O limite de 100 registros em `EvidenceResult` é apenas uma validação de contrato/payload: não interrompe consulta lenta nem substitui limites no executor.

Uma trilha interna mínima para a integração real deve registrar, quando disponíveis, identificador de correlação, identificador/versão do adaptador, estado e código interno estável, origem/versão do lote, filtros aplicados já normalizados, contagem de registros e duração. Registrar esses campos depende de contrato com Backend/Dados e de uma política de retenção e acesso. Não registrar por padrão pergunta ou histórico em texto bruto, identificadores pessoais, linhas detalhadas, SQL, prompts completos, credenciais, stack traces ou conteúdo de exceção. Para falhas da fonte, o núcleo mapeia exceções inesperadas para `EvidenceToolUnavailable`, devolve a mensagem recuperável genérica e emite somente um aviso fixo sem pergunta nem detalhe da exceção; isso evita vazamento acidental, mas ainda não constitui auditoria operacional completa.

**Estado verificado no protótipo:** fonte sintética e fontes falsas passam pelo mesmo contrato; resultado maior que 100 registros e metadados de referência inválidos são rejeitados; filtros não cobertos e ausência de evidência não produzem consulta ao modelo; falhas tipadas ou inesperadas resultam em estado recuperável, sem expor mensagem da exceção ou pergunta nos logs. Autenticação/autorização, timeout efetivo, auditoria estruturada, retenção e conexão somente leitura pertencem à integração futura e não foram implementados nem verificados. A porta atual é síncrona e não fornece cancelamento/timeout; a escolha de execução fica para o checkpoint 4.4.

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
