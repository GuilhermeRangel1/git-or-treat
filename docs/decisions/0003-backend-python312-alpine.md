# ADR-0003 — Python 3.12 com Docker Hardened Alpine no backend

**Data:** 2026-10-20
**Estado:** aprovada pela pessoa usuária na solicitação de troca para a base DHI
**IDs do PRD afetados:** preparação de WEB-05 e WEB-11; segurança na seção 9.2

## Contexto

As bases `python:3.12-slim` e `python:3.14-slim` apresentaram CVE-2026-85091 na zlib. As tags oficiais `python:3.12.15-alpine3.23` e `python:3.12.15-alpine3.24` também continham uma revisão afetada. Atualizar o pacote durante o build corrigiu a imagem derivada, mas manteve o alerta do editor sobre o `FROM`. A pessoa usuária definiu manter Python 3.12 e usar uma base oficial que já contenha a correção.

## Opções consideradas

1. Aguardar atualização das tags `python:*` consultadas: mantém a dependência da publicação de uma nova base.
2. Atualizar zlib com `RUN apk add`: corrigiu a imagem derivada nos testes, mas não atende à preferência por base já corrigida.
3. Usar `dhi.io/python:3.12-alpine3.24-dev`, mantida pela Docker Hardened Images: contém Python 3.12.15 e zlib `1.3.2-r1` na base verificada em Linux amd64.

## Decisão

Adotar `dhi.io/python:3.12-alpine3.24-dev` e remover a atualização corretiva da zlib do Dockerfile. Preservar `requirements.txt`, contratos HTTP, comando de inicialização e PostgreSQL. A variante `-dev` inclui shell, pip e ferramentas necessárias ao fluxo atual de instalação e testes do projeto. Não criar nem publicar base própria.

O CI constrói a imagem e executa `pip check` e a suíte dentro dela com PostgreSQL descartável, além dos testes no runner Ubuntu. O scanner de segurança permanece manual.

## Consequências e verificação

A base foi baixada e inspecionada diretamente: Python 3.12.15, zlib `1.3.2-r1`. Docker Scout na base Linux amd64 `de73484b502d` apresentou zero alertas em todas as severidades, considerando as informações e atestações disponíveis na consulta. O índice da base resolvido no build foi `sha256:f8eae95f3e1ccbf21845db72c21f1f4fc0a57cd410e731a1b2a6626f834f814c`.

A [documentação de uso DHI](https://docs.docker.com/dhi/how-to/use/) exige autenticação em `dhi.io`; um pull local com configuração sem credenciais funcionou nesta verificação. O workflow aceita os secrets `DHI_USERNAME` e `DHI_TOKEN` e faz login se ambos estiverem configurados. Confirmar o acesso no GitHub Actions; não versionar credenciais. A [orientação específica de Python](https://hub.docker.com/hardened-images/catalog/dhi/python/guides) descreve as diferenças entre variantes de desenvolvimento e runtime.

Os resultados da imagem do backend, comandos e pendências ficam no Registro de progresso do PRD. Revalidar base e imagem final ao atualizar tags ou dependências. Outras arquiteturas e a execução remota dos novos passos no GitHub não foram comprovadas nesta entrega. Nenhum resultado de scanner garante ausência futura de vulnerabilidades ou conclui WEB-05/WEB-11; métricas Gold e critérios funcionais continuam pendentes.
