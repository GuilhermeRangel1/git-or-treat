# Autenticação local por sessão — DEV-13.1

Este contrato documenta o login individual no backend FastAPI com cookie de sessão opaco. A interface React usa o proxy Vite para manter a API na mesma origem. A autenticação e os perfis WEB-10 foram exercitados em banco descartável, API e navegador reais. A suíte completa do Backend passou; o requisito permanece em validação enquanto respostas Admin e reconciliação com Gold autorizado estiverem pendentes.

## Modos

- `ORDERS_AUTH_MODE=session`: autenticação individual por sessão persistida no banco operacional. É o modo para login e para acesso Gold integrado.
- `ORDERS_AUTH_MODE=service`: credenciais Bearer privadas para CLI/Swagger e automação local. Não devem ser publicadas ao navegador.
- `ORDERS_AUTH_MODE=demo`: somente desenvolvimento com dados sintéticos; não identifica uma pessoa nem deve acessar dados reais.

Produção usa `session`. O modo de sessão não aceita credenciais de serviço em paralelo. Não existe cadastro público.

A autorização GenAI Gold reutiliza a sessão e a contenção de leitura existente, com conexão analítica restrita separada da resolução operacional. Matriz, configuração e limites em [acesso Gold da GenAI](genai-gold-access.md). Isso não acrescenta perfis por área nem habilita o executor de perguntas Gold.

## Endpoints

- `GET /api/v1/auth/session`: retorna HTTP 200 e `Cache-Control: no-store`, com `{enabled, user, expires_at}`. `user` é nulo para cookie ausente, inválido ou expirado. Em `session`, `enabled` é `true`; nos modos `service` e `demo`, é `false`.
- `POST /api/v1/auth/login`: recebe `{username, password}`. Sucesso retorna o mesmo envelope com usuário; credenciais inválidas retornam 401 genérico, excesso de tentativas 429, origem rejeitada 403 e modo incompatível 503.
- `POST /api/v1/auth/logout`: revoga a sessão e responde 204 sem corpo. É idempotente.

O usuário exposto contém `{id, username, profile, permissions}`; `profile` é nullable e `permissions` contém o catálogo efetivo derivado do perfil em modo WEB-10. A identidade registrada em eventos é `user:<id>` e `auth_mode=session`. O corpo de resposta nunca inclui senha, hash ou token.

## Cookie e proteção

O cookie `grid360_session` contém token aleatório opaco de pelo menos 256 bits, com `HttpOnly`, `SameSite=Lax`, `Path=/api/v1`, host-only e `Secure` em produção. A duração padrão é 3600 segundos, sujeita ao limite configurado. O banco guarda somente o SHA-256 do token, usuário e expiração UTC. Login substitui a sessão atual; logout revoga o token anterior.

Chamadas autenticadas por cookie e operações de autenticação exigem `Origin` exatamente permitido por `BACKEND_CORS_ORIGINS`; origem ausente, `null` e navegação `cross-site` são recusadas. Login aceita somente JSON. O cliente do portal envia cookies com `credentials: include`, não persiste credenciais no armazenamento do navegador e limpa consultas/dados de identidade ao sair ou expirar.

## Provisão local

Após atualizar o esquema, em `backend/`, execute `python -m alembic upgrade head` em um banco operacional local previamente selecionado. Depois execute `python scripts/bootstrap_local_auth.py`. A ferramenta cria, somente quando faltam, contas artificiais para os perfis habilitados pela versão do esquema; para WEB-10 são os cinco perfis descritos abaixo. Senhas iniciais aleatórias ficam em `work/local-auth/credentials.txt`, ignorado pelo Git. Contas existentes não têm senhas, perfis ou permissões redefinidas. Guarde esse arquivo localmente e não o publique.

O script de inicialização Gold não aplica migrações automaticamente. Revise o alvo do banco e mantenha backup adequado antes de atualizar um banco que contenha dados. Não copie credenciais privadas para logs, commits, prompts ou respostas.

### Perfis de plataforma — WEB-10

A decisão aprovada na [ADR-0022](../decisions/0022-perfis-de-acesso-web10.md) substitui `reader`/`operator` como política de autorização do portal em modo `session`. A conta tem um único perfil entre `commercial`, `customer_service`, `losses`, `operations` e `admin`; permissões são derivadas desse perfil e reavaliadas no Backend a cada requisição. O campo `profile` é nullable por compatibilidade: contas legadas continuam autenticáveis, mas perfil nulo/desconhecido recebe zero permissões. O JSON `permissions` legado não concede acesso de plataforma. A matriz detalhada está no [contrato de acesso da plataforma](platform-access.md).

Após atualizar o código, confira o banco local selecionado e aplique a migração explicitamente em `backend/`:

```powershell
python -m alembic upgrade head
python scripts/bootstrap_local_auth.py
```

O bootstrap cria, de forma idempotente, uma conta artificial para cada perfil que ainda não exista; nomes de usuário padrão são os próprios IDs dos perfis e podem ser personalizados com `--commercial-username`, `--customer-service-username`, `--losses-username`, `--operations-username` e `--admin-username`. Senhas aleatórias só são gravadas no arquivo local ignorado `work/local-auth/credentials.txt`. Contas existentes não têm perfil/senha redefinidos ou promovidos. Para recuperar acesso admin, use o processo operacional autorizado para obter acesso ao banco e atribuir explicitamente `admin` à conta existente; não há senha padrão nem rota de recuperação pública.

Para atribuir ou revogar um perfil de conta existente, em `backend/`:

```powershell
python scripts/set_user_profile.py --username <usuario> --profile admin
python scripts/set_user_profile.py --username <usuario> --clear-profile
```

Substitua `admin` por um dos cinco IDs válidos para atribuição. `--clear-profile` deixa a conta autenticável sem perfil e, portanto, sem permissões de plataforma; a próxima requisição relê essa alteração. A operação não redefine senha nem revoga o cookie, mas autorização é reavaliada no servidor. As opções `--database-url` dos dois scripts são sobrescritas explícitas; mantenha DSNs e credenciais fora do histórico do shell e dos arquivos versionados.

Sessão ausente, inválida, expirada, revogada ou de usuário inativo retorna 401 e exige novo login. Uma sessão válida sem perfil autorizado ou sem a permissão do recurso retorna 403; o portal preserva a sessão e mostra acesso negado. Rollback da revisão de perfis (`python -m alembic downgrade genai08000001`) apaga sessões e zera o JSON legado de permissões antes de remover coluna/constraint, para não reativar concessões antigas. Isso desconecta todas as contas e não restaura automaticamente o acesso antigo; reaplique a migração e atribua os perfis de forma explícita para recuperar o modo WEB-10.

`ORDERS_AUTH_MODE=service` continua sendo identidade técnica de leitura analítica em desenvolvimento, sem perfil admin ou `ai:ask`; tokens não são contas de usuário. `ORDERS_AUTH_MODE=demo` continua exclusivo de desenvolvimento com `ANALYTICS_SOURCE=synthetic` e não concede acesso Gold nem substitui sessões por perfil.

## Escopo e verificação

O login não cria cadastro público, recuperação de senha ou perfis por área/território. Os perfis fixos WEB-10 substituem `reader`/`operator` como autorização do portal em sessão. A jornada integrada confirmou navegação, acessos HTTP, ciclo de Perdas e revalidação de sessão; a suíte completa do Backend passou. O aceite permanece `Em validação` enquanto respostas/reconciliação Admin com Gold autorizado não forem comprovadas.

Evidência em 30/10/2026: contra o PostgreSQL descartável `grid360_auth_fullsuite_test`, `python -m pytest tests -q -p no:cacheprovider` em `backend/` aprovou 534 testes, pulou 66 e reportou um aviso Starlette. A migração `8f6a1c2d9e30` foi aplicada somente ao banco operacional local selecionado após backup privado; contagens Gold/operacionais permaneceram iguais e as contas artificiais foram provisionadas no arquivo local ignorado. No navegador com API real passaram login/cookie, permissões reader/operator, reload, logout, replay e credencial inválida. A revisão visual com capturas cobriu 1366×768, 1280×720 e 1440×900. Ver detalhes e limites no [plano de implementação](../plans/2026-10-29-backend-auth-login-grid360-plano.md) e no [Registro de progresso do PRD](../PRD.md). WEB-11 permanece pendente.
