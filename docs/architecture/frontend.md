# Arquitetura do frontend

**Estado atual:** sete jornadas de produto compostas em um layout persistente. Panorama, Receita, UC 360, Inspeções e Operação têm consultas demonstrativas integradas; Ordens consulta a persistência operacional e permite ações confirmadas pelo servidor; o Assistente integra o chat demonstrativo pelo Backend. Operação apresenta consolidado, ranking e investigação do alimentador conforme o escopo registrado no PRD. Receita, UC 360 e fila também oferecem integração Gold CSV provisória selecionada pelo backend; os aceites Gold continuam pendentes conforme o [PRD](../PRD.md). Esta descrição registra a arquitetura em execução, sem alterar escopo ou status de produto.

**Decisão estrutural:** [ADR-0001](../decisions/0001-arquitetura-frontend.md). Referências complementares: [ADR-0004 — contratos analíticos e fonte sintética](../decisions/0004-contratos-analiticos-e-fonte-sintetica.md), [ADR-0006 — Panorama](../decisions/0006-panorama-fonte-produto-e-contrato-dev01.md), [ADR-0008 — Receita](../decisions/0008-exploracao-demonstrativa-receita.md), [ADR-0009 — UC 360](../decisions/0009-uc360-contratos-de-consulta.md), [contrato de Inspeções DEV-05](../contracts/inspection-dev05.md) e [catálogo de contratos analíticos](../contracts/analytics-api.md).

## Estrutura e ownership

```text
frontend/src/
  app/                 rotas, provedores e entrada das features
  layouts/             sidebar, cabeçalho e composição persistente
  features/            panorama, receita, uc360, inspecoes, ordens, operacao,
                       assistente e diagnóstico dev-contracts
  shared/
    analytics/         contrato e hook do Panorama; extração adiada
    api/               transporte HTTP e configuração do QueryClient
    filters/           filtros do Panorama; extração adiada
    theme/             contexto, provedor e hook de tema
    ui/                Button, Modal e componentes visuais do Panorama
  styles/              entrada global e tokens semânticos
  test/                preparação dos testes
  main.tsx             ponto de entrada
```

- `app` conecta rotas, provedores, layouts e componentes de entrada das features. Não contém regras de domínio.
- `layouts` mantém a estrutura entre navegações e consome `shared` e a configuração de navegação recebida por props.
- Cada `feature` é dona de sua apresentação, estado de domínio e integração. Features não importam componentes internos umas das outras.
- `shared/api`, `shared/theme`, `Button` e `Modal` oferecem recursos usados entre áreas. `shared/analytics`, `shared/filters`, `MetricCard` e `ContentState` são atualmente usados pelo Panorama; sua reorganização para `features/panorama` foi adiada a pedido da pessoa usuária e é uma exceção temporária de ownership.
- `shared` não importa `app`, `layouts` ou `features`. A verificação de fronteiras valida imports estáticos e dinâmicos literais.

## Rotas e carregamento

A [ADR-0013](../decisions/0013-composicao-ui-e-carregamento-frontend.md) registra a evolução da composição e a exceção temporária do Panorama.

`app/routes.ts` define caminhos, rótulos, contexto visual, requisito e componente de entrada. `app/router.tsx` mantém `AppLayout` em torno das rotas e coloca o `Suspense` interno ao layout, para que a estrutura global permaneça montada durante a troca de conteúdo. A rota `/panorama` é carregada diretamente; as demais páginas de produto usam `React.lazy` por rota e são carregadas ao navegar. `/uc-360/:ucId` reutiliza a mesma entrada lazy da busca. `/dev/contratos` é carregada sob demanda apenas em desenvolvimento e não participa da navegação de produto.

## Componentes compartilhados e diálogos

`shared/ui/Button.tsx` reúne variantes comuns de controle/acento/ícone. `shared/ui/Modal.tsx` fornece estrutura nativa controlada (`dialog`), tamanhos médio/grande e cabeçalho inline/fixo; features continuam responsáveis pelo conteúdo e pelos rascunhos específicos. Receita e Inspeções usam o modal para filtros; o fundamento de Inspeções usa a mesma estrutura com conteúdo da própria feature. O menu mobile do layout também usa diálogo nativo.

`MetricCard`, `ContentState`, `shared/analytics` e `shared/filters` são usados pelo Panorama, embora ainda estejam em `shared`; a extração dessa ownership exclusiva foi adiada a pedido da pessoa usuária e fica registrada como exceção temporária. `Button` e `Modal` são usados entre áreas; cada feature mantém seu conteúdo e suas regras específicas.

## Estado e responsabilidade das features

| Estado                                                                 | Responsável                                                                        |
| ---------------------------------------------------------------------- | ---------------------------------------------------------------------------------- |
| Filtros aplicados, período, seção, paginação e ordenação serializáveis | URL normalizada e validada pela feature.                                           |
| Resposta da API, carregamento, atualização e erro                      | TanStack Query, com chaves que incluem o recorte e cancelamento por `AbortSignal`. |
| Rascunhos ainda não aplicados, diálogo, menu e expansões locais        | Componente ou feature que apresenta a interação.                                   |
| Tema                                                                   | Provedor compartilhado e preferência local.                                        |

Panorama, Receita e Inspeções mantêm seus filtros aplicados na URL; UC 360 mantém busca, período, seção e paginação na URL. Em UC 360, `UC360Page` coordena rota, consultas e transições de URL; `UC360SearchPanel` cuida do rascunho e dos resultados; `UC360Detail` compõe cabeçalho, contexto e histórico; `UC360PeriodForm` mantém rascunho de período local; `UC360Comparison` apresenta os quatro KPIs uma única vez, separados por grandeza física e financeira; `UC360SupportMetrics` apresenta geração própria e faturas em aberto; e `UC360Interpretation` apresenta fatos observados e limites. O coordenador encaminha alterações para `uc360-state` e a URL. Os hooks existentes em `useUC360.ts` preservam decoders e sinais de cancelamento.

O `QueryClient` é estável por montagem dos provedores e não dispara consultas por conta própria. Retry automático global fica desativado; cada consulta define sua atualização e expiração conforme contrato. Nenhum formulário duplica o estado aplicado: a confirmação move o valor do rascunho local para a URL.

## Fronteira HTTP e contratos

`shared/api/client.ts` centraliza Fetch, distingue falhas HTTP/rede/configuração/JSON e encaminha `RequestInit`, incluindo `AbortSignal`. A tipagem `apiClient<T>` não valida dados externos. Cada feature decodifica a resposta de `unknown` antes de apresentá-la e inclui no `queryKey` os parâmetros que alteram a resposta. O frontend consome a API FastAPI; não lê diretamente banco ou arquivos Gold.

`/dev/contratos`, descrita na [ADR-0004](../decisions/0004-contratos-analiticos-e-fonte-sintetica.md), exercita contrato e proveniência em desenvolvimento. Contratos demonstrativos em [analytics](../contracts/analytics-api.md), [Receita](../contracts/revenue-dev03.md), [UC 360](../contracts/uc360-dev04.md) e [Inspeções](../contracts/inspection-dev05.md) não comprovam reconciliação Gold.

Ausência não é zero; estados vazios, parciais, indisponíveis, erro e atualização têm apresentações distintas. A interface mostra unidade, período, origem e limitações do contrato em cada área aplicável. Respostas de IA e hipóteses não substituem evidência auditável.

## Tema, estilo e qualidade

A stack é React + TypeScript, Vite, Tailwind CSS 4 e Lucide React. `styles/globals.css` conecta tokens semânticos aos utilitários Tailwind. `data-theme` coordena os temas claro/escuro; falhas no armazenamento local não impedem iniciar ou alternar o tema. Páginas entram no layout compartilhado e não recriam sidebar, cabeçalho, QueryClient ou provedor.

Scripts do [frontend/package.json](../../frontend/package.json) oferecem Vitest/Testing Library, lint Oxlint, Prettier, verificação de fronteiras e build TypeScript/Vite. Esses gates validam implementação e estrutura, mas não substituem jornadas de produto, reconciliação com Gold nem critérios de aceite do PRD.

Para evidências específicas e histórico de validações, consulte os documentos existentes: [DEV-03](../plans/2026-10-21-dev03-evidence.md), [DEV-04](../plans/2026-10-22-dev04-evidence.md), [DEV-05](../plans/2026-10-22-dev05-evidence.md) e os registros de progresso do [PRD](../PRD.md).

## Operação: consolidado e investigação do alimentador

`features/operacao/contract.ts` valida os envelopes de summary 1.2.0 e ranking/detalhe 1.1.0 em execução, incluindo período, alimentador e paginação solicitados. `operations-state.ts` é responsável pela URL: o filtro `alimentador` pertence à lista; `feeder_id` identifica o detalhe aberto, sem apagar o filtro de origem. Os hooks de `useOperations.ts` usam o transporte compartilhado, chaves completas e cancelamento. Consultas de resumo, ranking e detalhe são independentes; respostas de outro recorte não são reaproveitadas como atuais.

`OperacaoPage` coordena a URL e compõe filtros, consolidado, ranking, detalhe, séries e fundamentos. Os componentes específicos permanecem na feature; `Button`, `Modal`, layout e temas continuam compartilhados. As fórmulas e os valores vêm da API; o frontend apenas apresenta, formata e dimensiona as barras. A regra do consolidado parcial está na [ADR-0015](../decisions/0015-consolidado-demonstrativo-de-continuidade.md). Referência visual: layer 06 do Figma, com séries mensais e filtros suportados pelo [contrato DEV-08](../contracts/operations-dev08.md).

## Assistente: conversa demonstrativa

Os títulos e subtítulos de Receita, UC 360, Inspeções, Ordens, Operação e Assistente seguem os frames originais do Figma nos dois temas. Os rótulos superiores de UC 360 e Inspeções são Atendimento e Perdas; os nomes da navegação permanecem os mesmos. O Assistente usa um painel central de até 960 px, com superfície, borda e raio de 20 px. `title` e `section` nos metadados de rota distinguem título de página, contexto superior e rótulo do menu. O metadado `layout: "conversation"` seleciona as medidas próprias do Assistente: área desktop com margens de 32 px e cabeçalho de 48 px; painel 960 × 800 px em x=352/y=104 no viewport 1440 × 1024. No mobile 390 × 844, o painel mede 358 × 752 px em x=16/y=76. A altura de 800 px é um teto no desktop: o painel encolhe em janelas menores. A rota usa a altura dinâmica da janela (`100dvh`), cabeçalho sem encolhimento e conteúdo flexível com `min-height: 0`; somente o histórico tem rolagem. O compositor fica fixo no rodapé do painel. Em janelas com altura de até 480 px, o cabeçalho interno do Assistente reduz o espaço reservado para preservar área de conversa. As outras rotas mantêm rolagem normal de página.

Além dos provedores de tema e cache, há controles locais de navegação e aparência. O chat mantém mensagens e contexto em estado React enquanto a página está aberta; não usa `localStorage`, sessão persistida ou histórico compartilhado. O QueryClient é estável por montagem dos provedores; retries automáticos de consultas e mutações ficam desativados por padrão. O chat oferece repetição manual somente quando o erro HTTP validado indica `retryable=true`.

O chat chama `POST /api/v1/ai/questions` pelo transporte compartilhado, valida o envelope v1 em execução e apresenta estado, evidências, marcação de demonstração, recorte e limitações. Contexto não confiável contém somente até três turnos anteriores e serve à continuidade linguística; não é identidade ou autorização. Erros de protocolo e rede são separados dos estados de negócio, e a UI não tenta novamente automaticamente. As chamadas passam pelo Backend; a chave Gemini permanece no serviço GenAI. Nesta versão, os valores são artificiais e não há Gold. As demais integrações devem preservar unidade, período, filtros, atualização, qualidade e indisponibilidade. Ausência não vira zero. Fórmulas oficiais, segurança, transições e idempotência permanecem responsabilidades do Backend/Gold.

O chat não persiste histórico e sua limpeza remove o conteúdo da memória da tela. A aplicação não interpreta Markdown/HTML do modelo: respostas são renderizadas como texto. A apresentação de evidência é derivada exclusivamente do envelope validado pelo serviço; não cria valores ou gráficos no cliente.


## Integração provisória Gold v1 — 27/10/2026

Receita, UC 360 e fila de inspeção têm composição executável com `ANALYTICS_SOURCE=gold`, consultas SQL parametrizadas, agregação/paginação no banco e catálogo de filtros real. O portal preserva rotas e valida envelopes; apresenta lote, importação local, limitações e ausências. `priority_label` preserva a categoria textual; score e estimativa são nulos. Histórico mensal da UC distingue agregado financeiro de fatura individual. Modo sintético permanece explícito e não solicita banco. Panorama/Operação e GenAI não foram homologados para essa fonte; os requisitos continuam abertos. Veja [contrato e execução local](../contracts/gold-csv-v1.md#consumo-provisório-pela-api-e-pelo-portal).
