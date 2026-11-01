# ADR-0012 — Identidade individual nas ordens e proxy sem credenciais

**Data:** 23/10/2026. **Estado:** princípio de segurança mantido; arquitetura atual de sessão registrada na [ADR-0020](0020-autenticacao-backend-por-sessao.md).

O proxy Vite não autentica clientes nem injeta credenciais. Portas de desenvolvimento são publicadas somente em localhost, e os modos de acesso explícitos permanecem separados: identidade individual no portal, credenciais privadas de serviço em CLI/Swagger e demo sintética local. O servidor determina identidade e permissão; nunca confia em campos de ator enviados no corpo. A demo não representa identidade individual nem pode ser usada com dados reais.

WEB-10 continua pendente até que login, autorização e a jornada integrada sejam testados e aceitos. Perfis por área/território, posse individual das ordens e trilha operacional completa não são definidos por esta decisão. Consulte o [contrato de sessão](../contracts/local-auth.md) e o [handoff de autenticação](../contracts/inspection-auth-handoff.md).
