# Autenticação local por sessão — DEV-13.1

Este contrato documenta o login individual no backend FastAPI com cookie de sessão opaco. A interface React usa o proxy Vite para manter a API na mesma origem. A implementação integrada foi exercitada em banco descartável e navegador contra API real em 30/10/2026; WEB-10 continua pendente porque o requisito amplo de perfis por cargo ainda não está todo implementado.

## Modos

- `ORDERS_AUTH_MODE=session`: autenticação individual por sessão persistida no banco operacional. É o modo para login e para acesso Gold integrado.
- `ORDERS_AUTH_MODE=service`: credenciais Bearer privadas para CLI/Swagger e automação local. Não devem ser publicadas ao navegador.
- `ORDERS_AUTH_MODE=demo`: somente desenvolvimento com dados sintéticos; não identifica uma pessoa nem deve acessar dados reais.

Produção usa `session`. O modo de sessão não aceita credenciais de serviço em paralelo. Não existe cadastro público.

## Endpoints

- `GET /api/v1/auth/session`: retorna HTTP 200 e `Cache-Control: no-store`, com `{enabled, user, expires_at}`. `user` é nulo para cookie ausente, inválido ou expirado. Em `session`, `enabled` é `true`; nos modos `service` e `demo`, é `false`.
- `POST /api/v1/auth/login`: recebe `{username, password}`. Sucesso retorna o mesmo envelope com usuário; credenciais inválidas retornam 401 genérico, excesso de tentativas 429, origem rejeitada 403 e modo incompatível 503.
- `POST /api/v1/auth/logout`: revoga a sessão e responde 204 sem corpo. É idempotente.

O usuário exposto contém `{id, username, permissions}`; permissões são `orders:read` e `orders:write`. A identidade registrada em eventos é `user:<id>` e `auth_mode=session`. O corpo de resposta nunca inclui senha, hash ou token.

## Cookie e proteção

O cookie `grid360_session` contém token aleatório opaco de pelo menos 256 bits, com `HttpOnly`, `SameSite=Lax`, `Path=/api/v1`, host-only e `Secure` em produção. A duração padrão é 3600 segundos, sujeita ao limite configurado. O banco guarda somente o SHA-256 do token, usuário e expiração UTC. Login substitui a sessão atual; logout revoga o token anterior.

Chamadas autenticadas por cookie e operações de autenticação exigem `Origin` exatamente permitido por `BACKEND_CORS_ORIGINS`; origem ausente, `null` e navegação `cross-site` são recusadas. Login aceita somente JSON. O cliente do portal envia cookies com `credentials: include`, não persiste credenciais no armazenamento do navegador e limpa consultas/dados de identidade ao sair ou expirar.

## Provisão local

Após atualizar o esquema, em `backend/`, execute `python -m alembic upgrade head` em um banco operacional local previamente selecionado. Depois execute `python scripts/bootstrap_local_auth.py`. A ferramenta cria `reader` (`orders:read`) e `operator` (`orders:read`, `orders:write`) somente quando faltam; senhas iniciais aleatórias ficam em `work/local-auth/credentials.txt`, ignorado pelo Git. Contas existentes não têm senhas ou permissões redefinidas. Guarde esse arquivo localmente e não o publique.

O script de inicialização Gold não aplica migrações automaticamente. Revise o alvo do banco e mantenha backup adequado antes de atualizar um banco que contenha dados. Não copie credenciais privadas para logs, commits, prompts ou respostas.

## Escopo e verificação

O login não cria cadastro, recuperação de senha ou perfis por área/território. `reader` e `operator` demonstram apenas permissões globais das ordens. WEB-10 permanece pendente até que perfis e restrições de telas/ações por cargo cubram o escopo completo.

Evidência em 30/10/2026: contra o PostgreSQL descartável `grid360_auth_fullsuite_test`, `python -m pytest tests -q -p no:cacheprovider` em `backend/` aprovou 534 testes, pulou 66 e reportou um aviso Starlette. A migração `8f6a1c2d9e30` foi aplicada somente ao banco operacional local selecionado após backup privado; contagens Gold/operacionais permaneceram iguais e as contas artificiais foram provisionadas no arquivo local ignorado. No navegador com API real passaram login/cookie, permissões reader/operator, reload, logout, replay e credencial inválida. A revisão visual com capturas cobriu 1366×768, 1280×720 e 1440×900. Ver detalhes e limites no [plano de implementação](../plans/2026-10-29-backend-auth-login-grid360-plano.md) e no [Registro de progresso do PRD](../PRD.md). WEB-11 permanece pendente.
