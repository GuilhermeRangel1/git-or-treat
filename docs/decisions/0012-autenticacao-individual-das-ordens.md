# ADR-0012 — Identidade individual nas ordens e proxy sem credenciais

**Data:** 2026-10-23

**Estado:** revisada por solicitação explícita da pessoa usuária: login não é obrigatório na DEV-06

## Revisão de escopo — 23/10/2026

A exigência de login na tela básica descrita originalmente abaixo foi retirada. A DEV-06 deve permitir criação e consulta locais sem login. O modo explícito `demo` concede leitura/escrita somente com `APP_ENV=development` e `ANALYTICS_SOURCE=synthetic`; configurações incompatíveis são recusadas. Compose e script de demonstração selecionam esse modo. O ator é `local-demo`, sem alegação de identidade individual. Portas continuam em localhost, sem injeção de tokens pelo proxy; o servidor recusa origens de navegador não permitidas e requisições cross-site. O modo não é adequado a publicação externa ou dados reais. Não há alteração na persistência, idempotência ou validações das ordens.

OIDC permanece disponível como preparação opcional para uma etapa futura. Sua integração não bloqueia a entrega do backend ou o trabalho da pessoa responsável pelo frontend. Esta revisão prevalece sobre os trechos históricos abaixo que exigiam 401 até integrar login.

**IDs do PRD afetados:** WEB-05 e preparação parcial de WEB-10

## Contexto e opções

O proxy Vite acrescentava a credencial de escrita quando havia `ORDERS_DEV_PROXY_TOKEN`. `Origin` ausente/forjado não autentica um cliente HTTP; um proxy alcançável poderia permitir operações anônimas. O Compose publicava as três portas sem restringir interface. A credencial compartilhada também não identificava a pessoa operadora.

Restringir somente `Origin` não resolve autenticação. Manter credenciais globais exigiria um BFF autenticado ainda inexistente. Criar cadastro e senha locais acrescentaria armazenamento de credenciais e políticas não definidas no produto. A pessoa usuária solicitou corrigir os três pontos e deixar o backend pronto para outra pessoa integrar o frontend.

## Decisão

Remover integralmente a injeção de credenciais do Vite; encaminhar somente o Bearer que o cliente apresentar. Publicar portas do Compose em `127.0.0.1` e usar o mesmo bind no Vite fora do contêiner.

O backend atua como resource server OIDC configurável: valida assinatura RS256, chave RSA >=2048, emissor, audiência, subject, emissão, expiração e scopes `orders:read`/`orders:write`. Escrita inclui leitura. A identidade decorre da assinatura validada, nunca de um campo enviado pelo usuário. O ator registrado é um identificador derivado de emissor/subject, sem token ou perfil pessoal.

`APP_ENV=production` exige `ORDERS_AUTH_MODE=oidc`; configurações incompletas/inseguras e tokens de serviço em paralelo são recusados. A autenticação de serviço existente fica restrita a desenvolvimento por CLI/Swagger. O nome `OrdersServiceToken` do esquema Bearer no OpenAPI é mantido por compatibilidade, com descrição atualizada para os dois modos.

As chaves são obtidas somente da URL HTTPS configurada no servidor, com cache e timeout; URLs do JWT não são fontes de confiança. `kid` desconhecido não força refresh para impedir buscas por requisição controladas por entrada não autenticada. A política de rotação precisa considerar o cache de cinco minutos. Tokens de duração maior que uma hora são recusados.

## Consequências e limites

`GET /inspections/access` retorna identidade opaca e permissões autenticadas com `Cache-Control: no-store`. O frontend precisa integrar login/renovação com o provedor da equipe e enviar o token de acesso individual. A tela básica deixa de criar ordens automaticamente e retorna 401 até essa integração; não se reintroduz o bypass para preservar uma demo antiga.

Não há novo cadastro/senha ou escolha de provedor comercial. Configurar issuer/audience/JWKS e HTTPS do ingresso continua responsabilidade de implantação. Não há regra de posse individual das ordens no PRD; a autorização é por ação sobre o conjunto operacional. Introspecção/revogação imediata, perfis das demais áreas e trilha durável completa ficam fora desta fatia. O trabalho de histórico da DEV-07 deve receber o ator individual quando integrado.

Sem migração SQL adicional. Nova dependência: PyJWT com suporte criptográfico 2.15.1, consultada via Context7; [documentação oficial](https://github.com/jpadilla/pyjwt/blob/2.15.1/docs/usage.rst). Testes usam assinaturas RSA reais e identidades artificiais, sem credenciais do time.

Contrato, configuração e casos de erro: [entrega de autenticação para o frontend](../contracts/inspection-auth-handoff.md). Esta decisão complementa a autenticação da ADR-0007 sem concluir WEB-10 ou a jornada completa de WEB-05.
