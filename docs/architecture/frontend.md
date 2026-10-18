# Arquitetura do frontend

**Estado:** fundação e primeira fatia visual implementadas em 18/10/2026 na branch `feat/visual-frontend` (renomeada de `refactor/arquitetura-frontend`).
**Decisão:** [ADR-0001](../decisions/0001-arquitetura-frontend.md).
**Escopo de produto:** [PRD §5.2 e WEB/IA](../PRD.md). Os requisitos funcionais continuam pendentes.

## Limite da entrega

A fundação arquitetural foi concluída antes da etapa visual. A primeira fatia visual autorizada reproduz a sidebar e o topo do Panorama nos temas claro/escuro, com navegação mobile. O conteúdo do Panorama termina antes dos filtros: título, subtítulo e decoração estática. A sidebar não inclui o rodapé demonstrativo; a linha de dados sintéticos e atualização ilustrativa também foi omitida.

As outras seis funcionalidades permanecem sem conteúdo de negócio. Não há filtros, KPIs, gráficos, dados mockados, consultas, formulários operacionais ou chat. A entrega prepara a interface; não conclui requisitos funcionais do PRD.

## Estrutura e direção das dependências

```text
frontend/src/
  app/                 composição: rotas, provedores e testes de navegação
  layouts/             estrutura persistente, cabeçalho e sidebar
  features/            panorama, receita, uc360, inspecoes, ordens, operacao, assistente
  shared/
    api/               transporte HTTP e fábrica do QueryClient
    theme/             contexto, provedor e hook de tema
    ui/                marca, botão de ícone e alternância de tema
  styles/              entrada global e tokens compartilhados com Tailwind
  test/                preparação dos testes de componentes
  main.tsx             ponto de entrada
```

- `app` compõe layouts, funcionalidades e recursos compartilhados.
- `layouts` depende de seus componentes e de `shared`; recebe os itens de navegação por propriedade.
- Uma `feature` depende de seus próprios arquivos e de `shared`. Componentes de outra funcionalidade são acessados somente após extrair uma interface compartilhada pertinente.
- `shared` não importa funcionalidades, layouts ou a composição da aplicação.
- `styles` é uma fundação comum. `scripts/check-boundaries.mjs` verifica imports estáticos e dinâmicos literais reconhecidos pelo analisador TypeScript, relativos ou via `@/`.
- `shared/ui` contém apenas os componentes visuais reutilizados pelo layout. `shared/filters` e `shared/analytics` continuam adiados até existirem componentes e contratos concretos.

## Composição, navegação e tema

`app/routes.ts` é o registro de caminhos, rótulos, metadados, ícones Lucide e componentes de entrada. `app/router.tsx` monta as rotas filhas em `AppLayout` com `Outlet`. A estrutura e seus estados locais permanecem montados ao navegar. Raiz e caminhos desconhecidos preservam o redirecionamento para Panorama.

As páginas não recriam sidebar, cabeçalho global ou provedores. O metadado `contentHeading` permite que Panorama forneça o próprio título e decoração sem acoplar o layout à funcionalidade. O menu mobile usa `dialog` nativo, fecha ao navegar ou passar para desktop e oferece fechamento por botão e Escape, com retorno de foco ao acionador. Os metadados do assistente referenciam IA-05, acesso ao agente no portal. Os demais estados do agente continuam trabalho futuro.

O tema usa `data-theme` no elemento raiz e preferência local quando disponível, com fallback para o sistema. Falha de leitura/gravação no armazenamento não impede iniciar nem alternar o tema. O modo é aplicado antes da pintura da atualização React. Nenhuma informação de negócio é persistida nesse mecanismo.

## Estilização

React + TypeScript + Vite, Tailwind CSS 4 com `@tailwindcss/vite` e Lucide React são a base adotada.

`styles/globals.css` importa Tailwind e tokens. `@theme inline` conecta variáveis existentes a utilitários semânticos como `bg-canvas`, `bg-surface`, `text-content`, `text-muted` e `border-border`. A variante `dark:` acompanha `data-theme`, mantendo o tema selecionado pela pessoa.

O CSS transitório de layout foi removido. Sidebar, cabeçalho e Panorama usam utilitários Tailwind e tokens semânticos; as fontes seguem o Figma: Manrope, DM Sans e IBM Plex Mono. O item ativo usa fundo neutro e barra goiaba. A sidebar desktop mede 224 px, seus itens têm 44 px e os controles de tema/menu têm 44 × 44 px; o menu mobile ocupa a tela e seus itens têm 48 px. O breakpoint do layout desktop é 1024 px.

Os ícones identificados no Figma são importados de `lucide-react`, sem arquivos SVG exportados para ícones. Os únicos assets locais novos são a marca original e os desenhos decorativos do Panorama, em versões clara/escura; ambos preservam dimensões do Figma. A decoração é oculta de tecnologias assistivas e não representa uma série de dados.

Referências consultadas via Figma MCP em 18/10/2026: [Panorama desktop claro](https://www.figma.com/design/oTjmpIBgbA7OOYb9ZmMG9K?node-id=15-164), [escuro](https://www.figma.com/design/oTjmpIBgbA7OOYb9ZmMG9K?node-id=16-1129), [mobile claro](https://www.figma.com/design/oTjmpIBgbA7OOYb9ZmMG9K?node-id=195-3781) e [menu mobile](https://www.figma.com/design/oTjmpIBgbA7OOYb9ZmMG9K?node-id=197-4744). A identidade original é a referência vigente.

## Estado: política para as próximas funcionalidades

| Estado | Responsabilidade |
| --- | --- |
| Filtros aplicados, período, comparação, paginação e ordenação | URL normalizada e validada pela funcionalidade; preservar somente parâmetros pertinentes ao navegar. |
| Dados recebidos, atualização e erro de consulta | TanStack Query; chaves incluem os parâmetros que alteram a resposta. |
| Formulário ainda não confirmado, menu e diálogo | Estado local do componente ou funcionalidade. |
| Tema | Provedor compartilhado e preferência local. |
| Mensagens e envio do assistente | Estado próprio do módulo, com retenção e contexto acordados com backend/IA. |

Além dos provedores de tema e cache, há controles locais de navegação e aparência. Ainda não há filtros, hooks de domínio, histórico de chat ou estado operacional. O QueryClient é estável por montagem dos provedores; retries automáticos de consultas e mutações ficam desativados por padrão. Cada funcionalidade deverá escolher atualização, expiração e tentativas com base em seu contrato. Nenhum provedor dispara requisições.

## Fronteira HTTP e contratos

`shared/api/client.ts` usa Fetch e aceita `RequestInit`, inclusive `AbortSignal`. Lê o corpo uma única vez, distingue erro HTTP, rede, configuração e JSON inválido e preserva cancelamentos. Resposta vazia retorna `undefined`; o consumidor deve tipá-la como `void`. Um corpo string é tratado como JSON quando o chamador não fornece `Content-Type`; FormData mantém seu cabeçalho automático.

`apiClient<T>` expressa o tipo esperado em compilação; não valida o conteúdo recebido em execução. Cada funcionalidade deverá acordar DTOs e validação/adaptação com o backend antes de consumir dados. Os envelopes já propostos em `backend/app/schemas/common.py` e os contratos sintéticos no [guia de IA](../services/ai-agent.md) são referências em revisão, não autorização para apresentar placeholders como dados reais.

`VITE_API_URL` é uma URL pública do backend: fallback local somente em desenvolvimento; uma requisição fora desse modo exige configuração explícita. Não é necessário configurar API para abrir esta interface visual. Variáveis `VITE_*` são públicas e não recebem credenciais. Nenhuma rota do backend é consultada nesta etapa.

As próximas integrações devem preservar unidade, período, filtros, atualização, qualidade e indisponibilidade. Ausência não vira zero. Fórmulas oficiais, segurança, transições e idempotência permanecem responsabilidades do backend/Gold. A interface deverá refletir confirmação do servidor e vincular o insight ao mesmo recorte aplicado, sem apresentar resposta antiga como interpretação nova.

## Qualidade e evidências

TypeScript estrito, Oxlint, Prettier, verificação de fronteiras e Vitest/Testing Library estão disponíveis em scripts do [package.json](../../frontend/package.json) e executados na CI.

Os testes atuais verificam a fronteira HTTP, cancelamento, configuração, navegação entre sete áreas, persistência da estrutura e do tema e falha do armazenamento. A primeira fatia visual também é conferida em Chrome headless nos dois temas, em desktop e mobile, incluindo ausência de requisições de negócio e comportamento do menu. Esses testes não exercitam Gold, jornadas de negócio ou acessibilidade completa. As dimensões principais são comparadas ao Figma; a reprodução se limita à fatia autorizada.

## Referências consultadas em 18/10/2026

- [Tailwind com Vite](https://tailwindcss.com/docs/installation/using-vite) e [tokens](https://tailwindcss.com/docs/theme), Tailwind 4.
- [Layouts React Router](https://reactrouter.com/start/declarative/routing), React Router 7.
- [QueryClientProvider](https://tanstack.com/query/latest/docs/framework/react/reference/QueryClientProvider), TanStack Query 5.
- [Vitest](https://vitest.dev/guide/), Vitest 4; [Testing Library](https://testing-library.com/docs/react-testing-library/intro/).
- Versões resolvidas e reproduzíveis: `frontend/package-lock.json`.
