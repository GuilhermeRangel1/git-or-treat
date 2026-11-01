# ADR-0022 — Perfis de acesso da plataforma

**Estado:** aprovada em 01/11/2026
**Requisito:** WEB-10

Adotamos um perfil único, persistido por conta, com permissões fixas calculadas pelo Backend e aplicadas novamente em cada requisição. Os cinco perfis são `commercial`, `customer_service`, `losses`, `operations` e `admin`; contas legadas ficam sem perfil e sem permissões de plataforma até atribuição operacional explícita, e o JSON de permissões legado não concede acesso em sessão. A matriz de rotas, ações e recursos Gold é mantida no [contrato de acesso da plataforma](../contracts/platform-access.md).

O Frontend usa as permissões retornadas na sessão para navegação e bloqueio de rotas, enquanto o Backend permanece autoridade para endpoints e ações. A conta admin acessa todas as telas e ações existentes e a união das capacidades GenAI implementadas, sem criar capacidade ou dado ausente. Atendimento e Perdas mantêm o Assistente acessível, mas recebem esclarecimento quando o domínio ainda não tem capacidade segura. Escolhemos papéis fixos em vez de edição dinâmica ou múltiplos cargos para limitar a superfície administrativa neste escopo; cadastro público e gestão de usuários pela interface ficam fora do WEB-10.
