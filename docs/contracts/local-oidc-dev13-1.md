# Execução local Gold com OIDC — DEV-13.1

O provedor de desenvolvimento é Keycloak 26.8.1 em Docker, conforme a [ADR-0019](../decisions/0019-oidc-local-docker.md). O banco Gold deve estar carregado e acessível antes da inicialização. Essa execução não importa CSVs nem aplica migrações.

## Inicialização

Com Docker Desktop ativo e dependências Python/frontend instaladas, execute na raiz:

```powershell
./scripts/start-gold-oidc.ps1
```

A conexão é obtida de `DATABASE_URL` do processo ou de `backend/.env`; o parâmetro `-DatabaseUrl` permite usar outra conexão existente. Preserve a conexão privada fora de arquivos versionados e do histórico de comandos. O script recusa portas ocupadas; confira a execução anterior antes de encerrá-la.

Portal: `http://localhost:5173`. API: `http://127.0.0.1:8001`. Provedor: `http://localhost:8082/realms/grid360`. O login redireciona para o Keycloak e retorna ao portal usando PKCE. A URL exata de retorno é controlada pelo cliente local.

As contas artificiais são `reader` e `operator`. As senhas aleatórias e privadas ficam em `work/local-oidc/credentials.txt`, ignorado pelo Git. A conta de leitura não recebe ações de escrita; o servidor também recusa essas operações. Não use contas pessoais ou senhas reaproveitadas nesse provedor.

O provedor pode ser iniciado isoladamente por `backend/venv/Scripts/python.exe backend/scripts/start_local_oidc.py` (ou pelo ambiente `.venv` correspondente). Logs e PIDs de API/frontend ficam em `work/dev131-oidc`. Não publique esses arquivos.

## Recuperação e limites

Falha na inicialização encerra somente os processos API/frontend criados pela chamada. O contêiner do provedor permanece independente; pode ser consultado com `docker compose -f backend/local-oidc/compose.yaml ps` e encerrado com `docker compose -f backend/local-oidc/compose.yaml stop`.

HTTP local exige a opção explícita `OIDC_ALLOW_LOCAL_HTTP=true` em desenvolvimento. Produção recusa essa opção e exige HTTPS. O proxy encaminha o access token recebido do navegador; não acrescenta credenciais de serviço. Tokens de usuário permanecem em memória, e a saída/troca de usuário deve descartar os caches remotos.

A demo `scripts/start-orders-demo.ps1` usa fonte sintética e SQLite sem login. Ela não comprova o acesso Gold. Provas HTTP, testes automáticos e validação visual devem ser identificados separadamente no [registro de evidências](../plans/2026-10-29-dev13-1-gold-frontend-evidencias.md).
