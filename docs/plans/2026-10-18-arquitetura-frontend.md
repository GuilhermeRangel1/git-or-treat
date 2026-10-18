# Plano de implementação — arquitetura do frontend

> Execução em etapas na sessão atual, com as skills locais de `.agents/skills`.

**Objetivo:** preparar a arquitetura do frontend e parar antes de reproduzir as páginas do protótipo.

**Arquitetura:** SPA React/TypeScript/Vite com módulos por funcionalidade, layout persistente, infraestrutura compartilhada de tema e HTTP e um provedor TanStack Query sem consultas de negócio. Tailwind prepara a estilização futura; Lucide permanece como biblioteca de ícones.

**Especificação:** solicitação de 18/10/2026 e avaliação arquitetural aprovada na conversa; PRD WEB-01 a WEB-07 e IA-01 a IA-06. A arquitetura efetiva será registrada em `docs/architecture/frontend.md` e ADR-0001.

## Limites

- Branch original `refactor/arquitetura-frontend`; execução deste plano restrita à primeira etapa. Após sua conclusão e novo pedido, a branch foi renomeada para `feat/visual-frontend`.
- Preservar as sete áreas e o conteúdo vazio das páginas; nenhuma consulta, KPI, gráfico ou fluxo operacional.
- A aparência existente é transitória. O alinhamento ao Figma pertence à etapa seguinte.
- Contratos de domínio e filtros serão definidos com backend/dicionário; não criar DTOs ou endpoints fictícios.
- Requisitos funcionais permanecem pendentes; não publicar ou mesclar a branch nesta etapa.

## Tarefas e verificações

- [x] **1. Fundação e ferramentas.** Configurar Tailwind/Vite, Vitest/Testing Library, TypeScript estrito, formatação e verificação de dependências entre camadas. Preservar os tokens existentes; CSS de layout permanece local e transitório.
- [x] **2. Transporte HTTP.** Testar antes de corrigir: erro textual preserva status; respostas vazias e JSON inválido são distintas; cancelamento é preservado; headers aceitam Headers e FormData; configuração de produção exige URL explícita. Implementar cliente em `shared/api/client.ts`, sem consumidores de negócio.
- [x] **3. Composição.** Mover páginas para `features`, tema para `shared/theme` e componentes de navegação para `layouts`. Criar registro único de rotas em `app/routes.ts`, `AppLayout` com Outlet e provedores estáveis. Testar navegação, persistência do layout/tema e ausência de acesso à API.
- [x] **4. Documentação.** Registrar estrutura, dependências permitidas, política de estado, migração e limites em guia arquitetural e ADR; sincronizar README, guia frontend e PRD.
- [x] **5. Fechamento.** Executar limites de importação, formatação, lint, testes, tipos/build e revisão final. Verificar as sete rotas em navegador. Parar ao concluir a arquitetura.

## Foco de revisão

- O layout deve permanecer montado ao trocar de área.
- A falha do armazenamento de preferências não pode impedir a aplicação de iniciar.
- Um erro HTTP com corpo não JSON mantém status e evidência técnica no cliente.
- Os provedores não iniciam consultas, retries ou mutações de negócio.
- O código compartilhado não depende de funcionalidades ou da composição da aplicação.

## Registro de execução

- Branch criada a partir de `main`, com árvore de trabalho inicialmente limpa.
- Estratégia: os contratos analíticos, hooks de filtros e componentes do Figma ficam documentados como trabalho futuro; esta etapa implementa somente infraestrutura utilizada ou necessária à composição.
- Conforme orientação posterior da pessoa usuária, o plano fica em `docs/plans/`, e as decisões e o guia em `docs/decisions/` e `docs/architecture/`.
- Instalação inicial encontrou falha interna no resolvedor de peers do npm 10. A resolução foi concluída com npm 11 temporário, sem alterar o npm do sistema; em seguida `npm ci` com npm 10 validou a instalação reproduzível pelo lockfile, com zero vulnerabilidades reportadas.
- Antes das correções, seis dos sete testes HTTP e o teste de armazenamento indisponível falharam pelos motivos previstos. Depois das correções, os dez testes passaram.
- Verificações aprovadas: fronteiras em 23 arquivos; teste negativo rejeitando import de `shared` para `features`; formatação; Oxlint; dez testes Vitest; TypeScript estrito e build Vite; links locais Markdown e whitespace do diff.
- Verificação em Chrome headless: sete áreas navegadas, sidebar preservada por identidade DOM, tema escuro mantido, páginas vazias, zero erros de execução e zero requisições ao backend. O roteiro e a captura ficam em `work/architecture/`, ignorado pelo Git.
- Revisão de escopo: nenhuma implementação de KPI, gráfico, consulta de negócio ou componente do protótipo foi acrescentada. Na conclusão deste plano, a etapa visual permanecia não iniciada. O pedido posterior iniciou somente a sidebar e o topo estático do Panorama, registrados no [guia arquitetural](../architecture/frontend.md); revisão humana da branch pendente.
