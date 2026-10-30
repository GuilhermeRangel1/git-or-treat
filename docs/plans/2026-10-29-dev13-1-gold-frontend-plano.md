# DEV-13.1 — plano de integração Gold no frontend

Data: 29/10/2026. Estado: aprovado; etapas 2–4 implementadas e revisadas, etapas 1 e 5 parciais por acesso OIDC e validação no navegador. Base: commit `a118766`, camada API publicada na branch `dev13.1`. Este documento registra o plano; execução e limites ficam nas [evidências frontend](2026-10-29-dev13-1-gold-frontend-evidencias.md).

## Objetivo e fronteira

Conectar Panorama, Ordens e Operação aos contratos reais da API, preservando significado, ausência de dados e identidade da publicação. Ordens continua sendo persistência operacional: sua relação com a Gold ocorre na criação da OS e nos fundamentos congelados, não pela substituição da lista operacional por uma tabela analítica.

Requisitos relacionados: WEB-01 a WEB-07, especialmente WEB-01/07 no Panorama, WEB-04/05 na criação e ciclo das ordens e WEB-06/07 em Operação; integração DE-04/05/06/08. Dependências: DEV-02 a DEV-08 e DEV-12, contrato API Gold entregue e banco já carregado. Receita e UC 360 não entram nesta implementação; seus vínculos não podem sugerir disponibilidade Gold inexistente.

Fontes: [PRD](../PRD.md), [dicionário](../dicionario_gold.md), [contrato Gold v2](../contracts/analytics-gold-dev13-1.md), [ADR-0018](../decisions/0018-api-gold-dev13-1.md), [arquitetura frontend](../architecture/frontend.md), [guia frontend](../services/frontend.md), [guia backend](../services/backend.md) e [evidências da API](2026-10-28-dev13-1-gold-api-evidencias.md). Aplicadas as skills backend-coding-standards e frontend-coding-standards; organização orientada por writing-plans. As versões usadas pelo projeto estão em `frontend/package.json`; não se propõe atualização de bibliotecas.

## Diagnóstico do código atual

| Área | Situação observada | Trabalho necessário |
| --- | --- | --- |
| Panorama | `shared/analytics/usePanoramaData.ts` e `panoramaContract.ts` consomem o contrato demonstrativo; cartões, gráfico, filtros e insight seguem esse modelo. | Decodificar v2 e representar números nulos, comparação parcial, opções reais e origem Gold. |
| Ordens | `shared/api/orders.ts` consulta a persistência operacional. `features/ordens/order-actions.ts` reconhece snapshots legados/v1, mas considera v2 não suportado. | Interpretar fundamentos v2 sem perder compatibilidade histórica ou exigir UC na Gold atual. |
| Criação de OS | Fluxo está em `features/inspecoes/CreateOrder.tsx`, fila/detalhe e `shared/api/orders.ts`; payload tipado ainda não inclui fingerprint. | Adaptar essa entrada necessária da jornada de Ordens ao contrato Gold. |
| Operação | `features/operacao/useOperations.ts` fixa contratos 1.2.0/1.1.0 e envia `page/page_size` ao detalhe. | Contrato v2, base por indicador e detalhe agregado; paginação de ocorrências retorna 422 na Gold. |
| Acesso | `shared/api/client.ts` usa Fetch; Vite apenas encaminha `/api`. Não há autenticação Gold automaticamente fornecida por esse proxy. | Resolver acesso de leitura/escrita antes da ativação; demo é restrito à fonte sintética. |

## Abordagem proposta

Evoluir as features existentes com decoders explícitos por versão/origem e pequenos modelos de apresentação. Reutilizar transporte, TanStack Query, URL, Modal, Button e tokens atuais. Não converter v2 para um DTO sintético que obrigue preencher lacunas. Manter compatibilidade sintética verificável; nunca recorrer à fonte sintética após falha Gold.

Uma troca apenas de URL/configuração não basta, pois as semânticas e nulabilidades mudaram. Uma segunda aplicação ou duplicação integral das páginas aumentaria manutenção sem resolver consistência. A recomendação é adaptar a fronteira de dados e apenas os componentes afetados, preservando a composição existente e a exceção de ownership do Panorama.

### Decisão de acesso anterior à ativação

Proposta: reutilizar OIDC individual e scopes de leitura/escrita já previstos no backend, com credencial de usuário em memória e envio Bearer pelo transporte. A existência do backend OIDC não demonstra que login/sessão frontend estejam implementados: essa etapa exige verificar o provedor disponível e o fluxo autorizado. Ausência de provedor/configuração bloqueia a ativação Gold no navegador, mas permite desenvolver decoders e componentes com fixtures artificiais.

Credenciais de serviço não entram em `VITE_*`, bundle, URL, fixtures ou armazenamento persistente do navegador. Não introduzir injeção de token de serviço pelo proxy: isso contrariaria a ADR-0012 e exigiria decisão explícita separada. Sessão/BFF seria alternativa arquitetural a discutir apenas se OIDC direto não servir ao ambiente. Confirmar o fluxo de acesso com a pessoa responsável antes de implementá-lo; esse ponto não é uma aprovação implícita de infraestrutura nova.

## Etapas de execução futura

### 1 — Contratos, acesso e identidade comum

- [x] Conferir OpenAPI e schemas atuais contra v2, sem alterar backend apenas para reproduzir valores demonstrativos.
- [x] Criar `frontend/src/shared/analytics/goldContract.ts` para metadados comuns realmente usados pelas três jornadas e testes correspondentes. DTOs de cada domínio permanecem na respectiva feature/ownership atual. Decodificar `unknown`, versão, fonte, lote, fingerprint, esquema, temporalidade e limites; não aceitar contrato desconhecido silenciosamente.
- [ ] Integrar acesso conforme a decisão acima em `shared/api/client.ts` e no módulo de sessão definido após verificar a infraestrutura existente. Distinguir 401, 403, 409, 422 e 503 sem expor detalhes internos. Atualizar os testes de transporte/proxy quando afetados.
- [x] Definir contexto de publicação compartilhado no nível da aplicação: a primeira leitura Gold estabelece lote/fingerprint; chamadas dependentes enviam `expected_lote/expected_fingerprint`. Leituras paralelas iniciais só podem compor uma vista após concordância das identidades.
- [x] Incluir origem, versão do contrato, identidade da publicação e parâmetros normalizados nas chaves das consultas Gold, além de encaminhar AbortSignal. Na troca de publicação, cancelar/inutilizar respostas antigas, limpar seleções incompatíveis e invalidar o grupo Gold. HTTP 409 oferece atualização coordenada; evitar retry infinito ou mistura de cards novos com detalhe antigo.
- [x] Manter caches operacionais de ordens independentes da publicação analítica. Não enviar identidade Gold em consultas históricas de ordens nem apagar resultados de escrita por causa de uma recarga.

Provas: decoder rejeita versão inválida; publicações diferentes não se combinam; mudança de filtros descarta resposta atrasada; leitura sem permissão não exibe dados residuais. Sem dependências novas por padrão.

### 2 — Panorama

Arquivos: `shared/analytics/{types,panoramaContract,usePanoramaData}.ts`, filtros atuais em `shared/filters`, `features/panorama/{PanoramaPage,PanoramaMetricCard,PanoramaSeriesChart,PanoramaFoundations,PanoramaStatus,AIInsightCard,usePanoramaInsight}` e respectivos testes.

- [x] Adaptar tipos/decoder v2, incluindo `statusComparacao`, limitações, opções reais e valores nulos. Receber cálculos do servidor; não recalcular preço, percentual ou DEC/FEC no navegador.
- [x] Remover opções/período padrão fixados na demonstração para Gold; usar `opcoesFiltros` e competência mais recente observada, sem chamá-la de mês fechado. Normalizar filtros aplicados na URL e tratar links antigos inválidos explicitamente.
- [x] Mostrar receita faturada e consumo medido com o universo elegível; nomear preço observado sem alegar tarifa. UCs faturadas no mês são distintas de atividade histórica.
- [x] Mostrar receita paga, energia faturada independente e UCs ativas históricas como indisponíveis, com motivo. Zero permanece zero; nulo não vira zero. Comparações observadas parciais mantêm aviso visível, inclusive com números presentes.
- [x] Gráfico preserva lacunas e alternativa textual. Filtro de classe mantém financeiro e sinaliza continuidade indisponível. Fundamentos exibem definição, unidade, recorte, atualização e publicação recebidos.
- [x] Em Gold, impedir requisição/uso do insight sintético e mostrar indisponibilidade contextual. Adaptar IA Gold requer tarefa própria; não concluir IA-04 nesta fatia.

Provas: valores reconciliados por município/classe; referência ausente/base zero; 1% calculado no servidor apesar do preço exibido arredondado; série com nulos; erro de acesso; mudança rápida de filtros; nenhum insight antigo associado a recorte novo.

### 3 — Ordens e entrada pela fila

Arquivos: `shared/api/orders.ts`, `features/ordens/{order-actions,OrderFoundationsDialog,OrdensPage,OrderActionsDialog,OrderHistory}`, `features/inspecoes/{contract,useInspectionQueue,queue-query,InspectionQueue,SuspicionDetail,InspectionFoundations,ConsumptionComparison,CreateOrder}` e testes relacionados. A adaptação da fila é dependência funcional da criação de OS; não amplia o escopo para Receita ou UC 360.

- [x] Implementar leitura tipada de snapshots v2 preservando legado/v1; versão desconhecida mantém mensagem segura e não bloqueia lista/ciclo/histórico. Mostrar origem congelada, regra e limites sem buscar a evidência atual para substituir a histórica.
- [x] Adaptar fila/detalhe ao snapshot Gold: categoria original, motivos/evidências e janelas P1/P2 exportadas. Retirar controles de score/recuperação e competência não suportados. Ordenar por UC/categoria com direção suportada, sem chamar ordenação textual de prioridade de despacho. Resetar página após mudar filtros.
- [x] Exibir recuperação indisponível com motivo; não transformar diferença de consumo em estimativa. Distinguir categoria de triagem da prioridade operacional BAIXA/MEDIA/ALTA.
- [x] Enviar `source_version`, `source_fingerprint` e `rule_version` do detalhe confirmado na nova intenção Gold. Preservar chave de idempotência/payload para replay da mesma intenção, inclusive após resposta perdida. Em conflito de publicação, atualizar evidência e exigir nova confirmação antes de gerar nova intenção; não recriar automaticamente.
- [x] Preservar criação única, controle de versão, permissões, cancelamento, conclusão e histórico. Atualizar/inutilizar caches operacionais após confirmação; navegação para ordens antigas funciona com UC removida da Gold.
- [x] Tratar vínculos para UC 360/Receita indisponíveis no modo Gold sem apresentar dados demonstrativos como fundamentos reais.

Provas: criar OS por fila Gold; clique/replay não duplica; snapshot v2 interpretado; v1/legado legíveis; conflito de lote; conflito de versão da OS; somente leitura sem ação de escrita; histórico preservado após cargas nova/repetida/inválida e retirada da UC.

### 4 — Operação

Arquivos: `features/operacao/{contract,useOperations,operations-state,OperacaoPage,OperationSummary,OperationRanking,OperationSeries,OperationDetail,OperationFilters,OperationSource,OperationFoundations,operation-format}` e testes correspondentes.

- [x] Decodificar v2 e adaptar janela/município/alimentador; verificar as opções que as respostas existentes realmente oferecem. Se faltar descoberta de competências/alimentadores, especificar pequena extensão de API com teste de contrato antes de implementá-la; não inventar uma rota de opções nem codificar os 122 IDs.
- [x] Remover `page/page_size` das chamadas de detalhe Gold e retirar tabela/paginador de ocorrências nesse modo. Exibir resumo/série agregados e motivo de indisponibilidade dos eventos individuais.
- [x] Resumo mostra DEC e FEC com estado, numerador e base próprios. Campos genéricos nulos por populações diferentes não significam erro de decodificação. Não calcular média simples nem somar populações mensais no cliente.
- [x] Ranking usa o indicador solicitado, limitações e exclusões; FEC válido continua visível quando DEC falta e vice-versa. Não filtrar apenas a população por classe/bairro.
- [x] Mostrar competências observadas/ausentes, base cadastral sem vigência histórica comprovada e ausência de homologação regulatória. Lacunas de série não viram zero.

Provas: DEC/FEC com populações diferentes; ausência de um numerador; denominador zero/variável; mês ausente; troca do indicador de ranking; detalhe sem paginação fictícia; janela/filtros idênticos entre resumo, ranking e detalhe.

### 5 — Ativação, navegador e reconciliação

- [ ] Ativar `ANALYTICS_SOURCE=gold` somente em perfil local explicitamente configurado após concluir acesso e adaptação das três jornadas. Não recarregar CSVs nem alterar Gold para ajustar a apresentação.
- [ ] Executar a jornada navegador → API → PostgreSQL no mesmo lote/fingerprint, com leituras reais e controles independentes. Registrar valores agregados e evidências sem dados identificáveis; não gravar OS de teste na Gold/ambiente real sem autorização específica. Escritas e ensaios de recarga usam banco descartável com dados artificiais.
- [ ] Conferir Panorama por mês/município/classe; fila com paginação e detalhe; criação/histórico da OS; Operação com resumo/ranking/detalhe. Medir requisições, cancelamento, navegação e tempo no volume recebido, sem declarar SLA não acordado.
- [ ] Conferir temas claro/escuro, responsividade, teclado/foco em modais, contraste, mensagens de estado e alternativa textual dos gráficos. Usar frames existentes do Figma como referência na execução visual, sem redesenho nesta proposta.
- [x] Executar em `frontend/`: `npm run check:boundaries`, `npm run format:check`, `npm run lint`, `npm test`, `npm run test:proxy` e `npm run build`. Acrescentar testes backend apenas para contratos/acesso alterados e os testes integrados de cargas/ordens afetados. Rodar `git diff --check`.
- [ ] Atualizar contratos, guias de serviço e arquitetura para a realidade entregue; registrar evidência e limites no PRD e sincronizar Trello se acessível. Não marcar WEB/DE concluídos somente pelos testes artificiais.

## Ordem e revisão

Executar 1 antes de ativar qualquer tela; depois 2, 3 e 4, com revisão por contrato e domínio; concluir em 5. A implementação de decoders/estados das três áreas pode ser dividida após fixar a fronteira comum. Cada entrega deve ter diff coeso, testes específicos e revisão; integração de Ordens depende também da entrada por Inspeções.

## Critérios de aceite da fatia frontend

1. As três jornadas utilizam contratos reais, identificam origem/recorte e não misturam publicações nas vistas analíticas; snapshots antigos de OS continuam explicitamente históricos.
2. Amostras agregadas Panorama/Operação/fila conferem com controles independentes da Gold; ciclo operacional preserva resultados e histórico nas provas de carga.
3. Ausência, zero, parcial, vazio, erro e falta de permissão são distintos; não existe fallback sintético, estimativa recuperável inventada ou ocorrência reconstruída.
4. Contratos sintéticos e snapshots antigos preservam compatibilidade verificada; acesso Gold é autorizado e nenhum segredo de serviço é enviado ao navegador.
5. Navegador e gates existentes têm evidência reproduzível. O aceite integral DEV-13.1 continua condicionado aos critérios do PRD e às lacunas abaixo.

## Bloqueios e limites externos

Pagamento, energia faturada independente, recuperação, atividade histórica e eventos individuais não são criados por este plano. Ordenação de despacho e definições regulatórias continuam dependentes de homologação. Prova Delta → CSV e amostras reconciliadas pelo responsável da Gold continuam dependências de aceite completo.

Autenticação frontend/provedor, descoberta real de opções de Operação e tratamento de vínculos para capacidades fora da fatia precisam ser fechados nas etapas indicadas. Alteração de critério do PRD ou ADR exige decisão explícita e documentação sincronizada; indisponibilidade apresentada corretamente não equivale a requisito integral concluído.
