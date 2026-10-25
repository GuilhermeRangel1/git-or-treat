# Arquitetura e composição React

## Evoluir a estrutura atual

A [arquitetura](../../../../docs/architecture/frontend.md) e a [ADR-0001](../../../../docs/decisions/0001-arquitetura-frontend.md) definem a direção dos imports:

| Área | Responsabilidade e dependências |
| --- | --- |
| `app` | Compor rotas, provedores, layouts e entradas das features. |
| `layouts` | Manter sidebar/cabeçalho e estrutura persistentes; consumir `shared` e navegação recebida por props. |
| `features` | Conter páginas, regras de apresentação e integração de cada funcionalidade; consumir seus arquivos e `shared`. |
| `shared` | Oferecer recursos transversais sem importar features, layouts ou `app`. |
| `styles` | Definir entrada CSS e tokens comuns aos temas. |

Não importe componentes internos de uma feature em outra. Extraia uma interface compartilhada quando existir reutilização concreta. Prefira imports diretos e `import type` para dependências apenas de tipo; um arquivo agregador não deve esconder ciclos ou contornar as fronteiras verificadas pelo projeto.

As páginas entram no layout existente; não recriam sidebar, cabeçalho global, `QueryClient` ou provedor de tema. Use os metadados das rotas para título, contexto e layout em vez de condicionais espalhadas que reconhecem caminhos literais.

## Organização interna das features

Organize pela coesão e responsabilidade dos arquivos. A página principal pode permanecer na raiz da feature; agrupe componentes específicos em `components/` quando a quantidade ou a complexidade tornar a navegação mais clara. Crie `hooks/`, `api/`, `types/` ou `utils/` somente quando existirem responsabilidades e arquivos suficientes para justificar a separação. Features pequenas podem continuar com estrutura plana; não precisam reproduzir a árvore de uma funcionalidade maior nem conter diretórios vazios ou camadas artificiais.

Recursos exclusivos permanecem na feature. Mova para `shared/` somente recursos realmente transversais, preservando a direção dos imports acima.

Exemplo de evolução possível da [feature Receita](../../../../frontend/src/features/receita/):

```text
features/receita/
  ReceitaPage.tsx
  ReceitaPage.test.tsx
  contract.ts
  revenue-filters.ts
  useRevenue.ts
  components/
    RevenueSummary.tsx
    RevenueSeries.tsx
    RevenueSeries.test.tsx
    revenue-series.css
    RevenueBreakdown.tsx
    RevenueDecomposition.tsx
    RevenueFiltersForm.tsx
```

Esta árvore é uma recomendação ilustrativa, incluindo um possível teste específico da série; não descreve a estrutura atual nem exige reestruturar a DEV-03. Hoje esses componentes ficam na raiz de Receita. Uma extração futura deve melhorar a manutenção e preservar contratos e comportamento.

## Responsabilidades de componentes e hooks

Separe quando uma unidade misturar razões independentes para mudar: formulário, transporte HTTP, tabela, diálogo ou cálculo de apresentação. Tamanho é um indício; não imponha número universal de linhas nem extraia wrappers vazios.

Mantenha o estado perto de quem o usa. Extraia hook por comportamento reutilizável ou composição que mereça um nome; não transfira um componente inteiro para um hook que retorna dezenas de propriedades. Hooks de consulta e mutação separados favorecem reutilização, mas podem ser compostos por um controlador pequeno quando a jornada exigir.

Declare componentes como funções com props tipadas e contratos estreitos. Use chaves estáveis da identidade do item; índice de posição não serve quando linhas mudam de ordem, são inseridas ou contêm estado. Declare todos os hooks antes de retornos condicionais, no topo do componente/hook.

## React e dependências

Calcule valores derivados durante renderização. Use efeitos para sincronizar com sistemas externos, com cleanup e dependências corretos; eventos de usuário ficam nos handlers. Não trate `useEffect` como proibido nem instale uma biblioteca de hooks apenas para evitar um efeito simples.

Memoização responde a uma necessidade medida ou de identidade estável; não é ritual em cada função. Confira se React Compiler está realmente configurado antes de atribuir otimizações a ele. React 19 admite `ref` como prop; APIs antigas compatíveis não justificam refatoração em massa.

Reutilize `shared/ui`, Lucide e recursos nativos acessíveis. Shadcn, Base UI, Motion, bibliotecas de formulários ou novos pacotes de ícones não são requisitos deste projeto. Para uma dependência necessária, avalie acessibilidade, compatibilidade, licença, custo e manutenção dentro da tarefa autorizada.

Fontes: [regras dos hooks](https://react.dev/reference/rules/rules-of-hooks), [estado derivado e efeitos](https://react.dev/learn/you-might-not-need-an-effect) e [chaves de listas](https://react.dev/learn/rendering-lists#keeping-list-items-in-order-with-key).
