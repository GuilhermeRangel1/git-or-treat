# Plano de implementação — Mapa interativo da RMR

> **Para execu??o por agentes:** usar superpowers:executing-plans para executar as tarefas abaixo. Delega??o somente se autorizada pela pessoa usu?ria. A nota original de planejamento foi supersedida pela autoriza??o expl?cita de implementa??o em 03/11/2026; a execu??o segue este plano.

**Data:** 03/11/2026. **Estado:** execu??o autorizada e em andamento; sem aceite funcional integral.

**Objetivo:** permitir localizar variações de faturamento e consumo na Região Metropolitana do Recife, selecionar um município e continuar a investigação em Receita com os filtros preservados.

**Arquitetura:** acrescentar a feature `mapa` ao layout persistente do portal, consumindo os contratos e endpoints de Receita existentes. Separar a malha geográfica pública dos indicadores privados da Gold v2. Reutilizar cálculos, transporte, autenticação, cache, componentes e tokens; não criar um segundo caminho de apuração financeira.

**Stack:** React 19, TypeScript, Vite, Tailwind, TanStack Query e Lucide já existentes; Leaflet 1.9.4 como referência inicial para o adaptador cartográfico, com versão e compatibilidade reconfirmadas na execução. Backend FastAPI/Pydantic e repositório analítico Gold v2 existentes. Não há migração de banco prevista.

**Especificação:** descrição do cartão aprovada nesta conversa, consolidada na seção seguinte; rastreabilidade em [PRD](../PRD.md), WEB-01/WEB-02/WEB-07 e autorização WEB-10. O adicional ainda não tem ID próprio: não reutilizar DEV-15, que identifica validação de jornadas. Registrar o identificador/link efetivo do cartão quando disponível, sem inventá-lo.

## 1. Escopo da primeira entrega

- Página `/mapa`, rótulo de navegação **Mapa da RMR**, com ícone `Map` de `lucide-react`.
- Entrada **imediatamente acima de Assistente**, na lista central de rotas, preservando essa ordem na sidebar expandida, recolhida e navegação mobile quando aplicáveis.
- Acesso inicial por `revenue:read`: Comercial e Admin, conforme a matriz vigente. O mapa não concede informações financeiras aos outros perfis.
- Municípios com contornos oficiais, zoom, seleção por clique e seleção equivalente em lista/tabela acessível.
- Filtros de competência inicial, competência final e classe; seleção de município e camada aplicadas na URL, preservadas em recarga e voltar/avançar.
- Camadas: faturamento observado no mês final, consumo medido no mês final, variação absoluta de faturamento e variação absoluta de consumo entre os meses inicial e final.
- Painel municipal: valores inicial/final, variações elegíveis, série mensal, bairros que contribuem para a variação do faturamento e botão **Investigar na Receita**.
- Legenda com unidade, limites de escala, per?odo e distin??o entre dado observado, zero, aus?ncia e cobertura insuficiente. Fontes t?cnicas, atribui??o, publica??o e evid?ncias ficam nos contratos/registros; a tela do mapa n?o exibe painel t?cnico de proveni?ncia.
- Claro/escuro, desktop/mobile, teclado, foco, contraste, movimento reduzido e alternativa textual aos dados geográficos.

**Fora do escopo:** localização individual de UCs, malhas de bairros, inspeções, DEC/FEC, comparação simultânea entre duas cidades, animação temporal, previsão, novas respostas de IA, dados em tempo real e alterações de grants. Os bairros aparecem no detalhamento tabular, sem prometer geometria ainda não verificada.

## 2. Padrões obrigatórios e referências

A execução e a revisão devem carregar e aplicar explicitamente:

1. [backend-coding-standards](../../.agents/skills/backend-coding-standards/SKILL.md), inclusive nos testes de integração, validação de contratos e eventuais ajustes da API. Ler [backend/AGENTS.md](../../backend/AGENTS.md) e [guia Backend](../services/backend.md). Router traduz HTTP; serviço mantém regras; repositório concentra acesso à fonte; nenhuma fórmula é transferida para o frontend.
2. [frontend-coding-standards](../../.agents/skills/frontend-coding-standards/SKILL.md), em toda a página, hooks, estilos e revisão visual. Ler [frontend/AGENTS.md](../../frontend/AGENTS.md), [arquitetura](../architecture/frontend.md), [guia Frontend](../services/frontend.md) e [referência visual existente](../design/grid360-prototype.md).
3. [vercel-react-best-practices](../../.agents/skills/vercel-react-best-practices/SKILL.md), aplicando apenas recomendações compatíveis com Vite: carregamento da feature sob demanda, ausência de consultas por município no carregamento inicial e atualização das camadas sem recriar o mapa inteiro.
4. [Política Gold v2](../agents/genai-gold.md#referência-obrigatória-gold-v2), [dicionário](../dicionario_gold.md), [contrato físico v2](../contracts/gold-csv-v2.md) e [acesso da plataforma](../contracts/platform-access.md). Não ampliar o escopo GenAI. Se surgir necessidade de escrever SQL ou mudar objetos PostgreSQL, carregar antes `supabase-postgres-best-practices`; isso não está previsto como requisito desta solução.

**Padronização visual é critério de aceite, não refinamento opcional.** A nova página deve parecer parte do mesmo sistema:

- Usar `AppLayout`, metadados de rota, `Navigation` e estrutura de cabeçalho existentes. Não recriar sidebar ou provedor de tema.
- Reutilizar shared/ui/Button, IconButton, Select, MonthYearField, MetricCard, Badge e ContentState onde suas interfaces atendam ? composi??o. DataProvenance n?o deve ser renderizado no Mapa; seus metadados permanecem na API e documenta??o. Seguir resumo de filtros/modal ?Ajustar filtros? do Panorama.
- Herdar `--font-sans` (**DM Sans**), `--font-title` (**Manrope**) e `--font-mono` (**IBM Plex Mono**) de `styles/tokens.css`, nos mesmos papéis e escalas das páginas atuais. Não adicionar fontes ou impor a fonte padrão do Leaflet nos controles, legendas ou tooltips.
- Preservar espaçamentos, bordas, raios, superfícies, tamanhos de ícones, pesos tipográficos, formatação numérica e estados de interação do portal. Usar tokens existentes; acrescentar tokens cartográficos mínimos para ambos os temas somente se as escalas exigirem, sem cores espalhadas pelo componente.
- CSS do mapa deve ser restrito ao contêiner da feature, inclusive z-index, tipografia, foco e controles Leaflet. Não alterar globalmente componentes de Receita para acomodar o mapa.
- Não importar arquivos internos de `features/receita` em `features/mapa`. Extrair para `shared` somente contratos/recursos com reutilização real e manter a compatibilidade de Receita.
- Não há frame específico aprovado para o mapa. Usar o sistema visual atual como referência; não declarar fidelidade a um frame inexistente nem modificar o Figma nesta fase.

## 3. Constatações técnicas que condicionam a entrega

1. `GET /api/v1/revenue` já entrega série, comparação, qualidade, cobertura, opções e agrupamento municipal/bairro, sob `revenue:read`. Reutilizar esse endpoint em vez de criar uma API geográfica para repetir cálculos existentes.
2. O caminho atual é `endpoints/revenue.py` → `build_revenue` → `build_gold_revenue` → `GoldAnalyticsRepository`, com contratos em `schemas/analytics.py`. A versão do envelope HTTP é independente da versão física Gold v2.
3. A comparação atual de Receita usa os **meses extremos** do intervalo; a série percorre as competências entre eles. As camadas de valores absolutos usam o mês final. Não apresentar esses valores como soma do intervalo nem introduzir outra regra de comparação silenciosamente.
4. `gold_revenue.py::quality` atualmente mantém `percent_change_eligible=False` e `billed_amount_change_percent=None` em Gold v2 por limitação de fechamento. O painel deve preservar a indisponibilidade e sua causa. A UI não pode calcular percentuais para contornar essa decisão. Percentuais continuam parte do aceite condicionado à elegibilidade da fonte; registrar como pendência se o cartão exigir um número indisponível. Percentual de consumo não tem campo público contratado e não entra nesta entrega.
5. `consumo_receita_bairro` permite recortes por competência/município/bairro/classe. Faturamento não significa arrecadação; consumo medido não significa energia faturada. Coordenadas de UCs não estão nas projeções analíticas documentadas.
6. O contrato usa nomes de município, sem assumir código IBGE presente na Gold. Uma correspondência explícita e verificada deve ligar os nomes aos códigos da malha. Não fazer associação aproximada em runtime.
7. Não presumir que todos os municípios do lote pertencem à RMR nem que a divisão metropolitana coincide com uma região imediata do IBGE. Verificar composição oficial, data de referência e cobertura do lote antes de construir o asset. Município territorial sem observações continua no mapa, marcado sem dados.

## 4. Estrutura prevista e interfaces

Os caminhos novos abaixo são propostas para a execução; os caminhos existentes foram conferidos no planejamento.

| Arquivo | Ação e responsabilidade |
| --- | --- |
| `docs/contracts/territory-map.md` | Criar contrato da experiência, camadas, meses extremos, geometria, cobertura, permissões e mapeamento Gold/IBGE. |
| `frontend/public/geography/rmr.geojson` | Criar malha pública simplificada, apenas contornos e identificadores oficiais. |
| `frontend/public/geography/rmr-metadata.json` | Criar proveniência: URLs, data/ano, códigos, atribuição e checksum da geometria. |
| `frontend/src/features/mapa/municipalities.ts` | Criar registro explícito de código IBGE, nome oficial e aliases Gold verificados. |
| `frontend/scripts/prepare-rmr-geography.mjs` | Criar preparação/validação reproduzível do asset oficial, sem indicadores privados. |
| `frontend/src/shared/analytics/revenueContract.ts` | Extrair o contrato/decoder já existente em Receita, sem mudança semântica. |
| `frontend/src/shared/analytics/revenueClient.ts` | Centralizar transporte `fetchRevenue(query, signal)` e tipos de consulta compartilhados. |
| `frontend/src/features/receita/contract.ts`, `useRevenue.ts`, `revenue-filters.ts` | Ajustar imports e manter reexports compatíveis quando necessário; preservar a jornada atual. |
| `frontend/src/features/mapa/contract.ts`, `map-state.ts`, `useTerritoryMap.ts` | Validar GeoJSON, definir URL e compor consultas/correspondência municipal. |
| `frontend/src/features/mapa/MapaPage.tsx`, `MapFilters.tsx` | Coordenar página e filtros, sem acumular código Leaflet ou cálculos de negócio. |
| `frontend/src/features/mapa/MunicipalityMap.tsx`, `map-scale.ts`, `map.css` | Encapsular ciclo de vida Leaflet, cores, seleção e estilos restritos. |
| `frontend/src/features/mapa/MapLegend.tsx`, `MunicipalityTable.tsx`, `MunicipalityPanel.tsx` | Exibir legenda, alternativa acessível e detalhamento municipal. |
| `frontend/src/app/routes.ts`, `router.test.tsx` | Inserir rota, ícone e ordem; verificar acesso e navegação. |
| `backend/tests/test_territory_map_revenue.py` | Criar testes do contrato HTTP existente que sustentará o mapa. |
| `frontend/src/features/mapa/*.test.ts(x)` | Criar testes de URL, correspondência, escala, seleção, estados e concorrência. |
| `docs/plans/2026-11-03-mapa-rmr-evidencias.md` | Criar apenas durante a execução, com resultados realmente observados. |

**Interface HTTP reutilizada:** `GET /api/v1/revenue?competencia_inicio=AAAA-MM&competencia_fim=AAAA-MM&group_by=municipio[&classe=...]` para a visão regional. Ao selecionar município, mesmo endpoint com `municipio=<nome Gold validado>&group_by=bairro` para série e detalhamento. Usar também o catálogo analítico existente para competências e classes; não fixar datas artificiais.

**Interface frontend proposta:** `MapLayer = 'revenue' | 'consumption' | 'revenue_change' | 'consumption_change'`; `MapQuery = { competencia_inicio: string; competencia_fim: string; classe: string; municipio: string; camada: MapLayer }`. `municipio` na URL é código IBGE; converter para o nome Gold apenas no cliente HTTP. Valor vazio representa nenhuma seleção. `parseMapSearchParams(params, defaults)` retorna `{ query: MapQuery | null; errors: string[] }`; `buildRevenueDestination(query, goldMunicipality)` gera URL de Receita com nomes de parâmetros aceitos pelo parser atual e `agrupar_por=bairro`.

**Interfaces de apresentação:** `MunicipalityMap` e `MunicipalityTable` recebem os mesmos itens por código IBGE, `selectedCode` e `onSelect(code)`. `MunicipalityPanel` recebe o envelope municipal validado e o destino para Receita; valores e deltas vêm da API. A escala só classifica valores finitos existentes, não calcula métricas.

## 5. Sequência de tarefas

### Tarefa 1 — Fechar o contrato de dados e a correspondência territorial

**Arquivos:** `docs/contracts/territory-map.md`, `municipalities.ts`, `prepare-rmr-geography.mjs`, assets geográficos e respectivos testes.

- [ ] Confirmar composição oficial da RMR, ano da malha, condições de uso e atribuição; registrar as fontes primárias e a diferença entre território oficial e cobertura do lote.
- [ ] Escrever casos controlados: código duplicado, geometria ausente, nome Gold sem correspondência, aliases conflitantes e município oficial sem dado. Duplicação/ambiguidade impedem associação; ausência analítica mantém o polígono com estado próprio.
- [ ] Executar os testes e observar falha antes da implementação do registro e validador.
- [ ] Implementar o registro explícito e a preparação GeoJSON. Preservar códigos como strings, validar Polygon/MultiPolygon, coordenadas e contornos com simplificação que mantenha a topologia. Não geocodificar consumidores.
- [ ] Publicar somente assets geográficos públicos e metadados; registrar checksum e atribuição. O browser carrega o asset local, sem depender da disponibilidade do IBGE a cada visita. Não usar tiles externos na primeira versão: os polígonos e rótulos são suficientes.
- [ ] Verificar o asset reproduzido e os testes. Registrar nomes não mapeados e impedir que desapareçam silenciosamente das conferências.

**Saída:** geometria identificável e correspondência auditável, sem dados privados versionados. Contrato explicita o bloqueio atual de percentuais.

### Tarefa 2 — Provar o contrato Backend que sustenta a página

**Arquivos:** `backend/tests/test_territory_map_revenue.py`; referências em `endpoints/revenue.py`, `services/revenue_analytics.py`, `services/gold_revenue.py`, `repositories/gold.py` e `schemas/analytics.py`.

- [ ] Aplicar `backend-coding-standards`. Criar testes de caracterização pelo endpoint público com fixture v2 controlada: dois municípios, duas classes, três meses e um bairro sem observação em um dos meses extremos.
- [ ] Asserções independentes: filtragem de classe, valores dos meses extremos, série dos três meses, deltas absolutos, nulidade por ausência e indisponibilidade de percentual. Exemplo artificial: faturamento 100 → 80 produz delta -20; consumo 10 → 7 produz delta -3; faturamento 0 → 20 mantém base zero distinta de ausência e não força percentual.
- [ ] Conferir 401 sem sessão, 403 para perfis sem `revenue:read`, acesso Comercial/Admin, 422 para período inválido ou parâmetro escalar repetido e comportamento vigente em troca de publicação. As negações devem ocorrer antes de acessar o repositório.
- [ ] Executar `python -m pytest -q tests/test_territory_map_revenue.py tests/test_revenue_dev03.py tests/test_platform_authorization.py`, a partir de `backend/`. Testes de caracterização podem passar desde o início; não alterar produção para fabricar uma etapa vermelha.
- [ ] Confirmar controles de publicação, nulidade e cobertura que o consumidor precisa. Se houver lacuna concreta, acrescentar primeiro o teste que falha e corrigir minimamente nas camadas existentes, mantendo compatibilidade e documentando o contrato. Não criar endpoint, tabela ou fórmula duplicados por conveniência.

**Saída:** comportamento atual documentado e testado para o mapa; limitações de fonte preservadas. Fixtures não constituem aceite Gold.

### Tarefa 3 — Compartilhar o cliente analítico e implementar URL/consultas

**Arquivos:** contrato/cliente compartilhados, imports de Receita, `map-state.ts`, `contract.ts`, `useTerritoryMap.ts` e testes correspondentes.

- [ ] Aplicar `frontend-coding-standards`. Cobrir parsing da URL: datas inválidas, ordem invertida, parâmetro repetido, camada desconhecida, classe inválida e município fora do registro. Entrada inválida mostra orientação e não dispara consulta com defaults silenciosos.
- [ ] Extrair tipos e decoder de Receita para `shared/analytics/revenueContract.ts`, e consulta HTTP para `revenueClient.ts`, preservando testes/exports usados pela feature atual. Não copiar o decoder nem permitir importação entre features.
- [ ] Implementar `parseMapSearchParams` e `buildRevenueDestination`. Defaults usam competências efetivamente publicadas; escolher as duas últimas quando disponíveis e permitir competência única, sem transformar mês ausente em zero.
- [ ] Compor cabe?alho, resumo/modal de filtros no padr?o do Panorama, mapa/lista e painel com componentes/tokens existentes. No desktop, mapa e painel lado a lado; no mobile, mapa seguido do painel, sem reduzir fontes nem gerar overflow horizontal. N?o mostrar Dados desta consulta, IDs brutos de publica??o, timestamps de importa??o nem parede de limita??es; manter unidades, per?odo e ressalvas pertinentes junto ?s m?tricas.
- [ ] Testar mudança rápida Olinda → Recife, troca de classe com detalhe aberto, logout e lote novo: nenhuma resposta atrasada pode substituir a seleção atual ou misturar publicações. No conflito de lote, invalidar resumo e detalhe conjuntamente e seguir a recuperação explícita do portal.
- [ ] Validar município/meses/classe retornados contra o pedido, não apenas o formato JSON. Falha de API não ativa fallback sintético. Geometria indisponível mantém lista analítica utilizável, com mensagem própria.
- [ ] Executar testes da nova feature, contratos compartilhados e Receita; comprovar recarga e histórico da URL.

**Saída:** dados validados e consistentes para mapa e detalhe, sem regressão em Receita.

### Tarefa 4 — Montar a página e a navegação com a identidade do portal

**Arquivos:** `routes.ts`, `router.test.tsx`, `MapaPage.tsx`, `MapFilters.tsx`, `MunicipalityTable.tsx`, `MunicipalityPanel.tsx` e testes.

- [ ] Testar a ordem `... Operação → Mapa da RMR → Assistente` para Admin e a posição imediatamente anterior ao Assistente entre os itens permitidos de Comercial; conferir ausência do mapa para os demais perfis e negação de acesso direto.
- [ ] Registrar `/mapa` como rota lazy com `requiredPermission: 'revenue:read'`, ícone Lucide `Map`, título e subtítulo nos metadados. Não inserir marcação independente em `Sidebar.tsx`.
- [ ] Compor cabe?alho, resumo/modal de filtros no padr?o do Panorama, mapa/lista e painel com componentes/tokens existentes. No desktop, mapa e painel lado a lado; no mobile, mapa seguido do painel, sem reduzir fontes nem gerar overflow horizontal. N?o mostrar Dados desta consulta, IDs brutos de publica??o, timestamps de importa??o nem parede de limita??es; manter unidades, per?odo e ressalvas pertinentes junto ?s m?tricas.
- [ ] Implementar tabela/lista com botões de seleção, indicação textual da seleção, unidades, indisponibilidade e acesso ao detalhe pelo teclado. Seleção pela tabela e pelo mapa atualiza o mesmo estado na URL.
- [ ] Exibir a série e os bairros reaproveitando primitivas compartilhadas existentes; se houver componente interno de Receita realmente adequado aos dois consumidores, extraí-lo com regressão em Receita em vez de copiá-lo ou importar entre features.
- [ ] No painel, faturamento/consumo usam meses extremos e série do período. Bairros sem comparação ficam explicitamente separados; contribuições conhecidas não são anunciadas como reconciliação integral quando há residual/ausência.
- [ ] Implementar **Investigar na Receita** com período, classe e nome municipal preservados. Testar o destino com o parser real de Receita, sem adicionar navegação de retorno complexa fora do escopo; o voltar do navegador deve restaurar o mapa.
- [ ] Verificar fontes calculadas e hierarquia visual contra Receita/Panorama, incluindo filtros, cards, séries e mensagens; registrar qualquer extração compartilhada necessária.

**Saída:** jornada acessível completa, usando a lista como alternativa funcional antes de depender do motor cartográfico.

### Tarefa 5 — Integrar o mapa, escalas e estados cartográficos

**Arquivos:** `MunicipalityMap.tsx`, `map-scale.ts`, `map.css`, `MapLegend.tsx`, dependência/lockfile e testes.

- [ ] Consultar documentação atual via Context7 e reconfirmar a versão estável/compatível do Leaflet e typings antes de instalar. Preferir integração direta isolada em componente React, sem wrapper adicional para esta camada pequena.
- [ ] Testar classificação: valor positivo, negativo, zero, todos iguais, todos ausentes, não finito, dado parcial e seleção sem observação. Zero conhecido não pode compartilhar o rótulo de ausência.
- [ ] Implementar escala sequencial para valores absolutos e divergente centrada em zero para deltas, com limites legíveis. A classificação usa todos os municípios elegíveis do recorte, não só o município selecionado; muda com os filtros e explicita os novos limites. Cobertura insuficiente recebe tratamento neutro/textual, sem sugerir comparação válida.
- [ ] Criar mapa e camada uma vez por montagem, ajustar cores e seleção sem reinstanciar o mapa, aplicar `fitBounds` inicial da RMR e permitir restaurar enquadramento. Encerrar listeners/instância na desmontagem e tratar redimensionamento do painel/viewport.
- [ ] Sincronizar seleção por clique e lista, borda de destaque, foco e controles de zoom. Não depender de hover ou cor para comunicar valores. Texto remoto é renderizado como texto seguro; não montar HTML de tooltip por interpolação de dados.
- [ ] Aplicar tokens e fontes do portal a controles/legenda/tooltip. Conferir stacking com filtros e menu mobile; respeitar movimento reduzido e gestos de rolagem no mobile.
- [ ] Testar no browser real montagem, mudança de tema/filtro/camada, saída/retorno à rota e resize. Testes com mock do Leaflet não substituem essa prova.

**Saída:** camada cartográfica integrada sem perda da alternativa acessível ou da identidade visual.

### Tarefa 6 — Reconciliar a jornada e registrar a entrega

**Arquivos:** testes necessários, relatório de evidências, PRD, contrato e guias afetados.

- [ ] Usar publicação Gold v2 autorizada e ambiente isolado; registrar schema, lote/fingerprint e cortes. Confirmar que a consulta do mapa está no caminho Gold, sem interceptação ou fallback demonstrativo.
- [ ] Conferir ao menos dois municípios, duas classes e dois meses comparáveis: valores Gold → banco → API → mapa/tabela → painel → Receita. Usar controle independente das funções que produzem a resposta. Registrar precisão de origem; moeda após formatação deve conferir a centavos, energia deve conferir à precisão publicada, sem tolerância arbitrária para encobrir divergência.
- [ ] Reconciliar municípios mapeados com o universo correspondente da RMR. Separar nomes não associados, municípios fora da RMR e valores desconhecidos; não usar o total geral da API como se fosse total regional. Não somar contagens mensais de UCs como unidades únicas do intervalo.
- [ ] Exercitar carregamento, erro/recuperação, ausência, cobertura parcial, valor inicial zero com delta absoluto válido, dado sem correspondência, troca de publicação, recarga, voltar/avançar e acesso negado. Verificar explicitamente as camadas de variação absoluta de faturamento e de consumo entre os meses extremos. Se o lote não contiver determinado caso, provar esse comportamento com fixture identificada, sem inventar amostra real.
- [ ] Conferir jornadas em 1440 px e 390 px, temas claro/escuro, teclado completo, foco visível, zoom, leitor/estrutura semântica da tabela, contraste e movimento reduzido. Capturar comparação visual com páginas atuais, incluindo fontes calculadas.
- [ ] Executar gates previstos abaixo, revisar critérios do cartão e registrar comandos/resultados/limites no relatório. Falha conserva o item aberto com causa e próximo passo.
- [ ] Na entrega funcional, atualizar o PRD no mesmo conjunto de mudanças, com entrada do adicional e evidência, sem concluir automaticamente WEB-01/02/07/10. Atualizar os guias que divergirem do comportamento entregue e sincronizar o cartão de rastreamento conforme as ferramentas e instruções aplicáveis, sem criar ou enviar mensagens externas nesta etapa de planejamento.
- [ ] Revisar a fatia segundo Backend/Frontend standards e critérios de negócio. Commits futuros devem seguir assunto/corpo em português e `Verificações:` com resultados reais, conforme AGENTS.md; nenhum commit/push está incluído nesta fase documental.

**Saída:** evidência reproduzível de integração e critérios revisados. Percentual indisponível por fonte permanece indisponível e explicitamente pendente se necessário ao aceite do cartão.

## 6. Comandos de verificação previstos para a execução

Estes comandos são instruções futuras, não resultados já obtidos:

```powershell
# Em backend/, com dependências e ambiente de teste existentes preparados
python -m pytest -q tests/test_territory_map_revenue.py tests/test_revenue_dev03.py tests/test_platform_authorization.py
python -m compileall -q app tests scripts

# Em frontend/
npm test -- src/features/mapa src/features/receita src/shared/analytics src/app/router.test.tsx
npm run lint
npm run check:boundaries
npm run format:check
npm run build

# Na raiz
git diff --check
```

Acrescentar testes PostgreSQL pertinentes se houver mudança de acesso ao banco, e os testes do script geográfico junto da tarefa 1. Antes da entrega funcional, executar as suítes completas dos serviços afetados conforme `.github/workflows/quality.yml`; registrar skips e dependências indisponíveis. A jornada real Gold e a revisão visual continuam necessárias mesmo com gates aprovados.

## 7. Foco de revisão e condições de aceite

| Risco/condição | Comportamento esperado | Tarefa que comprova |
| --- | --- | --- |
| Nome Gold divergente ou município sem geometria/dado | Sem associação aproximada, perda silenciosa ou zero artificial | 1, 3 e 6 |
| Percentual indisponível ou mês extremo ausente | Percentual indisponível conforme a fonte; delta absoluto indisponível quando faltar um extremo, sem fórmula alternativa no frontend | 2, 4 e 6 |
| Valor inicial zero e extremos disponíveis | Zero é valor observado válido para o delta absoluto de faturamento e consumo | 2, 4 e 6 |
| Troca rápida de seleção/filtro/lote | Resumo, cores e painel correspondem ao mesmo contexto autorizado | 3 e 6 |
| Usuário sem permissão abre URL diretamente | Rota e HTTP negam acesso, sem ampliar perfis | 2 e 4 |
| Estilo Leaflet, mobile ou uso sem mouse | Fontes/componentes padronizados, sem overflow e com lista equivalente | 4, 5 e 6 |

O adicional pode ser apresentado para aceite quando for possível identificar a variação no mapa, selecionar um município, ler fundamentos e continuar em Receita com contexto preservado, com números reconciliados e acesso controlado. Geometria pública, fixture ou screenshot isolados não encerram esse aceite. O escopo atual usa variações absolutas; o percentual indisponível na Gold v2 não é critério de aceite desta entrega.

## 8. Fontes técnicas consultadas no planejamento

- Código local e contratos indicados acima, consultados em 03/11/2026. A ordem da sidebar vem de `app/routes.ts`; o layout consome a navegação recebida.
- [Leaflet 1.9.4 — documentação oficial versionada](https://github.com/Leaflet/Leaflet/tree/v1.9.4), via Context7 `/leaflet/leaflet/v1.9.4`, consulta em 03/11/2026. Referência para GeoJSON, estilos e eventos; reconfirmar versão no início da implementação.
- [Exemplo oficial de mapa coroplético](https://leafletjs.com/examples/choropleth/): referência conceitual para polígonos coloridos, legenda e seleção; não copiar cegamente APIs de versões beta.
- [IBGE — API de malhas, documentação 3.0.0](https://servicodados.ibge.gov.br/api/docs/malhas?versao=3), consultada em 03/11/2026: geometrias simplificadas municipais em GeoJSON. A fonte oficial da composição metropolitana e o ano efetivo do asset devem ser registrados na tarefa 1; não foram presumidos neste plano.

## 9. Limite da fase de planejamento (hist?rico)

A instru??o original limitava a rodada de planejamento e exigia nova solicita??o antes da implementa??o. Foi supersedida pela autoriza??o expl?cita da pessoa usu?ria em 03/11/2026 para implementar na branch feat/mapa-rmr baseada em feat/web10-perfis (4ee933a). A execu??o atual segue as tarefas acima; esta altera??o n?o promove estados oficiais do PRD sem revis?o dos crit?rios/evid?ncias.

## Direção de apresentação aprovada durante a execução - 03/11/2026

A tela do Mapa segue o resumo de filtros e modal Ajustar filtros do Panorama. A pessoa usuária solicitou remover o painel visível Dados desta consulta, IDs brutos de publicação, timestamps e lista extensa de limitações, além da linha textual de variação percentual no painel municipal. Metadados técnicos permanecem na API/contratos; unidades, período e ressalvas pertinentes permanecem junto das métricas. Panorama não foi alterado. A captura pós-HMR foi realizada, sem promover estados oficiais do PRD.
