# ADR-0013 — Composição da interface e carregamento das páginas

**Data:** 2026-10-23
**Estado:** aprovada pela solicitação de refatoração da pessoa usuária
**IDs do PRD afetados:** WEB-02, WEB-03, WEB-04, WEB-07, ENT-03 e ENT-04

## Contexto

Receita e Inspeções repetiam a estrutura e o controle dos diálogos e estilos de botões, exigindo correções visuais separadas. UC360Page concentrava busca, período, apresentação e coordenação. O registro de rotas importava todas as páginas diretamente, produzindo uma entrada JavaScript de 474,91 kB. A ADR-0001 já define features, recursos compartilhados e layout persistente.

## Opções consideradas

1. Manter implementações independentes e importar todas as páginas diretamente: menos mudanças imediatas, com repetição de comportamento e carregamento de páginas ainda não visitadas.
2. Extrair a UI concretamente repetida, dividir a apresentação da UC 360 e carregar páginas sob demanda dentro do layout: reduz repetição e tamanho de entrada, acrescentando uma fronteira assíncrona de navegação.

## Decisão

Adotar a opção 2 com os componentes existentes e recursos nativos, sem nova biblioteca. Button e Modal em shared/ui centralizam apresentação e ciclo dos diálogos; as features mantêm campos, rascunhos e regras de URL. UC360Page coordena rotas e consultas e compõe busca e detalhe, com período, métricas e interpretação próprios.

React.lazy é declarado no escopo de módulo para Receita, UC 360, Inspeções, Ordens, Operação e Assistente. Suspense fica dentro de AppLayout, preservando a estrutura global. Busca e detalhe da UC reutilizam a mesma entrada lazy. A pessoa usuária adiou a revisão do Panorama: sua implementação, arquivos atuais em shared e import estático são preservados. Essa exceção de organização será reavaliada na atividade futura da página.

## Consequências e verificação

- A primeira visita a uma rota pode exibir o estado de carregamento do módulo. Layout e tema permanecem montados; os estados das consultas continuam sob TanStack Query.
- O build final tem entrada JavaScript de 351,27 kB (109,63 kB gzip), ante 474,91 kB (138,21 kB gzip). A redução de artefato não é uma medida de latência.
- Suíte frontend: 131 testes em 16 arquivos aprovados. Lint, fronteiras em 91 arquivos, Prettier e build TypeScript/Vite passaram. Navegação e diálogos foram conferidos no navegador.
- Contratos e aceites Gold permanecem nos estados do PRD. Confira o [plano](../plans/2026-10-23-frontend-architecture-refactor.md) e as [evidências](../plans/2026-10-23-frontend-architecture-evidence.md).
- Referência consultada via Context7 em 23/10/2026: [React.lazy](https://react.dev/reference/react/lazy), aplicado ao React 19.2.8 do projeto. A estratégia poderá ser revista se a medição das jornadas indicar custo relevante na primeira navegação.
