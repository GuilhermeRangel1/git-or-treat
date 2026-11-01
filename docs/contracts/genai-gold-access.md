# GENAI-05 — sessão Backend e leitura Gold restrita

Base: [sessão DEV-13.1](local-auth.md), [ADR-0020](../decisions/0020-autenticacao-backend-por-sessao.md), [catálogo Gold](../gold-catalog.md) e [contrato de execução](genai-query-execution.md). Acesso é global como na contenção atual da API Gold, sem acrescentar RBAC por domínio/território.

## Identidade e autorização

`get_genai_gold_access_resolver` usa `get_order_identity`/`resolve_session` com o cookie HttpOnly `grid360_session`. Cada chamada ao callback abre uma sessão ORM e transação novas na conexão operacional: logout, expiração, usuário inativo e retirada de permissão são relidos sem reutilizar o identity map ou snapshot anterior. A conexão termina antes das chamadas à GenAI e não é entregue ao leitor analítico.

A escolha segue a semântica de identity map e isolamento do SQLAlchemy 2.x, consultada via Context7 na [documentação oficial de sessão](https://docs.sqlalchemy.org/en/20/orm/session_basics.html) e de [transações](https://docs.sqlalchemy.org/en/20/orm/session_transaction.html). Expirar objetos dentro de uma transação antiga não garante observar uma revogação concorrente já confirmada.

| Identidade existente | Acesso GenAI Gold |
| --- | --- |
| `reader`, com `orders:read` | leitura dos agregados/colunas abaixo |
| `operator`, com `orders:write` que implica `orders:read` | mesma leitura; nunca escrita Gold |
| sessão ausente, inválida, expirada/revogada ou usuário inativo | HTTP 401 |
| usuário ativo sem leitura | HTTP 403 |
| modo `demo`/`service` | acesso individual Gold GenAI indisponível, HTTP 503 |

O `caller_ref` é o SHA-256 do ator interno com prefixo `session:`; não transporta ID bruto de usuário, cookie ou token. `AccessScope` só permite `read` e os IDs lógicos listados no módulo `app/core/genai_gold_access.py`. Texto da pergunta, histórico, `session_id` conversacional e cabeçalhos não concedem acesso. O token Backend → GenAI continua identificando somente o serviço técnico.

## Fonte e colunas concedidas

O script `backend/scripts/provision_genai_gold_reader.sql` cria o login dedicado `venergy_genai_reader`, sem privilégios administrativos, memberships ou propriedade de objetos. O login operacional e o de carga/migração são distintos do leitor.

| Fonte | Colunas concedidas |
| --- | --- |
| `gold_v2.diagnostico_receita` | competência, município, classe, subgrupo, bandeira, GD; receita total, consumo total, receita/consumo comparáveis; denominadores de UCs faturadas e com leitura |
| `gold_v2.consumo_receita_bairro` | competência, município, bairro, classe; as mesmas medidas e denominadores agregados |
| `gold_v2.indicadores_dec_fec` | competência, município, alimentador, DEC e FEC |
| `gold_v2.consumo_mensal_uc` | apenas competência, para a cobertura temporal do produtor existente; sem UC ou medida individual |
| `gold.publicacao_atual` / `gold.publicacao_linhagem` | views mínimas de publicação/linhagem já existentes |

Métricas lógicas admitidas: faturamento, consumo, ticket médio, tarifa efetiva, consumo médio por UC e DEC/FEC. Dimensões: município, bairro, classe, subgrupo, bandeira, GD e alimentador. UC não integra o escopo; métricas de atendimento continuam fora desta credencial porque o catálogo atual depende de registros/IDs individuais. Grants não substituem prontidão, semântica, controles ou aprovação de uma resposta quantitativa.

O script inspeciona permissões efetivas por coluna, nega escrita, CREATE/TEMP, sequências, funções de aplicação e leituras fora da matriz, inclusive quando herdadas de `PUBLIC`. Ele falha se um papel preexistente tiver privilégios adicionais. As views mínimas usam propriedade do migrador para projetar metadados; suas tabelas subjacentes em `public`, as contas e as ordens não são concedidas ao leitor.

## Configuração reproduzível

1. Selecione explicitamente o banco operacional/analítico local e aplique as migrações por seu processo autorizado de implantação.
2. Como administrador, revise CREATE/TEMP e grants herdados de `PUBLIC` nesse banco; o provisionador não os altera globalmente. Em banco compartilhado, avalie o efeito sobre os demais usuários antes de removê-los.
3. Execute `psql -v ON_ERROR_STOP=1 -f backend/scripts/provision_genai_gold_reader.sql` com a conexão administrativa configurada fora do Git. Use `\password venergy_genai_reader` na sessão administrativa para definir/rotacionar a senha sem colocá-la em comandos versionados.
4. Configure `GENAI_GOLD_DATABASE_URL` como segredo no Backend. Host, porta e banco devem ser os mesmos de `DATABASE_URL`, com usuário `venergy_genai_reader` e senha próprios. Nunca encaminhe a URL à GenAI, ao navegador ou aos logs.

`create_genai_gold_engine` recusa login operacional, driver diferente de `postgresql+psycopg`, fonte/banco divergente e escopos fora da matriz. `get_genai_gold_engine` deriva o acesso pelo callback e encerra o engine ao final da requisição; não existe fallback para `DATABASE_URL`. Erros de configuração são traduzidos para 503 sem conteúdo da URL.

Parâmetros extras das duas URLs são limitados a `sslmode`, `sslrootcert`, `sslcert`, `sslkey`, `channel_binding` e `application_name`. O dialeto incorpora parâmetros da URL aos argumentos do driver; aceitar `user`, `host`, `dbname`, `options` ou `service` permitiria sobrescrever identidade/destino após validar a parte principal da URL. A conexão deve declarar o destino explicitamente; configurações indiretas por serviço/passfile não são aceitas neste leitor. Comportamento conferido via Context7 na [API de criação de engines SQLAlchemy](https://docs.sqlalchemy.org/en/20/core/engines.html).

Na rotação, altere a senha pelo administrador e atualize o segredo Backend de forma coordenada. Encerre os pools antigos/reinicie os workers, pois mudar a senha não invalida conexões já autenticadas. Confirme uma conexão nova com o segredo atualizado e a rejeição do antigo; não registre nenhum dos valores. A prova descartável executa essa sequência sem alterar credenciais da aplicação local.

Por requisição há uma conexão analítica, sem overflow, com espera de pool de 2 s e conexão de 5 s. O papel tem limite de oito conexões, `statement_timeout=5s`, `lock_timeout=2s`, inatividade transacional de 5 s, `work_mem=4MB` e arquivos temporários de 16 MB. Os parâmetros de sessão e READ ONLY são defaults sobrescrevíveis pelo cliente; a barreira contra escrita/leitura indevida é a ACL efetiva. Deadline global de 35 s, máximo de linhas/bytes das evidências, cancelamento e liberação sob carga devem ser aplicados/medidos pelo executor GENAI-06 e GENAI-15; não estão implementados por esses defaults.

Para o executor, a política desta conexão adota os limites já definidos no contrato de execução: até **100 linhas e 16.384 bytes de evidência por requisição**, dentro dos 35 s totais e do teto SQL de 5 s. Os valores não reiniciam entre etapas ou tentativas. GENAI-06 deve limitar/materializar o resultado e conferir o tamanho serializado antes de enviá-lo à síntese; GENAI-15 deve medir concorrência, cancelamento e devolução das conexões. Os grants não implementam esses limites de resposta.

## Caminho público e limites

Em `ANALYTICS_SOURCE=gold`, `POST /api/v1/ai/questions` agora resolve a identidade de sessão. Uma identidade autorizada recebe o erro contratual 503 `service_unavailable` até a integração do executor/coordenador GENAI-06/07. A rota não encaminha a pergunta ao caminho demonstrativo com fonte Gold selecionada. O modo sintético conserva o encaminhamento existente.

A fatia local de GENAI-06 acrescenta `execute_gold_plan`: exige um resultado `planned`, confere novamente fingerprint, catálogo, métrica, filtros, janela e escopo, vincula o chamador à identidade capturada no planejamento e chama o resolvedor antes da consulta, imediatamente antes do SQL e após materializar o resultado. A leitura ocorre no snapshot PostgreSQL `REPEATABLE READ READ ONLY` da publicação capturada, com `statement_timeout` de 5 s, filtros ligados como parâmetros e limites de 100 linhas/16.384 bytes. O escopo de cache calculado inclui chamador, permissões, plano e lote para impedir compartilhamento entre pessoas. Nenhum cache Gold é servido ainda.

Para as métricas atualmente autorizadas, o executor compila `sum`, `ratio_of_sums` e leitura `key_grain_read` a partir dos mapeamentos do catálogo; também reconhece as agregações de contagem/média quando uma métrica vier a ser autorizada. Agrupa por dimensões aprovadas, permite ordenar pela medida ou dimensão agrupada e aplica o `LIMIT` depois da ordenação, com desempate estável. Janelas delimitadas aceitam somente meses/anos completos. Janela de frase acumulada não inventa filtro temporal físico. Planos incompatíveis falham antes da conexão.

O SQL é produzido por SQLAlchemy a partir do plano tipado e dos identificadores do catálogo; o modelo não envia SQL. Esta implementação não gera CTE, subconsulta ou JOIN. O validador SQL legado da demonstração também recusa qualquer JOIN (`join_not_approved`); sua versão atual não carrega nem prova relações/cardinalidade. A evidência serializada tem teto de 100 linhas e 16.384 bytes; excesso gera pedido de recorte menor. Timeout SQL de 5 s, snapshot somente leitura e revalidação de sessão/publicação permanecem aplicados.

A prova PostgreSQL descartável atravessa o planejador do Backend, o endpoint de teste e o executor com papel restrito, e confere soma, razão, DEC, agrupamento/ordenação, filtro parametrizado, zero, nulo e truncamento. Um teste unitário confere o limite de bytes da resposta serializada. A rota pública continua em 503 até GENAI-07 coordenar planejamento, execução e síntese. Esta prova não conclui a checklist inteira do GENAI-06 nem comprova credenciais, schema ou respostas sobre Gold real; carga/cancelamento sob concorrência permanecem GENAI-15.

## Evidência reproduzível — 31/10/2026

- `python -m pytest -q -p no:cacheprovider --tb=short tests/test_genai_session_access.py tests/test_order_sessions.py tests/test_ai_chat.py tests/test_genai_planning_metadata.py tests/test_genai_internal_contract.py`: 116 passaram na execução dirigida de sessão/login/chat/contratos.
- Após acrescentar a verificação de cookie inválido, `python -m pytest -q -p no:cacheprovider --tb=short tests/test_genai_session_access.py`: 6 passaram.
- PostgreSQL 16 descartável, `python -m pytest -q -p no:cacheprovider --tb=short tests/test_gold_reader.py tests/test_genai_session_postgres.py`: 2 passaram em 8,43 s; containers removidos. Ruff com a configuração de `backend/`, compileall nos arquivos Python alterados e `git diff --check` passaram.
- `tests/test_genai_session_postgres.py` usa `TEST_POSTGRES_URL` e `TEST_GOLD_READER_ADMIN_URL` num PostgreSQL 16 descartável com `gold_reader_test`. Migrações, login por cookie, dependências FastAPI, produtor de metadados e leitura com papel dedicado são reais. Duas contas produzem chamadores distintos; contexto adulterado não amplia acesso; retirada de permissão após admissão retorna 403 e zero SQL do leitor; logout nega novo acesso.
- A mesma prova contorna o default READ ONLY e a validação da aplicação: o banco nega IDs/medidas individuais, coluna não concedida, atendimento individual, contas/sessões, ordens, publicação subjacente, escrita, alteração de schema e TEMP. Também confirma que grants perigosos herdados de `PUBLIC` impedem provisionar. Tudo usa dados e senhas artificiais no container descartável.
- Continuação após `57e1b96`: regressão reproduziu parâmetros de URL aceitos indevidamente; a fábrica agora bloqueia a sobreposição de credencial/destino e mantém TLS permitido. Prova PostgreSQL estendida confirma negação de uma função `SECURITY DEFINER` que lê usuários, reprova o provisionamento ao conceder EXECUTE dessa função a `PUBLIC` e verifica rotação de senha com rejeição do segredo antigo. Nenhum cenário usa registros ou credenciais reais.

O PRD e o Trello mantêm os estados oficiais; configuração e uso com a fonte real, executor e evidência quantitativa continuam pendentes. Entrega versionada na branch `feat/genai-acesso-gold-por-sessao`; identidade e conexão no commit `8ef3c92`, com provisionamento, prova PostgreSQL e documentação na mesma sequência. Publicação acompanhada no cartão GENAI-05.

### Continuação local GENAI-06 — razão e nulos

A ordenação por `ratio_of_sums` usa a própria expressão de razão, comprovada com ticket médio 4,0 no PostgreSQL descartável. Se uma linha agregada tiver valor nulo (inclusive razão sem denominador válido), o executor pede esclarecimento e não entrega um subconjunto silenciosamente incompleto. Ausência de linhas permanece `no_evidence`, e zero numérico continua evidência. As regras do catálogo para nulos dentro de SUM/AVG não mudam.

A prova observa ausência de SQL para planos adulterados com fingerprint recalculado (métrica, unidade, limite). Seleção reproduzível em `backend/`: `python -m pytest -q -p no:cacheprovider --tb=short tests/test_genai_executor.py tests/test_genai_session_postgres.py tests/test_genai_plan.py`, com URLs somente para bancos descartáveis conforme `scripts/prepare_test_postgres.sql`: 55 aprovados. Timeout não comprova por si só custo/concorrência/cancelamento; essa parte da checklist GENAI-06 permanece aberta e terá medição complementar em GENAI-15.

- Complemento verificado nesta continuação: contenção real por bloqueio de tabela em PostgreSQL descartável provoca cancelamento SQLSTATE `57014` com timeout de teste de 25 ms (produção permanece 5 s). O executor sai do snapshot com rollback, o pool registra zero conexões emprestadas e a consulta seguinte recupera o mesmo resultado. Isso comprova recuperação após timeout do servidor; não comprova cancelamento por desconexão HTTP nem carga concorrente.
- Seleção final: `python -m pytest -q -p no:cacheprovider --tb=short tests/test_genai_executor.py tests/test_genai_session_postgres.py tests/test_genai_planning_metadata.py tests/test_genai_plan.py tests/test_genai_session_access.py`: **69 aprovados**, 1 aviso preexistente, em PostgreSQL 16 descartável com `pwdlib[argon2]` e `sqlglot>=30.23,<31` presentes na imagem. Os quatro subprocessos que falharam na seleção anterior passaram nesta execução; o registro histórico da falha permanece para rastreabilidade. Ruff e compilação dos arquivos alterados passaram. Continuação sem commit/push.

### Saturação do papel leitor — GENAI-06

O teste PostgreSQL existente mantém oito conexões físicas em pools independentes, confirma oito sessões do papel em `pg_stat_activity` e verifica a recusa da nona conexão. Depois de fechar uma conexão física, o pool anteriormente recusado conecta e executa `SELECT 1`. O encerramento deixa zero conexões emprestadas. Seleção executor/sessão PostgreSQL/contrato de plano: 55 aprovados em PostgreSQL 16 descartável. Essa prova confirma o teto de conexão e recuperação; carga concorrente de consultas, custo e cancelamento HTTP permanecem provas separadas.

Itens objetivos comprovados no GENAI-06: revalidação do plano na execução; valores parametrizados sem SQL livre; identificadores restritos ao catálogo e recusa de plano incompatível antes do SQL. Os testes de contrato, observação do driver e ACL do banco são as evidências. O cartão integral permanece em andamento.

### 31/10/2026 — Revisão do executor GENAI-06 e correções locais

- Revisão independente de padrões e especificação confirmou o reaproveitamento do catálogo, plano tipado e snapshot existentes, sem necessidade de nova arquitetura. Identificou e corrigiu uma ampliação temporal: frases livres em métrica mensal podiam retirar o predicado temporal. O seletor agora exige janela delimitada nessas métricas; a borda executora também exige frase explicitamente aprovada e fonte sem coluna temporal para acumulados. Regressão com fingerprint recalculado comprova recusa antes do SQL.
- `GoldPlanningResult` transporta o `GenAIRequestDeadline` iniciado pelo planejador. O executor exige esse prazo, verifica saldo antes da conexão e após materialização e aplica o menor valor entre 5 s e o saldo global ao timeout SQL. Prazo expirado é recusado antes do SQL; não há renovação do relógio entre planejamento e execução.
- PostgreSQL 16 descartável: `python -m pytest -q -p no:cacheprovider --tb=short tests/test_genai_executor.py tests/test_genai_session_postgres.py tests/test_genai_planning_metadata.py tests/test_genai_plan.py tests/test_gold_catalog.py tests/test_genai_deadline.py`: **116 aprovados**, um aviso preexistente Starlette/httpx. Ruff por configuração Backend e compileall dos quatro arquivos Python alterados passaram; diff-check passou. Inclui a prova de saturação e recuperação do papel leitor anteriormente local.
- Limites preservados: métricas de atendimento não são liberadas pelo escopo atual do GENAI-05; isso não autoriza ampliar grants para fechar testes. Ranking interpretado pelo núcleo ainda não é capacidade declarada; limite atual pede recorte quando excedido, sem entregar parcial silencioso. Amostra Gold autorizada, coordenação pública, cancelamento por desconexão e medição de custo sob carga continuam sem comprovação. Continuação local sem novo commit/push; cartão permanece aberto.

### 31/10/2026 — GENAI-06: matriz quantitativa do escopo autorizado

- O teste PostgreSQL existente passou a executar as sete métricas autorizadas: receita 12, consumo 30 kWh, ticket 4, tarifa efetiva 2,5 R$/kWh, consumo médio 15 kWh/UC, DEC 1,5 e FEC 0,5, com esperados literais independentes do compilador. As medidas comparáveis e denominadores da fixture são explícitos; não usa receita total como numerador de tarifa efetiva.
- Conjunto sem linhas produz `no_evidence`; zero continua registro 0; agregado nulo pede esclarecimento explícito; mais linhas que o limite pede recorte sem entregar parcial. Agrupamento e ordenação existentes continuam comprovados. Isso permite concluir o item de distinção zero/nulo/vazio/truncamento no escopo executável atual.
- Seleção PostgreSQL 16 descartável: `python -m pytest -q -p no:cacheprovider --tb=short tests/test_genai_executor.py tests/test_genai_session_postgres.py tests/test_genai_plan.py tests/test_gold_catalog.py tests/test_genai_deadline.py`: **108 aprovados**, 1 aviso preexistente. Ruff e compilação dos quatro arquivos Python alterados e diff-check passaram.
- O item de todas as métricas permanece parcial: atendimento mensal/acumulado requer aprovação de acesso compatível com a minimização atual, não sendo liberado apenas para concluir checklist. Provas de contagem/média/acumulado e tempo UTC no executor permanecem necessárias. Cartão fica 5/10, sem alterar estado oficial IA; continuação sem novo commit/push.

### 31/10/2026 — GENAI-06: compilação das onze métricas e precisão

- Ampliado o teste PostgreSQL existente para compilar/executar as quatro métricas de atendimento com conexão proprietária exclusivamente de teste, separada do fluxo de autorização: dois protocolos em fevereiro UTC, média 2 incluindo nota zero válida, soma acumulada de chamados 5 e média acumulada 2. Uma abertura em 31/janeiro 22h no fuso -03 pertence a fevereiro UTC; abertura sem data não entra no mês. Os acumulados usam a frase aprovada, sem inventar filtro de datas. Nenhum grant de produção foi ampliado; o leitor restrito continua negando atendimento.
- Corrigida a recusa excessiva de satisfação acumulada: uma fonte pode ter coluna temporal e ainda atender a métrica acumulada expressamente aprovada. A proteção permanece a frase exata do catálogo por métrica; métricas mensais exigem janela delimitada. A prova fecha compilação das onze métricas, mas somente sete são autorizadas no fluxo leitor atual.
- Casos enxutos de precisão verificam half-even em 1,005 / 1,015 / -1,015 e recusa de NaN/infinidades antes de produzir evidência numérica. Não há novas rotas ou catálogo paralelo.
- PostgreSQL 16 descartável: `python -m pytest -q -p no:cacheprovider --tb=short tests/test_genai_executor.py tests/test_genai_session_postgres.py tests/test_genai_plan.py tests/test_gold_catalog.py tests/test_genai_deadline.py`: **114 aprovados**, 1 aviso preexistente. Ruff e compileall dos cinco arquivos Python alterados e diff-check passaram.
- Checklist GENAI-06 passa a 7/10: compilação por métrica e prova no dialeto de soma/contagem/média/razão/grupo/ordem/precisão/ausência agora comprovadas. Limites reais restantes: amostra autorizada e consumo pelo fluxo público; custo/cancelamento e liberação sob execução concorrente; relações/CTE/subconsulta seguem capacidades não suportadas, sem habilitação por esta entrega. A prova de compilador com conexão proprietária não é aceite de autorização de atendimento. Continuação sem novo commit/push.
