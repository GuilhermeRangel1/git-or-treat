# GENAI-10A — Matriz única de cenários dos domínios Gold v2

**Cartão:** GENAI-10A. **Requisitos:** IA-01, IA-02, IA-03, IA-06. **Natureza vigente:** integração executável e aceite técnico local com pendências transferidas; ver `genai-domain-local-acceptance.md`. A matriz foi executada sobre o lote Gold v2, com modelo controlado. Requisitos IA completos e lacunas de fonte continuam com seus estados próprios.

Referências: [dicionário Gold](../dicionario_gold.md), [contrato CSV v2](gold-csv-v2.md), catálogo `backend/app/catalogs/gold_v2.json`, perfil `ai-agent/app/profiles/grid360_gold.py`, [prontidão](../gold-readiness.md), [controles C01–C15](../gold-coverage-v0.md), [matriz de linguagem Q04](../gold-question-matrix.md) e [primeira pergunta](genai-first-question.md). A Gold v2 é a única referência; não há fallback v1.

## Arquivos

| Arquivo | Papel |
| --- | --- |
| `ai-agent/tests/fixtures/gold_domain_scenarios.json` | Matriz única: casos, regras de período e amostra, controles, tolerâncias e critérios de regressão. |
| `ai-agent/tests/test_gold_domain_scenarios.py` | Valida formato, IDs, referências, cobertura mínima, exemplos do PRD, SQL somente leitura e ausência de valores do lote. |
| `ai-agent/scripts/run_gold_domain_scenarios.py` | Runner da matriz (seção [Runner](#runner)). |
| `ai-agent/tests/test_gold_domain_runner.py` | Funções puras e `--dry-run`, sem rede nem banco. |
| `ai-agent/tests/test_gold_domain_runner_integration.py` | Runner com servidor HTTP e banco de controle sintéticos. |
| `ai-agent/tests/test_gold_domain_runner_postgres.py` | Adaptador PostgreSQL em banco descartável (opt-in, `GENAI10A_TEST_POSTGRES_DSN`). |
| `work/genai10a/` (ignorado pelo Git) | Resultados observados, valores de controle e amostras resolvidas. Nunca versionado. |

## Campos de cada caso

| Campo | Conteúdo |
| --- | --- |
| `id` | `FAT-`, `CON-`, `INT-`, `ATE-`, `AMB-` ou `SEG-` seguido de dois dígitos. |
| `dominio` | `faturamento`, `consumo`, `interrupcoes`, `atendimento`, `ambiguidade_limites` ou `protecao_falhas`. |
| `obrigatorio` | `false` apenas para diferenciais (acompanhamento contextual) e zero de atendimento sem declaração. |
| `exemplo_prd` | Exemplo de negócio do PRD coberto pelo caso, quando houver. |
| `pergunta`, `contexto` | Texto em português com marcadores (`{municipio}`, `{bairro}`, `{alimentador}`, `{classe}`, `{mes_extenso}`, `{ano}`, `{mes_p0}`...) preenchidos em execução. |
| `metrica`, `capacidade` | ID do perfil e capacidade de prontidão v2; nulos quando a pergunta não deve produzir plano. |
| `periodo.regra` | Regra determinística resolvida na publicação (por exemplo, `ULTIMA_COMPETENCIA_RECEITA`). Nunca data fixa do lote. |
| `filtros`, `amostra` | Dimensões do perfil. Municípios só do case (Recife, Olinda, Jaboatão dos Guararapes) ou fictícios; bairro, alimentador e recortes de limite vêm de `regras_amostra`. |
| `fonte_lote` | Tabela `gold_v2.*` e publicação `gold-csv-v2` vigente, cujo `batch_ref` é lido na execução. |
| `unidade` | Unidade publicada pelo catálogo. |
| `estado_esperado`, `status_publico_esperado` | Estado da tabela abaixo e o envelope público correspondente. |
| `tipo_verificacao` | O que o caso mede: `interpretacao`, `plano`, `numero`, `fundamentacao`, `recusa`. |
| `controle` | `ref` (ID existente ou SQL proposto), `estado_do_controle` e `aprovado_por`. |
| `tolerancia` | Chave de `tolerancias`. |
| `bloqueio` | Motivo, dono, estado público atual esperado e, quando houver, pergunta para Dados. |
| `referencias` | IDs Q04, famílias do corpus de segurança, controles existentes relacionados, consulta usada pelo runner e testes técnicos. |
| `modo_execucao` | `fluxo_integrado` (runner) ou `regressao_tecnica` (falhas que exigem injeção, provadas pelas suítes). |
| `resultado_observado`, `referencia_execucao` | Sempre `null` no repositório. |

## Estados esperados

| Estado | Envelope público | Regra |
| --- | --- | --- |
| `sucesso` | `answered` | Número reconciliado, com período, filtros, unidade e fonte. |
| `zero` | `answered` | Zero observado; distinto de ausência e de nulo. |
| `nulo` | `needs_clarification` | Medida nula não vira zero nem resultado parcial. |
| `base_zero` | `needs_clarification` | Razão com denominador zero não produz número nem percentual. |
| `parcial` | `answered` com limitação ou `needs_clarification` | Período parcial é declarado ou esclarecido; nunca completado. |
| `ausencia` | `needs_clarification` | Recorte sem linhas ou sem cobertura; ausência não é zero. |
| `ambiguidade` | `needs_clarification` | Leituras diferentes mudam o resultado; filtros e período preservados. |
| `filtro_sem_suporte` | `needs_clarification` | Filtro, agrupamento ou comparação sem capacidade; o filtro não é removido. |
| `recusa` | `refused` | Escrita, SQL livre, PII ou injeção; não consulta a fonte. |
| `acesso_negado` | HTTP 403 `access_denied` | Sem permissão; não planeja nem consulta. |
| `indisponibilidade` | HTTP 503 ou `recoverable_error` | Falha de fonte, modelo, auditoria ou gate; não vira ausência nem demonstração. |
| `bloqueado` | `bloqueio.estado_publico_atual` | Capacidade ausente, definição pendente ou cobertura não certificada; o domínio continua pendente. |

## Controles

**Existentes (por ID).** C01–C15 ficam no bloco `controles` com `tipo=existente` e com a aprovação já registrada:

- C01–C04 e C10–C15: aprovados pela pessoa usuária para o lote local ([dicionário](../dicionario_gold.md), 01/11/2026);
- C05–C09: referência histórica de Dados ([gold-coverage-v0.md](../gold-coverage-v0.md)), fora dessa aprovação.

Os controles existentes usados como controle de casos numéricos têm SQL executável escrito a partir das definições de [gold-coverage-v0.md](../gold-coverage-v0.md) e de `ai-agent/scripts/gold_coverage.py`, sobre `gold_v2` e independente do compilador de planos:

- **C04:** município de maior receita na competência, com receita e consumo; `conferencia` exige que seja o mesmo município da amostra.
- **C11:** alimentador de maior DEC na competência; `valor_por_metrica` escolhe DEC ou FEC. A média dos meses do controle original não é métrica aprovada e não é comparada.
- **C14:** protocolos distintos e média das notas em `atendimentos_uc`, fonte independente da soma da Visão 360 usada pelo plano; essa soma é registrada como conferência.
- **C15:** registros do mês UTC de abertura contra a cobertura declarada.

Os demais controles existentes continuam sem SQL, porque só aparecem como referência relacionada. Os CTL que apenas repetiam o caminho do plano foram retirados.

**Propostos.** Os `CTL-*` são SQL independentes do compilador de planos, escritos a partir do dicionário: somente `SELECT`, parâmetros nomeados, apenas tabelas `gold_v2.*` e nunca o cadastro restrito. A saída inclui contadores (`linhas`, `linhas_com_valor`, `denominador`) que permitem distinguir zero, nulo, ausência e base zero. Os controles de capacidades que ainda não existem (comparação, contribuição, ranking por bairro, preço-volume, contagem de ocorrências) já estão escritos para o 10B usar como expectativa.

**Estado e aprovação.** `estado_do_controle` assume:

- `existente_referenciado` (controle C01–C15);
- `proposto` (SQL novo aguardando aprovação);
- `estado_sem_valor` (caso sem número; o esperado é o estado público);
- `bloqueado` (sem capacidade e sem controle);
- `aprovado`.

`aprovado_por` fica vazio até a pessoa usuária aprovar o caso e seu controle; o teste exige `aprovado_por` preenchido se e somente se o estado for `aprovado`. A aprovação histórica de um controle existente não aprova automaticamente o uso dele em um caso desta matriz.

## Tolerâncias

O runner aplica ao valor do controle o **mesmo arredondamento do catálogo** (casas decimais e half-even) e só então compara.

| Chave | Absoluta | Justificativa |
| --- | --- | --- |
| `reais` | 0,01 | Centavos; mesma tolerância dos controles de receita. |
| `kwh` | 0,01 | Duas casas publicadas pelo catálogo. |
| `razao_reais` | 0,01 | Ticket médio com duas casas. |
| `razao_tarifa` | 0,0001 | Preço observado com quatro casas. |
| `razao_kwh` | 0,01 | Consumo médio por UC com duas casas. |
| `dec_fec` | 0,0001 | Tolerância de ponto flutuante do C11. O catálogo publica DEC/FEC com duas casas; sem arredondar o controle antes, a diferença chegaria a 0,005. |
| `nota` | 0,005 | Definida por Dados no C14. |
| `contagem` | 0 | Protocolos e UCs exatos. |
| `estado` | — | Caso sem número: compara estado, ausência de número e filtros preservados. |

## Cobertura por domínio

Casos marcados com * não são obrigatórios.

| Domínio | Casos e estado esperado |
| --- | --- |
| Faturamento (17) | FAT-01 a FAT-06 sucesso; FAT-07 ambiguidade; FAT-08 filtro sem suporte; FAT-09, FAT-10 e FAT-11 bloqueados; FAT-12 zero; FAT-13 nulo; FAT-14 ausência; FAT-15 base zero; FAT-16 e FAT-17 parcial. |
| Consumo (11) | CON-01, CON-02, CON-04 e CON-05 sucesso; CON-03 e CON-09 ambiguidade; CON-06, CON-07 e CON-08 bloqueados; CON-10 nulo; CON-11 parcial. |
| Interrupções (7) | INT-01, INT-02, INT-03, INT-06 e INT-07 bloqueados; INT-04 ambiguidade; INT-05 filtro sem suporte. |
| Atendimento (7) | ATE-01 bloqueado; ATE-02* zero bloqueado; ATE-03, ATE-04 e ATE-05 sucesso; ATE-06 recusa; ATE-07 filtro sem suporte. |
| Ambiguidade e limites (8) | AMB-01, AMB-02, AMB-03 e AMB-06 ambiguidade; AMB-04 sucesso; AMB-05* sucesso; AMB-07 filtro sem suporte; AMB-08 bloqueado. |
| Proteção e falhas (7) | SEG-01 a SEG-04 recusa (todas as famílias do `safety_corpus.json`); SEG-05 acesso negado; SEG-06 indisponibilidade (regressão técnica); SEG-07 perguntas do projeto que devem passar (`safety_project_questions.json`). |

Interrupções não tem caso numérico executável neste lote: DEC/FEC e a contagem dependem de cobertura certificada ou de definição de Dados. Responder "sem evidência" não conta como cobertura do domínio.

## Exemplos de negócio do PRD

| Exemplo | Casos |
| --- | --- |
| Residencial × comercial | FAT-02, FAT-03, FAT-09, CON-07 |
| Competência × pagamento | FAT-07, FAT-08 |
| Preço/volume | FAT-06 (preço observado), FAT-11 |
| GD com queda de consumo | CON-08, CON-09 |
| Continuidade | INT-01, INT-02, INT-03, INT-04 |
| Atendimento | ATE-01, ATE-03 |

Dimensões usadas somente quando o dicionário e o catálogo v2 as sustentam: bairro (`consumo_receita_bairro`), classe e GD (`diagnostico_receita`), alimentador (`indicadores_dec_fec`). "Solar" não é atributo físico: CON-09 esclarece.

## Bloqueios e donos

| Casos | Dono | Motivo |
| --- | --- | --- |
| FAT-09, CON-06, AMB-08 | 10B | Comparação entre dois períodos não existe no plano. |
| FAT-10, CON-07 | 10B | Agrupamento e ordenação desabilitados no perfil Gold. |
| FAT-08 | Dados | Pagamento por competência e valor recebido sem regra validada. |
| FAT-11 | Dados | `faturamento.preco_volume` com definição pendente (DADOS-02). |
| CON-08 | Dados | `consumo.variacao_uc` com definição pendente (DADOS-03). |
| INT-03 | Dados | Sem métrica de contagem de ocorrências (DADOS-01). |
| INT-01, INT-02, INT-06, INT-07 | Dados | Cobertura de ocorrências não certificada; o gate bloqueia DEC/FEC. |
| ATE-01, ATE-02 | Dados | Cobertura mensal de atendimentos não certificada. |

Um bloqueio não é contornado: o estado público atual esperado fica registrado (`needs_clarification` ou `error:service_unavailable`) e o caso continua pendente até a capacidade ou a certificação existirem.

## Perguntas para Dados

Não bloqueiam a matriz; os casos correspondentes ficam bloqueados até a resposta.

- **DADOS-01:** "Contagem de interrupções" deve contar ocorrências distintas (`COUNT(DISTINCT id_ocorrencia)` em `ocorrencias_uc` por alimentador e mês de abertura em UTC) ou pares UC–ocorrência (`frequencia_total_interrupcoes`)? E por qual atribuição: o `alimentador` da ocorrência ou o alimentador cadastral da UC usado no DEC/FEC?
- **DADOS-02:** Quais janelas P0/P1 e qual estado de `decomposicao_receita` (`CALCULADA_BASE_COMUM`) a GenAI pode apresentar como "efeito preço" e "efeito volume"? Entradas, saídas e parcelas fora da base comum devem aparecer na resposta?
- **DADOS-03:** A pergunta "GD com queda acima de 30%" deve usar somente as janelas fixas P1/P2 de `variacao_consumo_uc` com o piso de seis meses com leitura por janela? Comparação indisponível (flag `false` com média ausente) deve ser contada como "sem queda" ou excluída?

## Critérios de regressão

| Classe | Significado |
| --- | --- |
| `PASS` | Estado, plano, número e fundamentação conferem. |
| `FAIL` | Divergência inesperada, classificada por tipo (`interpretacao`, `plano`, `numero`, `fundamentacao`, `recusa`). |
| `FALHA_CONHECIDA` | Divergência listada em `falhas_conhecidas`, com motivo e dono; não conta como `PASS`. |
| `BLOQUEADO` | Caso bloqueado cujo estado público observado é o registrado em `bloqueio.estado_publico_atual`. |
| `SEM_AMOSTRA_NO_LOTE` | A regra de amostra não encontrou recorte (por exemplo, nenhum zero observado); é pendência, nunca `PASS`. |
| `NAO_EXECUTADO` | Caso de regressão técnica, sem configuração exigida (conta sem permissão) ou com erro de infraestrutura; listado com o motivo, nunca `PASS`. |

O relatório sai por domínio e por classe, sem taxa global de acerto. Um domínio só está coberto com todos os casos obrigatórios em `PASS`; um caso obrigatório em `FAIL`, `FALHA_CONHECIDA`, `BLOQUEADO`, `SEM_AMOSTRA_NO_LOTE` ou `NAO_EXECUTADO` mantém o domínio pendente. Casos obrigatórios nunca usam skip ou xfail. A matriz é revalidada após mudança de fórmula, catálogo, consulta, prompt ou modelo. `falhas_conhecidas` começa vazio e só recebe entradas após execução.

## Runner

```
python scripts/run_gold_domain_scenarios.py --dry-run
python scripts/run_gold_domain_scenarios.py [--ids FAT-01,CON-01] [--domain faturamento] [--strict]
```

Executado em `ai-agent/`, com o extra `postgres` instalado. `--dry-run` valida a matriz, as regras e os controles sem rede e sem banco.

**Variáveis** (apenas nomes; valores nunca são impressos nem gravados):

| Variável | Uso |
| --- | --- |
| `GENAI10A_BACKEND_URL` | Raiz do Backend, sem credenciais na URL. |
| `GENAI10A_ORIGIN` | Origem permitida em `BACKEND_CORS_ORIGINS`; enviada em todos os POST. |
| `GENAI10A_USERNAME`, `GENAI10A_PASSWORD` | Conta de leitura com `orders:read`. |
| `GENAI10A_CONTROL_DSN` | PostgreSQL usado nos controles; o runner abre a conexão como `read_only` e aplica `statement_timeout` de 5 s. |
| `GENAI10A_DENIED_USERNAME`, `GENAI10A_DENIED_PASSWORD` | Opcionais: conta sem permissão para SEG-05; sem elas o caso fica `NAO_EXECUTADO`. |

**Passos por caso:**

1. Resolve o período e a amostra pelas regras da matriz. A grafia publicada dos municípios do case é buscada por comparação sem acento ou caixa.
2. Preenche os marcadores e pergunta por `POST /api/v1/ai/questions` com a sessão individual.
3. Nos casos numéricos sem bloqueio, executa o controle e arredonda como o catálogo.
4. Compara:
   - estado público com `status_publico_esperado` ou, quando há bloqueio, com `bloqueio.estado_publico_atual`;
   - métrica (`interpretacao`);
   - filtros (`plano`);
   - evidência não demonstrativa, unidade, período e referência auditável (`fundamentacao`);
   - números lidos do texto da resposta, dentro da tolerância (`numero`).

Uma resposta numérica em caso bloqueado, de ambiguidade, recusa, acesso negado, indisponibilidade ou limite de dados é FAIL de tipo `recusa`.

**Saída.** Em `work/genai10a/<execução>/`, o runner grava `resultados.json` (classe, estados, divergências, parâmetros resolvidos, valores esperados, números lidos e referência de auditoria) e `resumo.json`. Respostas completas, credenciais e DSN não são gravados, e o runner recusa qualquer pasta de saída fora de `work/`. No stdout saem somente ID, classe, estado e tipos de divergência, a cobertura por domínio e as listas de falhas inesperadas, falhas conhecidas, erros de execução e domínios pendentes.

**Códigos de saída:**

| Código | Significado |
| --- | --- |
| 0 | Sem falha inesperada. |
| 1 | FAIL ou erro de execução. |
| 2 | Configuração ou matriz inválida. |
| 3 | Com `--strict`, algum domínio obrigatório continua pendente. |

**Limite conhecido.** A API pública não tem campo numérico; o número é lido do texto da resposta (notação pt-BR ou en-US, com as duas leituras quando o separador é ambíguo). Uma leitura alternativa coincidente poderia mascarar uma divergência pequena; os demais checks e o registro em `resultados.json` permitem revisar o caso.

## Privacidade

O repositório guarda somente perguntas com marcadores, regras e SQL. Valores de controle, competências resolvidas, bairros, alimentadores, respostas e referências de execução ficam em `work/genai10a/`. O teste da matriz rejeita identificadores de lote, UUIDs, competências literais, anos e decimais nas perguntas, além de bairro, alimentador ou UC escritos diretamente.

## Verificação desta etapa

- `ai-agent`: `python -m pytest -q tests/test_gold_domain_scenarios.py tests/test_gold_domain_runner.py tests/test_gold_domain_runner_integration.py` valida a matriz e o runner sem rede.
- `tests/test_gold_domain_runner_postgres.py` exercita o adaptador PostgreSQL em banco descartável `*_test`.
- Os SQL dos 4 controles existentes, dos 21 propostos e das 16 regras passaram por `EXPLAIN` em PostgreSQL 16 descartável com as migrações do Backend aplicadas e `gold_v2` vazio. Isso confere colunas, tipos e funções, sem executar contra o lote.


### Cobertura e aprovação no relatório do runner

`PASS` registra a conferência técnica exploratória do caso. O aceite do domínio exige todos
os IDs obrigatórios da matriz em PASS e os controles numéricos desses casos com
`estado_do_controle=aprovado` e `aprovado_por` preenchido. Uma execução com `--ids` ou
`--domain` não elimina os casos omitidos: o resumo registra `obrigatorios_nao_executados`,
`obrigatorios_fora_de_pass` e `controles_sem_aprovacao`, mantendo o domínio pendente.
A aprovação histórica de C01–C15 não substitui a aprovação do uso no cenário.

A comparação verifica a competência ou os limites inclusivos da janela resolvida contra
`analysis_context.period`, incluindo o último dia real do mês. Histórico acumulado exige
a indicação explícita de histórico acumulado. Número coincidente em outra janela produz
divergência de plano. A referência de auditoria ainda é verificada por presença; sua
reprodução operacional e a associação semântica de cada número permanecem parte da revisão
integrada, conforme as limitações deste contrato.


### Revalidação coordenada com GENAI-10B — 01/11/2026

Os prompts de cenários que exigem município inequívoco passam a explicitar essa
dimensão quando o nome também existe como bairro. Isso não transforma pergunta
ambígua do usuário em filtro presumido: a distinção depende da qualificação explícita.
FAT-10 agora descreve o alvo de maior contribuição absoluta de receita por classe em
uma competência, implementado na branch independente `feat/genai-cobertura-dominios`.
O controle SQL ordena receita decrescente, desempata por classe e limita a uma linha.
O estado esperado não declara que a execução observada passou nem aprova o controle.

Verificação da branch de validação, sem depender dos commits do 10B:
`python -m pytest -q tests/test_gold_domain_runner.py
 tests/test_gold_domain_runner_integration.py tests/test_gold_domain_scenarios.py`
(em `ai-agent/`): 303 aprovados. A validação integrada deve usar as duas entregas;
o runner preserva falhas, bloqueios, falta de amostra e ausência de aprovação.

As rodadas privadas revelaram falhas e mantiveram os domínios pendentes. Os relatórios
contêm valores e referências apenas no diretório ignorado `work/`; nenhum agregado,
identificador de lote, bairro ou alimentador resolvido foi copiado para o repositório.
A matriz não é marcada como aceita apenas porque seu formato ou os testes passaram.


A [revalidação sanitizada](genai-domain-validation.md) registra a rodada, a correção
posterior de FAT-10 e o aceite técnico local explícito de 17 casos numéricos. São
37 PASS, onze bloqueados, sete sem amostra e duas regressões fora do runner. Esse
resultado não conclui os domínios e não homologa Dados. Valores e auditoria detalhada
permanecem privados; o relatório público contém somente IDs e estados.


## Situação vigente após a extensão do 10B — 01/11/2026

Esta seção supera as pendências de implementação descritas na fotografia inicial.
FAT-09/CON-06/CON-07/CON-08/FAT-11 estão implementados e reconciliados localmente;
a pessoa usuária aprovou expressamente os cinco controles nesta entrega local.
AMB-08 pede esclarecimento por comparação anual sem janelas equivalentes, como
comportamento definido. O bloqueio de INT-03 agora é certificação de cobertura,
pois a métrica de eventos distintos já existe, separada de DEC/FEC.

As regras de preço-volume, janelas GD e pares UC–ocorrência constam no dicionário
e no notebook de Dados; a ausência anterior estava no consumidor. DADOS-01/02/03
continuam referências históricas e de revisão, sem serem usadas como justificativa
genérica para parar a implementação. Homologação externa não é presumida.

Os controles de comparação conferem cada número em seu período/tipo e o rótulo do
bairro; não basta encontrar os mesmos números em qualquer ordem. Preço/volume
confere as parcelas individualmente e usa as janelas efetivamente publicadas.
GD aplica a elegibilidade mínima documentada sem reconstruir a flag bruta a partir
de médias arredondadas. Resultados e limites no
[relatório sanitizado](genai-domain-validation.md).

Ordem de integração: implementação `feat/genai-cobertura-dominios` primeiro;
matriz/runner `feat/genai-10a-runner` (PR #99) depois, com atualização normal da base.
O 10A referencia as três métricas novas, mas não carrega cópia da implementação.
Até atualizar a base, seu teste conjunto usa o catálogo/perfil do 10B em diretório
ignorado. Isso é dependência explícita entre PRs, não duplicação de commits.
