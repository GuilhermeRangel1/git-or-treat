# Testes, transações e consistência

## Escolher evidência pelo risco

| Alteração | Evidência útil |
| --- | --- |
| Regra ou cálculo | Resultado esperado independente, limites e ausência; reconciliação com Gold quando existir. |
| Endpoint/schema | Request → resposta/status/schema, parâmetros inválidos, erro e dependência indisponível. |
| Escrita operacional | Persistência observada em nova sessão, falha parcial, rollback e repetição/concorrência pertinente. |
| Migração/consulta PostgreSQL | Banco descartável da versão suportada; SQLite não comprova comportamento específico de PostgreSQL. |
| Injeção ou autorização | Caminho real HTTP executando a dependência; testar também acesso negado. |

Use doubles para regras isoladas, sem trocar toda a implementação por mocks no teste que deveria comprovar integração. Testes devem verificar efeitos/resultados, não apenas que um método colaborador foi chamado.

## Unidade de trabalho

Defina um único responsável por `commit` no caso de uso. O serviço operacional atual faz `commit`/`rollback`; `get_db` fecha a sessão. Se várias gravações precisarem ser atômicas, componha-as na mesma transação e evite commits internos em repositórios. `flush` envia comandos sem confirmar a transação.

`Session.begin()` pode delimitar uma transação nova; não o encaixe indiscriminadamente após operações que já iniciaram uma transação por autobegin. Um rollback após um commit concluído não desfaz esse commit. Falha na leitura de confirmação ou perda de resposta depois da gravação exige reconciliação, não repetição cega.

Para ordens, valide estados e transições aprovados no servidor. `disabled` no navegador não garante idempotência. Defina identidade da intenção, resposta à repetição e tratamento de concorrência; complemente com operação atômica e restrições/controle de versão quando o domínio exigir. Não invente estados ou constraints como se já estivessem aprovados no PRD.

## Isolamento dos testes

Use `app.dependency_overrides` para dependências FastAPI e restaure os overrides anteriores em `finally`/teardown. Para teste síncrono, `TestClient` e fixtures síncronas são suficientes. Adote `AsyncClient`/plugin assíncrono apenas quando necessário; confira execução do lifespan quando usar transporte ASGI diretamente.

As verificações de migração existentes exigem `TEST_POSTGRES_URL` e banco com nome terminado em `_test`; siga o README e preserve essas travas. Migrações de teste podem executar downgrade: nunca aponte para banco compartilhado ou de desenvolvimento com dados úteis.

Inclua ordenação/paginação, zero versus ausência, filtros combinados e fonte sintética explicitamente identificada nos contratos afetados. Não use dados pessoais nem segredos em fixtures. Evidência sintética comprova o caminho exercitado, não a validade das métricas reais nem os critérios completos do PRD.

Fontes: [overrides FastAPI](https://fastapi.tiangolo.com/advanced/testing-dependencies/), [transações SQLAlchemy 2](https://docs.sqlalchemy.org/en/20/orm/session_basics.html#framing-out-a-begin-commit-rollback-block) e [lifespan em testes HTTPX](https://www.python-httpx.org/advanced/transports/#asgi-startup-and-shutdown).
