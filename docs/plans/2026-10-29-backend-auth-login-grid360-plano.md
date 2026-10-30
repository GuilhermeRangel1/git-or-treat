# Plano — autenticação backend e login Grid 360

Data: 29/10/2026. Estado: fatia de login/sessão implementada e revisada; WEB-10 permanece `Pendente`. Dependências: WEB-05, WEB-11 e banco operacional migrado. A decisão vigente é a [ADR-0020](../decisions/0020-autenticacao-backend-por-sessao.md), e os endpoints/cookie/provisão estão no [contrato local](../contracts/local-auth.md). A implementação desta fatia não conclui todos os critérios de WEB-10.

## Resultado esperado

O portal mostra `/login` para visitantes anônimos; o Backend valida credenciais e mantém a sessão em cookie HttpOnly. Leitor consulta ordens e operador consulta/altera. Reload restaura sessão pela API; logout revoga sessão e limpa dados em cache. O login reaproveita a arte, animação e direção visual do protótipo local em `D:/login-grid360`, sem adicionar os artefatos privados do protótipo ao repositório.

## Sequência e critérios de prova

1. **Backend e banco.** Migração operacional cria usuários/sessões. Endpoints de sessão/login/logout, hashing Argon2, expiração, revogação, CSRF e limites de tentativa seguem o contrato. CLI idempotente provisiona `reader`/`operator` com senhas aleatórias privadas. Provar testes HTTP e migração PostgreSQL descartável, incluindo usuário inativo, replay de cookie revogado, 401/429/403/503 e escrita recusada ao leitor.
2. **Portal.** Substituir o fluxo de identidade pelo contrato de sessão, adicionar página acessível `/login`, envio real de usuário/senha e feedback seguro. Usar `credentials: include`; não guardar senha ou token em storage. Logout, expiração e troca de identidade cancelam consultas e reiniciam caches Gold. Provar decoders, concorrência/limpeza de sessão, erros e permissões em testes frontend.
3. **Visual e integração.** Adaptar o protótipo ao tema/tokens do portal e verificar desktop, tablet, mobile, overflow, zoom e movimento reduzido. Com API real e banco descartável, provar login, reload, logout e permissões no navegador. Não usar ordens reais nem copiar dados do dataset.
4. **Operação e documentação.** Launcher Gold seleciona `ORDERS_AUTH_MODE=session`, migrações são aplicadas explicitamente pelo operador, provisionamento registra senhas apenas no arquivo local ignorado. Sincronizar README, guias, contrato, ADR e progresso WEB-10/WEB-11 após obter resultados reais.

## Estado atual

Fatia de login/sessão implementada e revisada; WEB-10 e WEB-11 permanecem `Pendente`. A revisão final desta entrega está registrada abaixo e no Registro de progresso do [PRD](../PRD.md). Os resultados identificam o que foi executado antes e depois dos últimos ajustes cosméticos.

## Evidências da implementação — 30/10/2026

### Backend e banco

- Em `backend/`, `python -m pytest tests -q -p no:cacheprovider`, contra o banco descartável `grid360_auth_fullsuite_test`: **534 passaram, 66 foram pulados, 1 aviso Starlette**.
- A migração `8f6a1c2d9e30` foi aplicada ao banco operacional local selecionado após backup privado em `work/local-auth/backups`. Contagens de tabelas Gold e operacionais antes/depois permaneceram iguais; reader e operator artificiais foram provisionados em `work/local-auth/credentials.txt`, ignorado pelo Git.

### Frontend e jornada visual

- Antes dos últimos ajustes cosméticos, a suíte completa aprovou **327 testes em 43 arquivos**. A matriz original de **22 combinações** também passou nessa etapa.
- Após remover controles, cópias e uma linha a pedido da pessoa usuária e compactar o layout para desktop de baixa altura, `npm run build` e `npm run format:check` passaram. A cena final mantém somente a composição animada, sem divisor inferior; nota e rodapé ficam abaixo do formulário em fluxo normal, sem sobreposição. Em navegador a 100% de zoom, `documentScrollHeight == innerHeight` nos três viewports: 1366×768, 1280×720 e 1440×900 (scrollHeight igual a 768, 720 e 900, respectivamente); não houve rolagem vertical.
- No navegador contra a API real, passaram login/cookie, permissões reader/operator, reload, logout, replay e credencial inválida. A suíte completa não foi repetida após os ajustes cosméticos; portanto, os resultados 327/43 e da matriz 22 descrevem a versão anterior a esses ajustes.

### Estado de aceite e pendências

- WEB-10 permanece `Pendente`: autenticação individual e a jornada de login foram verificadas, mas perfis e restrições de telas/ações por cargo em todo o escopo do requisito ainda não estão implementados.
- WEB-11 permanece `Pendente`; a suíte backend aprovada não conclui sozinha os critérios amplos do requisito.
- Nenhuma senha, DSN ou dado individual foi copiado para esta evidência.
