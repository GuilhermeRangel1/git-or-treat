# Acesso às ordens — contrato para o portal

O acesso autenticado usa sessões mantidas pelo Backend e cookie HttpOnly; não há credenciais de serviço injetadas pelo proxy. Rotas, envelope, permissões, proteção de origem, cookie, revogação e provisão estão no [contrato de autenticação local](local-auth.md). Decisão arquitetural: [ADR-0020](../decisions/0020-autenticacao-backend-por-sessao.md).

## Ordens e permissões

- `reader` recebe `orders:read`: consulta fila, ordens e histórico; não pode criar nem alterar ordens.
- `operator` recebe `orders:read` e `orders:write`: consulta e executa as ações operacionais permitidas pelo contrato DEV-06/DEV-07.
- A identidade/ator é resolvida pelo servidor a partir do usuário autenticado, nunca do corpo enviado pelo portal.
- `ORDERS_AUTH_MODE=service` continua disponível para CLI/Swagger com credenciais privadas. O portal não recebe nem armazena essas credenciais.
- `ORDERS_AUTH_MODE=demo` é limitado a desenvolvimento com fonte sintética e não identifica uma pessoa.

## Execução e aceite

Após aplicar explicitamente as migrações ao banco operacional local, execute `python scripts/bootstrap_local_auth.py` dentro de `backend/` para provisionar contas artificiais. As senhas iniciais são aleatórias e ficam apenas em `work/local-auth/credentials.txt`, ignorado pelo Git. Contas existentes não têm senha ou permissão redefinidas.

Em 30/10/2026, login por sessão, cookie, permissões reader/operator, reload, logout, replay e credencial inválida foram exercitados no navegador contra API real; também houve revisão visual nas resoluções registradas no [plano](../plans/2026-10-29-backend-auth-login-grid360-plano.md). A suíte completa passou antes dos últimos ajustes cosméticos, e build/formatação passaram depois deles. WEB-10 continua pendente porque perfis e restrições de telas/ações por cargo em todo o escopo ainda não estão implementados; WEB-11 também permanece pendente.
