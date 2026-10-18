# ADR-0001 — Frontend modular com layout persistente e fundações compartilhadas

**Data:** 2026-10-18
**Estado:** aprovada pela solicitação de ajuste arquitetural da pessoa usuária
**IDs do PRD afetados:** preparação para WEB-01 a WEB-07 e IA-01 a IA-06

## Contexto

O frontend possuía sete páginas contendo apenas o mesmo layout, CSS global antecipando funcionalidades sem componentes e um cliente HTTP genérico. O PRD exige preservar recortes, distinguir estados e exibir evidência dos dados. A pessoa usuária definiu React + Vite + Tailwind e Lucide e autorizou primeiro a arquitetura, com parada antes de implementar o visual das páginas.

## Opções consideradas

1. Manter páginas, serviços e componentes em agrupamentos técnicos globais: menor migração imediata, mas responsabilidade de domínio dispersa ao adicionar consultas e interações.
2. Organizar funcionalidades com fundações compartilhadas e composição central: migração pequena do scaffold e limites claros para manutenção e testes.
3. Adotar arquitetura com múltiplas aplicações ou uma camada extensa de entidades e serviços genéricos: custo desproporcional ao portal e aos contratos ainda em definição.

## Decisão

Adotar a opção 2: `app`, `layouts`, `features`, `shared` e `styles`, conforme o [guia arquitetural](../architecture/frontend.md). Rotas e navegação usam um único registro; o layout permanece montado com Outlet. React Router existente é mantido, Tailwind 4 prepara a estilização e Lucide permanece para ícones.

TanStack Query 5 prepara a responsabilidade por dados do servidor, com um cliente estável e sem consultas nesta entrega. Estado transitório permanece local; filtros aplicados terão representação em URL quando implementados. TypeScript estrito e testes comportamentais protegem as fronteiras.

A mudança é infraestrutura. As sete páginas continuam vazias; KPIs, gráficos, formulários de negócio e integração ficam fora da etapa.

## Consequências e verificação

- As dependências entre camadas passam a ter uma verificação automatizada.
- A equipe ganha um padrão para adicionar componentes e contratos por funcionalidade.
- Há dependências adicionais de cache, Tailwind e testes; as versões são fixadas no lockfile.
- CSS e tokens herdados continuam transitórios até a etapa de fidelidade visual.
- A configuração de API só é exigida quando há uma requisição fora do desenvolvimento.
- A decisão pode ser revista se os limites reais dos módulos ou a estratégia de consultas exigirem outra composição. Não altera fórmulas, endpoints, autorização ou regras operacionais.
- Evidências e pendências ficam no Registro de progresso do PRD; aprovação arquitetural não conclui requisitos funcionais.
