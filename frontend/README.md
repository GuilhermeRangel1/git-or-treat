# Frontend — Grid360

SPA React + TypeScript + Vite, com Tailwind CSS e ícones Lucide. A sidebar, o Panorama e as jornadas disponíveis seguem o Figma nos temas claro/escuro, com navegação mobile. O Assistente já envia perguntas pelo Backend para o serviço GenAI usando o contrato v1; a demonstração usa evidências artificiais e não substitui integração com Gold.

A [arquitetura](../docs/architecture/frontend.md) define responsabilidades, dependências, tema, transporte HTTP e política de estado. A escolha está registrada na [ADR-0001](../docs/decisions/0001-arquitetura-frontend.md). O [PRD](../docs/PRD.md) governa os critérios funcionais.

### Sessão e perfis WEB-10

No modo autenticado, a resposta de sessão inclui perfil e permissões efetivas. O portal filtra a navegação, protege cada rota/ação e envia consultas autenticadas pelo proxy; o Backend continua validando toda autorização. 401 exige autenticação novamente; 403 preserva a sessão e mostra acesso negado. Perfil nulo recebe a mensagem de conta ainda não provisionada. A política canônica e o estado de validação estão na [ADR-0022](../docs/decisions/0022-perfis-de-acesso-web10.md), no [contrato de acesso](../docs/contracts/platform-access.md) e no [PRD](../docs/PRD.md#web-10--perfis-e-autorização).

## Executar

A partir de `frontend/`:

```sh
npm ci
npm run dev
```

O ambiente de CI usa Node.js 22; use uma versão compatível com os requisitos declarados pelo Vite instalado. O Docker de desenvolvimento está disponível em `Dockerfile.dev`.

O Panorama exige a API para exibir os indicadores; as demais páginas ainda estão no escopo visual. A rota de diagnóstico `/dev/contratos` existe somente durante o desenvolvimento e consulta `/api/v1/kpis` por meio do cliente HTTP compartilhado. Em desenvolvimento, sem `VITE_API_URL`, as consultas usam a origem do portal e o proxy `/api` do Vite, cujo destino padrão é `http://127.0.0.1:8000`. No Docker, `API_PROXY_TARGET=http://backend:8000` configura esse destino no servidor; `DEV_USE_POLLING=true` atualiza os arquivos do volume Windows. Para outro servidor, configure `VITE_API_URL`; em produção essa variável continua obrigatória (use `/` somente quando houver proxy no servidor publicado). Essa URL é pública; credenciais não pertencem a variáveis `VITE_*`.

Para testar o chat com os três serviços no Docker, configure os arquivos privados conforme [a integração Backend → GenAI](../backend/README.md#chat-do-portal-no-docker-compose), execute `docker compose up --build` na raiz e acesse `http://localhost:5173/assistente`. O navegador chama somente o Backend; não recebe a chave do Gemini.

## Verificar

```sh
npm run check:boundaries
npm run format:check
npm run lint
npm test
npm run build
```

`npm run format` aplica formatação e `npm run test:watch` acompanha os testes durante o desenvolvimento. As verificações também são executadas na CI.

### Finais de linha no Windows

O frontend usa LF: `.prettierrc.json` define `endOfLine: "lf"` e a regra `/frontend/** text=auto eol=lf` em `../.gitattributes` impede que um novo checkout converta esses arquivos para CRLF, mesmo com `core.autocrlf=true`. Não é necessário alterar a configuração global do Git. Arquivos binários continuam sujeitos à detecção automática do Git.

Se um checkout existente ainda contiver CRLF, execute `npm run format` e depois `npm run format:check`. Revise o diff antes de commitar; normalização de finais de linha não deve introduzir mudanças funcionais. Não use limpeza ou checkout forçado para isso quando houver trabalho local.

Verificado com Prettier 3.9.10, conforme o lockfile. Referências: [opção de finais de linha do Prettier](https://prettier.io/docs/options#end-of-line) e [atributos de texto e EOL do Git](https://git-scm.com/docs/gitattributes#_eol).

## Abrir a fila DEV-05 com dados sintéticos no Windows

Na raiz do repositório, com `backend/venv` preparado e dependências do frontend instaladas:

```powershell
.\scripts\start-inspection-demo.ps1
```

O comando inicia API em `8000` e frontend em `5173`, em segundo plano, e verifica o contrato da fila antes de informar sucesso. Abra **http://localhost:5173/inspecoes**. A fonte sintética e a URL da API são configuradas explicitamente nos processos, sem editar `.env`. Logs/PIDs ficam em `work/dev05-demo/`, ignorado pelo Git. A demo iniciada pelo script usa SQLite em memória e não mantém ordens persistentes. Reexecutar reconhece uma demo compatível já ativa, inclusive pelo Docker; se as portas pertencerem a outros serviços, o comando recusa substituí-los. É possível escolher `-BackendPort` e `-FrontendPort`.

No Docker Compose, o frontend usa `5173` e `VITE_API_URL=/`: o proxy do Vite encaminha `/api` para `http://backend:8000`. Os consumidores já incluem `/api/v1` no caminho; adicionar esse prefixo na variável duplica a rota e impede carregar os dados.

Na revisão DEV-05 de 22/10/2026, cabeçalho e conteúdo passaram a compartilhar largura fluida centralizada até 1920 px, como o Panorama da DEV-02, com espaçamento adaptativo. O ajuste foi aplicado aos componentes de layout, sem merge de branches.

## Abrir Ordens DEV-06 com persistência local

Na raiz do repositório, com o ambiente `backend/.venv` (ou `backend/venv`) e as dependências do frontend já instalados:

```powershell
.\scripts\start-orders-demo.ps1
```

Abra **http://localhost:5173/ordens**. Se as portas padrão já estiverem ocupadas, preserve a instância existente e use:

```powershell
.\scripts\start-orders-demo.ps1 -BackendPort 8010 -FrontendPort 5180
```

Nesse caso, abra **http://localhost:5180/ordens**. A execução seleciona demo sintética sem login, aplica as migrações e mantém ordens em `work/dev06-demo/orders.sqlite`. Recarregar a página ou reiniciar os serviços conserva os registros nesse arquivo. O script não altera `.env`; frontend e API escutam apenas em localhost, e o proxy encaminha as chamadas sem acrescentar credenciais. Logs e PIDs ficam em `work/dev06-demo/`.

Uma lista inicial vazia é esperada em um banco novo. Abra **Inspeções**, selecione uma suspeita e use **Criar ordem de inspeção**. Após a confirmação do servidor, abra **Acompanhar ordem** ou o menu **Ordens**. O script antigo de Inspeções usa banco em memória e não deve ser usado para conferir a persistência das ordens.

## Fundação visual inicial

Branch `feat/visual-frontend`, renomeada de `refactor/arquitetura-frontend`. A [referência Figma](https://www.figma.com/design/oTjmpIBgbA7OOYb9ZmMG9K?node-id=15-164) orienta a sidebar de 224 px e o cabeçalho do Panorama. O rodapé demonstrativo e a linha de dados sintéticos foram retirados conforme pedido. O Assistente é a exceção às páginas ainda visuais: tem envio de perguntas, respostas, estados de erro, evidências sintéticas e contexto transitório no contrato v1.

Os ícones usam Lucide; a logo é um asset local. A decoração do Panorama usa um único SVG no componente: desenha as linhas, transmite pulsos e repousa em cerca de 3,7 s; passar o mouse repete os pulsos. A preferência por movimento reduzido mantém o desenho estático. O tema é persistido quando o armazenamento permite. No mobile, o menu pode ser aberto, fechado com botão/Escape e usado para navegar. Há foco visível e atalho para o conteúdo.

Para conferir a fatia visual do produto: abra `/panorama` em 1440 × 1024 e 390 × 844, alterne os dois temas, navegue nas sete áreas e exercite o menu mobile. Para conferir o consumidor do contrato em desenvolvimento, abra `/dev/contratos`; essa tela é uma ferramenta de diagnóstico separada, sem item no menu e sem dados embutidos. A construção das jornadas de negócio, ordens e IA permanece pendente.
