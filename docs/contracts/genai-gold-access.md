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

A dependência analítica está pronta para a futura coordenação, que deve passar o callback a `plan_gold_question` e revalidar antes de executar/servir cache. Não existe cache Gold neste caminho. Esta entrega comprova integração de software com PostgreSQL descartável e sessões reais artificiais; não comprova uma pergunta quantitativa Gold de ponta a ponta, fonte privada carregada ou rotação de segredo no ambiente real.

## Evidência reproduzível — 31/10/2026

- `python -m pytest -q -p no:cacheprovider --tb=short tests/test_genai_session_access.py tests/test_order_sessions.py tests/test_ai_chat.py tests/test_genai_planning_metadata.py tests/test_genai_internal_contract.py`: 116 passaram na execução dirigida de sessão/login/chat/contratos.
- Após acrescentar a verificação de cookie inválido, `python -m pytest -q -p no:cacheprovider --tb=short tests/test_genai_session_access.py`: 6 passaram.
- PostgreSQL 16 descartável, `python -m pytest -q -p no:cacheprovider --tb=short tests/test_gold_reader.py tests/test_genai_session_postgres.py`: 2 passaram em 8,43 s; containers removidos. Ruff com a configuração de `backend/`, compileall nos arquivos Python alterados e `git diff --check` passaram.
- `tests/test_genai_session_postgres.py` usa `TEST_POSTGRES_URL` e `TEST_GOLD_READER_ADMIN_URL` num PostgreSQL 16 descartável com `gold_reader_test`. Migrações, login por cookie, dependências FastAPI, produtor de metadados e leitura com papel dedicado são reais. Duas contas produzem chamadores distintos; contexto adulterado não amplia acesso; retirada de permissão após admissão retorna 403 e zero SQL do leitor; logout nega novo acesso.
- A mesma prova contorna o default READ ONLY e a validação da aplicação: o banco nega IDs/medidas individuais, coluna não concedida, atendimento individual, contas/sessões, ordens, publicação subjacente, escrita, alteração de schema e TEMP. Também confirma que grants perigosos herdados de `PUBLIC` impedem provisionar. Tudo usa dados e senhas artificiais no container descartável.
- Continuação após `57e1b96`: regressão reproduziu parâmetros de URL aceitos indevidamente; a fábrica agora bloqueia a sobreposição de credencial/destino e mantém TLS permitido. Prova PostgreSQL estendida confirma negação de uma função `SECURITY DEFINER` que lê usuários, reprova o provisionamento ao conceder EXECUTE dessa função a `PUBLIC` e verifica rotação de senha com rejeição do segredo antigo. Nenhum cenário usa registros ou credenciais reais.

O PRD e o Trello mantêm os estados oficiais; configuração e uso com a fonte real, executor e evidência quantitativa continuam pendentes. Entrega versionada na branch `feat/genai-acesso-gold-por-sessao`; identidade e conexão no commit `8ef3c92`, com provisionamento, prova PostgreSQL e documentação na mesma sequência. Publicação acompanhada no cartão GENAI-05.

## Fechamento das lacunas locais do GENAI-05 — 31/10/2026

| Item do cartão | Implementação e prova disponíveis nesta branch | Pendência delimitada |
| --- | --- | --- |
| Credencial restrita e separação de carga/leitura | Provisionador SQL reproduzível, segredo exclusivo Backend, engine dedicado e migração/leitura com identidades distintas; prova PostgreSQL com papel real restrito | Instalar/rotacionar o segredo e conferir o provisionamento no ambiente Gold de destino; nenhuma credencial real foi criada por esta entrega |
| Fontes e colunas aprovadas | Grants da matriz acima e testes de negação no PostgreSQL, incluindo UC, medidas individuais, tabelas operacionais, escrita e criação, mesmo contornando a aplicação | Validar a mesma configuração no ambiente autorizado; o teste descartável não representa a instalação real |
| Escopo por consulta, duas identidades e contexto adulterado | Resolvedor relê autorização; teste HTTP alterna pessoa autorizada e pessoa sem permissões, mantendo tentativa de impersonação em pergunta, query string e cabeçalhos; sessão negada recebe 403 sem evidência e sem chamada GenAI | O consumidor deve chamar o callback na execução (GENAI-06). Não há cache Gold nesta branch; qualquer implementação futura deve revalidar antes de servir cache |

A fixture compartilhada de autenticação passou a distinguir `permissions=None` (permissão padrão de teste) de `permissions=[]` (sem permissões). Antes, uma lista vazia criava acidentalmente uma pessoa leitora, impedindo provar esse caso com fidelidade.

Verificação reproduzível em `backend/`, PostgreSQL 16 descartável configurado pelo script `scripts/prepare_test_postgres.sql`, com `TEST_POSTGRES_URL` e `TEST_GOLD_READER_ADMIN_URL` apontando exclusivamente para esses bancos: `python -m pytest -q -p no:cacheprovider --tb=short tests/test_genai_session_access.py tests/test_genai_session_postgres.py tests/test_gold_reader.py tests/test_order_sessions.py tests/test_ai_chat.py`: **31 aprovados**, um aviso preexistente Starlette/httpx. Imagem recebeu as dependências declaradas `pwdlib[argon2]` e `sqlglot>=30.23,<31`. Ruff de `test_genai_session_access.py`, compilação dos dois arquivos de teste alterados e diff-check passaram. Nenhum executor GENAI-06 foi incluído nesta branch.
