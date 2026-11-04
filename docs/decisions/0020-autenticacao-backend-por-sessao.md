# ADR-0020 — Autenticação individual por sessão do backend

**Data:** 29/10/2026. **Estado:** adotada; autenticação backend e jornada principal de sessão validadas em 30/10/2026. WEB-10 e WEB-11 continuam pendentes em seus escopos completos. **Requisitos relacionados:** WEB-05, WEB-10 e WEB-11.

## Contexto

O portal precisa identificar a pessoa operadora e autorizar leituras e escritas das ordens e o acesso integrado à Gold. O navegador não deve manter tokens de portador nem receber credenciais de serviço. A pessoa usuária determinou concentrar a autenticação individual no backend e oferecer uma página de login nativa do portal.

## Decisão

O Backend FastAPI autentica usuário e senha e mantém sessões opacas revogáveis no banco operacional, separadas do schema Gold. O cookie `grid360_session` é HttpOnly, SameSite=Lax, limitado a `/api/v1` e Secure em produção; apenas o hash SHA-256 do token fica persistido. As chamadas com cookie validam origem contra `BACKEND_CORS_ORIGINS`. As rotas `/api/v1/auth/session`, `/api/v1/auth/login` e `/api/v1/auth/logout` seguem o [contrato de autenticação local](../contracts/local-auth.md).

Os modos existentes permanecem distintos: `session` para identidade individual, `service` para CLI/Swagger com credenciais privadas e `demo` somente para fonte sintética em desenvolvimento. Produção exige `session`. Provisão é uma ação local explícita, sem cadastro público e sem senhas padrão compartilhadas. A API resolve usuário ativo, sessão e permissões em cada chamada; `reader` pode ler e `operator` pode ler e escrever ordens.

## Consequências e limites

Usuários/sessões exigem migração explícita do banco operacional e hashing de senha com biblioteca estabelecida. O launcher local realiza a provisão sem imprimir senhas em console/log e não aplica migrações. Testes backend e jornada no navegador passaram; evidências e limites estão no [contrato local](../contracts/local-auth.md) e no [Registro de progresso do PRD](../PRD.md). A sessão autenticada habilita identidade individual, mas não define posse de ordens nem perfis por área/território, que continuam pendentes em WEB-10. WEB-11 também não é concluído pela suíte observada.
