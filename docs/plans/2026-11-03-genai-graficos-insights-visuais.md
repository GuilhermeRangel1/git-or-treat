# Gráficos e insights visuais — evidência da implementação

Branch `feat/genai-graficos-insights-visuais`, base develop `77fa425`. Cartão https://trello.com/c/OGgXnYfa. Estado atual: **18/18 critérios técnicos locais contemplados**, com evidências publicadas no [PR #116](https://github.com/GuilhermeRangel1/git-or-treat/pull/116), direcionado à develop. Implementação nos commits622755d,403b772,2e6d92a,6772a10 e399fdb5; documentação final acompanha esta publicação. PR aberto para revisão, sem merge.

## Composição e resultado

O Backend monta a prévia e o campo opcional versionado do chat sobre a consulta existente, com pontos exatos da evidência e dados do catálogo. Fonte/plano/filtros/unidade/período/publicação são conferidos; o serviço GenAI não pode fornecer gráficos. O consumidor valida o JSON e usa `VisualEvidence`, compartilhado com o modal do Panorama. Suporta indicador, barras, ranking horizontal, linha temporal e rosca de participação válida.

Panorama mantém o cartão compacto. Modal responsivo com comparação temporal e distribuição por município/classe; filtros específicos são preservados. Cinco maiores + Demais no servidor; lista completa até 1000, gráfico com até seis setores/dez barras e tabela de vinte linhas por página. Chat conserva até 100 pontos, visualiza até 24/dez conforme tipo e exporta a lista retornada, explicitando o alcance. Sem chamada de modelo adicional.

PNG/CSV revalidam identidade, escopo e publicação no servidor antes de salvar. Troca de conta, permissão, lote ou desmontagem bloqueia o arquivo antigo. Histórico conserva gráfico somente com publicação/escopo atuais; memória e acompanhamento seguem consultando a fonte atual. Os gráficos do modal já aparecem antes da interpretação; o chat negocia dados progressivos antes da síntese, mantendo JSON compatível.

## Verificações reproduzíveis

Backend, com as dependências de requirements instaladas:

```powershell
python -m pytest tests/test_visual_export.py tests/test_chat_visualization.py tests/test_chat_visualization_history.py tests/test_genai_flow.py tests/test_genai_client.py tests/test_ai_history_http.py tests/test_conversation_memory_http.py tests/test_genai_invalidation.py tests/test_panorama_distribution.py tests/test_panorama.py tests/test_panorama_current_composition.py tests/test_gold_panorama_money.py -q --tb=short
```

154 passaram. Inclui sessão ausente, origem pública adulterada, permissão revogada antes/durante a conferência, publicação divergente, IDs/valores/unidade/período adulterados, composição com executor/síntese controlados, compatibilidade histórica, lacuna temporal, filtros, zero/nulo e volume.

Frontend:

```powershell
npm.cmd test -- --run src/shared/analytics/VisualEvidence.test.tsx src/shared/analytics/distributionContract.test.ts src/shared/analytics/panoramaContract.test.ts src/features/assistente/visualization.test.ts src/features/assistente/AssistentePage.test.tsx src/features/panorama/PanoramaInsight.test.tsx src/features/panorama/GoldInsight.test.tsx
npm.cmd run build
npm.cmd run lint
npm.cmd run check:boundaries
```

59 testes passaram. Build e fronteiras passaram; lint sem erro, somente aviso anterior do AuthProvider. Ruff dos dez arquivos novos desta fatia e `git diff --check` passaram. Nos dois arquivos legados do Panorama, permanecem nove apontamentos de Ruff (imports/tipos/literais) idênticos à base77fa425; nenhuma ocorrência nova. Os outros arquivos Python modificados passaram no Ruff. O ambiente Python do host usou apenas pwdlib[argon2] adicional no diretório ignorado work/graficos-runtime; nenhuma dependência versionada mudou.

## Gold local real

Com a configuração Gold já ativa, no Backend desta branch:

```powershell
python -m scripts.check_visual_gold
```

O script usa transação REPEATABLE READ/READ ONLY e timeout de 5 s; compara o serviço de distribuição com SQL independente, sem escrever dados, chamar modelo, mudar privilégios ou imprimir valores/referências. Resultado observado: todos os municípios 14; municípios com classe 14; classes do município 5; recorte específico sem distribuição artificial. Valores/categorias/totais conferidos; participação corretamente indisponível nesses recortes.

Nesta sessão os serviços da porta 5173 continuaram na worktree develop-check. Para não reconstruí-los nem trocar seu código, o probe foi executado em subprocesso isolado no Backend existente, carregando somente os três módulos da feature em memória e executando o mesmo script. O executor local ignorado work/reconcile-overlay.py não contém segredos. Isso comprova a distribuição/repositório com Gold real; não prova o novo chat pelo navegador com Gold/modelo real.

## Navegador e exportações

Chromium com snapshots artificiais serializados pelo Backend e decoder real: chat com linha/tabela, modal com municípios/classes/filtros específicos, PNG/CSV, listas 14/200, tabela paginada, 320/390/1440px e claro/escuro passaram. Caso adicional de 24pontos: PNG 3600px, 320/390/768/1440px, dois temas, movimento reduzido, download negado sem arquivo e Escape/foco do modal passaram. Sem erros JavaScript ou overflow global nos cenários exercitados.

Prévia e scripts locais ignorados em frontend/visual.local, porta 5184, /visual.local/preview.html. Chat em ?view=chat usa resposta artificial fixa; não é consulta Gold/Gemini. Série extensa em ?view=stress. Scripts check-chat-visual.mjs, check-many.mjs, check-distribution.mjs e check-wide-access.mjs. Artefatos em visual-artifacts; PNG do chat inspecionado visualmente. Capturas não contêm dados privados. O uso de ARIA/teclado foi conferido; não houve teste com leitor de tela externo.

Tempos de abertura automatizada de 107–183ms em Vite são observações locais, não benchmark SQL/p50/p95. React 19.2/useId: https://react.dev/reference/react/useId, consultado por Context7 em 03/11/2026. SVG nativo, nenhuma biblioteca nova para gráficos.

## Revisão

| Eixo | Achados e tratamento |
| --- | --- |
| Padrões | Período do contexto não conferido com plano e CSV sem alcance. Corrigidos; revisão confirmou recusa do período adulterado e diff limpo. |
| Especificação | Mesmos dois pontos e PNG 1200px estreito para 24observações. Corrigidos com validação de período, nota exportada e largura até 3600px, metadados em linhas. Sem outros bloqueios encontrados nessa fatia. |

## Continuação — fechamento técnico local

### Implementação

- Negociação NDJSON nas rotas existentes, inclusive histórico, sem repetir planejamento/SQL/síntese. Dados publicados somente depois de auditoria da fonte, revalidação e conferência do plano. Preview explícita, resultado final a substitui. Clientes anteriores seguem JSON.
- Fila de um evento; cancelamento antes/depois do primeiro dado e saída da conversa encerra coordenador. Leitor limita 256KiB, UTF-8 e sequência de eventos. Fonte sanitizada do núcleo aceita apenas com hash exato da origem. Falha do modelo conserva dados somente com acesso/publicação revalidados;403/409 removem a prévia. ErrorBoundary preserva tabela/CSV se o desenho falhar.
- Leitura ampliada local com IDs: diferenças, percentual com base positiva, pico e extremos apropriados ao tipo, sem causa presumida nem participação em ranking. Nenhuma chamada adicional para desenhar/interpretar o gráfico. Distribuição do Panorama também oferece leitura sobre os pontos exibidos.

### Verificações finais

```powershell
python -m pytest tests/test_progressive_question.py tests/test_visual_reading.py tests/test_chat_visualization.py tests/test_chat_visualization_history.py tests/test_visual_export.py tests/test_panorama_distribution.py tests/test_genai_flow.py tests/test_genai_client.py tests/test_ai_history_http.py tests/test_conversation_memory_http.py tests/test_genai_invalidation.py tests/test_panorama.py tests/test_panorama_current_composition.py tests/test_gold_panorama_money.py -q --tb=short
npm.cmd test -- --run src/shared/analytics/ChartBoundary.test.tsx src/features/assistente/AssistentePage.test.tsx src/features/assistente/api.test.ts src/shared/api/jsonStream.test.ts src/shared/api/client.test.ts src/shared/analytics/VisualEvidence.test.tsx src/shared/analytics/distributionContract.test.ts src/features/assistente/visualization.test.ts src/features/panorama/PanoramaInsight.test.tsx src/features/panorama/GoldInsight.test.tsx src/shared/analytics/panoramaContract.test.ts
npm.cmd run build
npm.cmd run lint
npm.cmd run check:boundaries
```

Resultados: 162 Backend e 95 frontend passaram. Build/formatação/fronteiras passaram; lint sem erro, aviso preexistente AuthProvider. Ruff dos novos arquivos e dos demais Python modificados nesta rodada passou, preservados os nove apontamentos anteriores nos dois arquivos legados do Panorama. Diff limpo. Nova revisão de especificação detectou cancelamento antes da prévia; corrigido, teste passou e revisor revalidou. Revisão de padrões não encontrou novo bloqueio.

### Prova Gold/Gemini e portal

Backend temporário 8014 e frontend 5186; GenAI temporária usa o mesmo código da branch e a configuração privada já autorizada. Os serviços principais 5173/8000 não foram alterados. A imagem GenAI principal não continha as últimas mudanças; a rodada final usou o app da branch montado no serviço isolado, evitando confundir versão antiga com falha nova.

Conta temporária somente leitura, senha em memória; cookies e resultados privados só em arquivos ignorados. Perguntas reais: receita faturada de Recife em junho/2026 (um ponto), comparação maio/junho (dois) e série janeiro–junho (seis). Todas `answered`, preview antes de complete. SQL independente `SUM(receita_total_reais)` por competência no diagnóstico Gold v2, transação somente leitura pelo leitor dedicado: todos os pontos e a identidade do conjunto inicial/final conferidos. CSV baixado pelo portal igual aos pontos e SQL.

Histórico real: pergunta inicial, acompanhamento de mês, definição DEC e retomada da primeira pergunta. Quatro respostas `answered`, três gráficos; conceito cita documentação sem gráfico. Restauração de quatro interações/três gráficos passou; filtros do acompanhamento/retomada iguais ao inicial e os valores retomados conferem. Conversa temporária apagada ao final. Portal real: gráfico/tabela/CSV/PNG e recarga passaram, zero erros JavaScript. Restauração também conferida pela API real.

Scripts privados reproduzíveis nesta sessão: `python frontend/visual.local/check-real-progress.py`, `python frontend/visual.local/check-gold-history.py`, `node visual.local/check-real-browser.mjs`, `python frontend/visual.local/benchmark-visual.py`. Dependem da sessão temporária e composição local; arquivos não serão commitados. Roteiro portátil: iniciar composição Gold desta branch; autenticar leitor autorizado; enviar as três perguntas acima com Accept JSON/NDJSON; comparar pontos com SQL independente na mesma publicação; conferir tabela/CSV/PNG e histórico; remover conta/conversas de teste. Nunca registrar cookie, senha, chave ou números privados no relatório público.

### Latência exploratória

Mesma comparação, mesmos serviços/Gold, três requisições por modo; sequência JSON seguida de progressivo, sem carga controlada. Valores em segundos:

| Modo | Primeiro dado p50 | Primeiro dado p95 empírico | Completo p50 | Completo p95 empírico |
| --- | --- | --- | --- | --- |
| JSON |15,792|19,213|15,792|19,213|
| Progressivo |14,153|14,653|16,069|16,917|

P95 nearest rank = máximo com n=3. Amostra apenas local, sem SLA/garantia de melhora total. O ganho observado é antecipar os dados; a síntese continua variável. Os logs sanitizados da GenAI isolada registraram 14 correlações com uma chamada real por correlação. Não há chamada para gerar gráfico; retentativas já existentes continuam possíveis. O middleware HTTP mede cabeçalhos no stream; os tempos acima vêm do consumidor até cada evento/final, não desse log parcial.

### Acessibilidade e falhas

Chromium:320/390/768/1440, claro/escuro, zoom de 200%, movimento reduzido, abertura/fechamento por teclado, Escape/foco e títulos/descrições SVG passaram. Árvore ARIA da tabela contém cabeçalhos de coluna/linha e alternativa completa dos valores. Isso é conferência da árvore usada por tecnologia assistiva; não houve sessão manual com NVDA. Não depende apenas de cor. Teste automatizado de renderer com erro preservou tabela/CSV. Série de 24pontos exporta PNG 3600px. Cenários controlados continuam cobrindo tipos, escalar, nulo/zero/base zero/parcial, nomes extensos, payload adulterado/excessivo e falhas. Conteúdo real não entrou nas capturas públicas.

### Matriz dos 18critérios

| Critério | Evidência | Estado local |
| --- | --- | --- |
| Contrato versionado e limites |schemas/decoders, IDs,32KiBchat/256KiBPanorama/stream, rejeição de extras|Atendido|
| Executor e pontos autorizados |consulta existente, SQL real independente, filtros mantidos|Atendido|
| Escolha dos quatro tipos |barras/linha/ranking/rosca válida, testes zero/nulo/parcial|Atendido|
| Renderer/tabela/acessibilidade |Chromium quatro larguras/dois temas/zoom/ARIA/teclado|Atendido|
| Vínculo de consulta e publicação |mapper, decoder, testes adulteração e invalidação|Atendido|
| Caso de uso/HTTP/tela e Gold |162/95 testes, portal real, SQL independente|Atendido|
| Composição realmente usada |Backend+GenAI da branch, sessão e leitor dedicados|Atendido|
| Identidade/cache/histórico/exportação |revogação, origem inválida, restauração real e testes|Atendido|
| Timeout/cancelamento/modelo/download |fluxos controlados, cancel antes/depois, prévia revalidada, boundary|Atendido|
| Registro no PR e documentos/cartão |[PR #116](https://github.com/GuilhermeRangel1/git-or-treat/pull/116), relatório e contratos publicados|Atendido|
| Modal com gráficos/análise |distribuição e leitura ampliada, componentes compartilhados|Atendido|
| Leitura proporcional fundamentada |VisualReading local/IDs/base positiva/extremos, sem causa|Atendido|
| Metadados legíveis sem acordeão |interface e regressões conceituais|Atendido|
| PNG |chat/modal, real/controlado,24pontos, metadados/temas|Atendido|
| CSV |precisão/escape/nulo/zero, alcance, real=SQL|Atendido|
| Latência/chamadas |comparação local 3+3, eventos reais,14 correlações|Atendido|
| Histórico/acompanhamento/memória |quatro interações reais, três gráficos, conceito/retomada|Atendido|
| pt-BR |catálogo/precisão, datas/moedas/contagens/tabela/exportações|Atendido|

Não há outra pendência de implementação identificada nesta revisão. O último critério foi atendido pela publicação das alterações e evidências no [PR #116](https://github.com/GuilhermeRangel1/git-or-treat/pull/116); a conclusão técnica local não decorre apenas deste arquivo. Estados oficiais IA/homologação de Dados preservados; recortes sem cobertura continuam indisponíveis. DEC503 e avisos de consumo da colega não foram alterados. Revisão/CI/merge do PR são etapas de integração posteriores, sem merge automático.


## Disponibilização no Docker para conferência

Em03/11, imagens de IA, Backend e frontend foram reconstruídas desta branch. Configuração privada foi copiada somente para os arquivos .env ignorados; nenhum segredo foi exibido ou commitado. .dockerignore exclui também variações .env, work/ e a prévia artificial do contexto de build.

```powershell
docker compose --env-file .env.gold-v2 -p dev131-gold -f docker-compose.yml -f docker-compose.gold-v2.yml build ai-agent backend frontend
docker compose --env-file .env.gold-v2 -p dev131-gold -f docker-compose.yml -f docker-compose.gold-v2.yml up -d --no-deps --force-recreate ai-agent backend frontend
```

Build/recriação passaram. Frontend5173 e health Backend8000 responderam200; GenAI saudável, Gold ativa e chave configurada (somente presença conferida). Mounts apontam a worktree genai-graficos. Volume PostgreSQL e lote preservados, sem executar loader ou migração. Smoke autenticado real na composição reconstruída: comparação maio/junho, data→complete e dois pontos iniciais/finais iguais; conta temporária removida. Usuários/sessões existentes não foram redefinidos. Docker permanece ativo para a pessoa usuária conferir no navegador.


## Sincronização do PR com a develop atual

Após abrir o PR116, a develop estava em6fc93de, com as entregas do PR115 de Inspeções/Ordens e ajustes visuais. A integração nesta branch foi preparada por merge normal, sem squash, cherry-pick ou reescrever commits. Não houve conflitos de conteúdo; históricos e documentos dos dois lados foram preservados. Não é merge deste PR na develop.

Verificação na árvore integrada:186 testes Backend passaram na imagem Docker limpa (162 da fatia e regressões de field_files/order_lifecycle);153 testes frontend passaram (95 da fatia e regressões de Inspeções/Ordens/Receita), build e fronteiras passaram. Os testes adicionais validam os pontos recebidos da develop, sem introduzir novos cenários na feature. Backend recebeu as dependências já versionadas pela develop (openpyxl/defusedxml); sua imagem foi reconstruída e Backend/frontend recriados, sem tocar no volume Gold. localhost5173 e health8000 continuaram200, IA saudável. Os186 testes da imagem registraram somente aviso de descontinuação do TestClient/httpx da versão instalada; nenhum teste falhou.


### 2026-11-03 — IA-04 — leitura imediata e estabilidade do insight

- Integração executável local na branch `feat/genai-graficos-insights-visuais`, ainda sem novo commit: leitura calculada dos indicadores/distribuição assim que o Panorama chega. A hipótese continua identificada como geração da IA e chega depois; falha recuperável preserva leitura e nova tentativa. Contexto inválido não reapresenta interpretação antiga.
- Sínteses respondidas vinculadas ao contexto são reutilizadas por 120 s, até 64 entradas em memória por processo. Chave: tela, evidência, limitações, lote e escopo/identidade completos; só o saldo transitório de prazo é excluído. Cada requisição mantém prontidão, autorização, leitura e publicação atuais e nova auditoria; falhas não entram no cache. Reiniciar o Backend limpa o cache. Navegador cancela em 70 s e na troca de recorte, com limpeza de timer/listener.
- Antes: respostas reais em 44,540 s e 40,824 s. Perfil separado: total 49,565 s, prontidão 14,353 s, snapshot 0,020 s, síntese 35,060 s. Depois, reutilizações em 13,060 s e 13,630 s, `answered`, com observações/hipótese iguais e auditorias distintas. A rodada inicial pós-alteração teve falha recuperável em 29,512 s e resposta em 36,765 s; o provedor continua variável. Amostra exploratória, sem alegação de SLA.
- Chromium no localhost: leitura visível com IA deliberadamente pendente em 4.967 ms (390 px) e 2.224 ms (1440 px); zero erros JavaScript. Interceptação controlada prova apresentação; medições API acima usaram Gold/Gemini reais, sem publicar payloads ou segredos.
- Verificações: Backend `test_genai_client.py`, `test_gold_panorama_coordination.py`, `test_ai_insights.py`: 71 aprovados; frontend `GoldInsight`, `InsightInvalidation`, `PanoramaInsight`, `InsightFilterScope`: 14 aprovados. Build, fronteiras (218 arquivos), Ruff direcionado e `git diff --check` passaram; lint mantém aviso preexistente do AuthProvider. Estados obrigatórios do PRD preservados.


### 2026-11-03 — IA-04 — competência e comparação explícitas no insight

- A inspeção do fluxo não reproduziu envio de outra competência: filtros da URL, chave da consulta e contexto validado acompanham mês/comparação. A ambiguidade visual existia: comparação sem valor anterior não mostrava o mês solicitado; a leitura durante a espera priorizava distribuição territorial, mesmo com variação temporal válida.
- O cartão e o modal agora identificam o mês solicitado na comparação indisponível. A leitura imediata prioriza variação temporal quando calculada. O consumidor confere também o valor do período anterior contra o KPI antes de aceitar a síntese; datas/filtros continuam sujeitos às guardas existentes. O gráfico recebe explicitamente a origem Gold e seus botões são identificados como janela do gráfico (a síntese mensal segue os filtros da página).
- Chromium no portal real, usando Ajustar filtros → Aplicar: maio/2026 com abril, junho com junho/2025, junho sem comparação e junho com maio. Payload do insight e rótulo visível coincidiram nos quatro casos; zero erros JavaScript. A síntese foi mantida pendente por interceptação para provar atualização imediata, sem novas chamadas Gemini nesta verificação.
- Regressões: 72 testes Backend (transporte/cache/coordenação/insights) e 21 frontend (cartão, invalidação, filtros e série) aprovados; build, Ruff direcionado e diff-check passaram. Cache testado também com comparação diferente. Alterações locais sem commit/push; estados obrigatórios preservados.


### 2026-11-03 — IA-04 — concentração e próximo passo sem espera pelo modelo

- O trecho “segmento concentra X% da receita observada” e o próximo passo ainda dependiam de a síntese terminar para aparecer nesse formato. A resposta inicial do Panorama agora inclui `distribuicao.composicaoReceita`, calculada no Backend sobre os mesmos grupos já lidos, sem nova consulta SQL nem chamada Gemini. `revenue_composition_from_groups` é compartilhado com a síntese; o consumidor valida dimensão, maior segmento, valor e percentual contra o conjunto reconciliado e usa os mesmos formatadores do cartão final.
- Durante a espera, cartão e modal apresentam essa leitura e o próximo passo. A hipótese complementar continua separada e depende da IA. Zero, valores negativos, soma incompatível e grupos fora do limite não produzem concentração. A condição de cobertura mensal e as regras de comparação permanecem as existentes.
- Chromium no localhost com Gold real e chamada IA interceptada: texto de concentração e próximo passo visíveis em 2.280 ms (390 px) e 2.237 ms (1440 px), ambos com IA ainda pendente; zero erros JavaScript. Isso comprova a antecipação do trecho apontado, sem afirmar redução da latência do provedor.
- Verificações: 59 testes Backend (`test_panorama_current_composition`, `test_panorama_distribution`, `test_gold_panorama_coordination`, `test_panorama`) e 26 frontend (`GoldInsight`, `distributionContract`, `panoramaContract`, `PanoramaInsight`, `InsightInvalidation`) aprovados; build/fronteiras e Ruff dos serviços passaram. O schema Panorama mantém quatro avisos UP045 anteriores, sem novo problema funcional. Complemento local sem commit/push.


### 2026-11-03 — IA-04 — insight pronto permanece durante revalidação

- Retorno à janela/refetch do mesmo insight Gold respondido confere acesso/publicação pelo endpoint existente de verificação e reutiliza a análise em memória, sem repetir Gemini. A chave agora também inclui valores atual/anterior e unidade. A verificação tem limite de 8 s, cancelamento e escopo de bairro quando utilizado; troca de recorte/identidade/publicação mantém as invalidações existentes.
- O cartão e o modal mantêm a análise durante essa conferência. Falha de transporte/5xx preserva a última análise com aviso discreto de atualização pendente; 401/403/409 e contexto inválido continuam ocultando-a. A leitura calculada dos indicadores continua independente da primeira geração. Cache não é persistido em navegador/banco.
- Chromium com sessão local e insight Gold/Gemini real: uma geração, três conferências (200 real, 503 e 403 controladas). Conteúdo permaneceu nos dois primeiros casos e foi ocultado na recusa; nenhum segundo POST de geração ocorreu. Sem publicar números, mensagens, credenciais ou payloads.
- Frontend: 16 testes direcionados (`GoldInsight`, `InsightInvalidation`, `PanoramaInsight`, `InsightFilterScope`) e build passaram; fronteiras (218 arquivos) e diff-check passaram; lint mantém só o aviso preexistente do AuthProvider. TanStack Query v5: comportamento de revalidação/erro conferido via Context7 na documentação/código oficial (`tanstack/query`, query.ts), preservando os controles de negócio no consumidor. Complemento local sem commit/push.


### 2026-11-03 — publicação dos complementos de latência e estabilidade

Os complementos locais acima foram preparados para publicação na mesma branch do PR #116: `ee77230` (reuso de síntese), `33a030c` (concentração antecipada) e `80ac907` (consumidor estável e recorte). As referências anteriores a ausência de commit descrevem o estado durante as validações. Esta atualização documental integra o quarto commit autorizado; segredos, credenciais, scripts privados de navegação e artefatos locais permanecem fora do Git. O push não equivale a merge nem a aprovação da CI remota.

### Correções após perguntas no portal — 03/11/2026

As imagens reportadas mostraram restrições legadas de linguagem/capacidade e apresentação inadequada. A extensão usa o mesmo perfil Gold v2, o orquestrador, executor e renderer compartilhado; não adiciona SQL, fonte, permissão ou chamada Gemini para desenhar. Cadência mensal explícita deixa de ser recusada; município/classe/bairro de consumo usam agrupamentos autorizados. Datas incompletas, ausência de cobertura e comparação de bairro continuam sujeitas aos controles existentes. Categorias sem ordem explícita mostram os dez maiores valores e informam o alcance; todas as observações permanecem na tabela/CSV. Ordens explícitas são preservadas. Resposta resumida e comparação pt-BR derivam das observações verificadas; o runner mantém vínculo mês/valor no novo formato.

Reprodução privada no localhost, com sessão existente e agregados minimizados autorizados:

| Pergunta | Resultado final | Pontos reconciliados com SQL |
| --- | --- | --- |
| Como evoluiu o consumo medido em Recife, mês a mês, de janeiro a junho de 2026? | `answered`, linha | 6 |
| Mostre a receita faturada por classe em Recife em junho de 2026. | `answered`, barras horizontais | 5 |
| Quais municípios tiveram maior consumo medido em junho de 2026? | `answered`, barras horizontais | 14 |
| Distribua a receita faturada por município em junho de 2026. | `answered`, barras horizontais | 14 |
| Compare o consumo medido em Recife entre janeiro e junho de 2026. | `answered`, barras verticais | 2 |

Os cinco fluxos emitiram `data → complete`; prévia, pontos finais e SQL independente reconciliados. Tempos completos 16,910 / 18,761 / 15,830 / 16,265 / 17,247 s, respectivamente; não são SLA. Fonte de conferência: somas independentes da projeção Gold v2 autorizada, sem reutilizar o builder SQL nem extrair números do texto. Scripts/payloads/sessões/capturas ficam ignorados em `frontend/visual.local`, sem dados privados no Git.

Chromium com sessão real e nova pergunta de ranking confirmou resposta final, barras à esquerda, ausência de overflow em 320/390/1440 px e ambos os temas, 14 linhas na tabela e downloads PNG/CSV. Captura adicional por repetição do retorno autorizado, sem nova geração; zero erros JavaScript. Conversas de teste removidas, inclusive a primeira rodada interrompida por espera inadequada no script; conversas anteriores preservadas. O roteiro passou a esperar a mensagem final exibida, e a medição geométrica usa o SVG do gráfico em vez do ícone do botão.

Comandos de regressão executados no Docker (GenAI com cópias de testes e contratos do repositório; Backend com bind da worktree):

- GenAI `python -m pytest -q tests/test_gold_visual_questions.py tests/test_gold_planning_http.py tests/test_core_plan_synthesis.py tests/test_interpreter.py tests/test_interpreter_rules.py tests/test_gold_question_filters.py tests/test_gold_receptivity.py`: 349 passaram.
- Runner `python -m pytest -q tests/test_gold_domain_runner_integration.py`: 36 passaram, incluindo rejeição dos meses trocados no formato novo e antigo.
- Backend `python -m pytest -q tests/test_chat_visualization.py tests/test_chat_visualization_history.py tests/test_visual_reading.py tests/test_visual_export.py`: 30 passaram.
- Frontend `npm test -- src/shared/analytics/VisualEvidence.test.tsx src/features/assistente/visualization.test.ts src/features/assistente/AssistentePage.test.tsx`: 44 passaram. `npm run build`, `npm run check:boundaries` (218 arquivos) e Ruff direcionado passaram; `npm run lint` mantém aviso preexistente do AuthProvider.

Backend reiniciado e imagem final do ai-agent reconstruída sem reexecutar loader ou alterar o volume Gold. Nova fatia local ainda sem commit/push; estados oficiais e homologação de cobertura permanecem os anteriores.

### Correção do CI documental — 03/11/2026

O [job documental do PR116](https://github.com/GuilhermeRangel1/git-or-treat/actions/runs/41689965234/job/126105642480), head `9822087`, falhou somente no link `docs/services/backend.md → ../decisions/0005-backend-python=312-alpine.md`. Os outros quatro checks passaram. O guia agora aponta para a ADR existente `0005-backend-python312-alpine.md`; nenhuma regra do workflow foi afrouxada. Reprodução do próprio bloco Python de `.github/workflows/quality.yml` em cópia de `git archive HEAD` com overlay dos arquivos locais alterados: configurações válidas, seis imports presentes, 167 documentos sem links quebrados. `git diff --check` passou. Correção ainda local, sem commit/push ou nova CI remota.

### Indicador de andamento — 03/11/2026

O envio corrente mantém uma fase explícita na página: consulta antes de `data`, interpretação após a prévia e repouso ao concluir resposta/erro. A fase também governa lateral/compositor, inclui criação de conversa e é limpa na troca de conversa/histórico; revisões antigas continuam descartadas. Não depende somente de `mutation.isPending`, evitando um aviso de consulta junto de conteúdo já encerrado.

`npm test -- src/features/assistente/AssistentePage.test.tsx src/features/assistente/AssistenteSession.test.tsx`: 33 passaram, incluindo os três desfechos do stream (sucesso, falha do modelo e acesso negado). Build, fronteiras (218 arquivos), formatação dos arquivos alterados e diff-check passaram; lint mantém aviso anterior do AuthProvider. Chromium com retorno Gold já reconciliado repetido na rota de perguntas confirmou final sem “Consultando os dados…”/“Preparando a análise…”, lateral pronta, tabela e PNG/CSV; zero erros JS. Conversa de teste removida. Nenhuma chamada Gemini nova foi necessária; HMR do Docker local já apresenta a alteração. Mudança ainda sem commit/push.


## Correção da seleção de gráfico no chat — 03/11/2026

O tipo donut existia somente no componente/Panorama. O chat restringia schema e decoder a bars/horizontal/line; a pergunta de distribuição por município sempre virava barras. A afirmação anterior de setorial no chat era incorreta.

Agora o mapper considera rosca para billing.revenue e energy.consumption agrupados em uma competência, sem order, com 2–99 categorias únicas, valores não negativos e total positivo finito. Resultado que atinge o limit do plano permanece barras; médias, índices e múltiplos períodos também. O total é dos valores observados, sem inferir cobertura mensal. Schema/decoder validam parcela e conjunto exato; até 100 referências visuais permitem representar grupos reais antes de condensar a legenda. Backend monta total e setores com valor, percentual e IDs das parcelas; schema e decoder conferem soma, participação e cobertura exata do conjunto sem repetição. O portal apenas formata/renderiza os setores recebidos. A leitura opcional conserva seu limite de 24 IDs e é omitida para conjuntos maiores. Tabela/CSV mantêm a lista individual completa e a rosca reutiliza o renderer/PNG do Panorama com até seis setores ou cinco maiores + Demais.

Verificações executadas nesta fatia:

- `docker exec dev131-gold-backend-1 python -m pytest -q tests/test_chat_visualization.py tests/test_chat_visualization_history.py tests/test_visual_reading.py tests/test_visual_export.py`: 36 passaram. Inclui 14/30 categorias, ranking ascendente, negativos, soma zero, limite da consulta e múltiplos períodos.
- `npm test -- --run src/features/assistente/visualization.test.ts src/shared/analytics/VisualEvidence.test.tsx src/features/assistente/AssistentePage.test.tsx`: 47 passaram. Rosca soma 105 no controle de 14 grupos, cinco maiores + Demais de 45, tabela completa, percentuais somando aproximadamente 100%; parcelas negativas e total zero recusados.
- Build TypeScript/Vite, fronteiras (218 arquivos), Ruff e diff passaram; lint somente com aviso preexistente em AuthProvider. Arquivos TypeScript formatados com Prettier.
- Cinco perguntas pela API pública, mesma Gold v2 local e Gemini real: série mensal line (6 pontos, 17,067s), classe donut (5, 15,813s), ranking horizontal (14, 15,590s), distribuição municipal donut (14, 15,920s), comparação bars (2, 15,620s). Todas answered, com data e complete. Os 41 pontos de prévia/final foram reconciliados com SQL independente somente leitura pelo leitor existente.
- Chromium com repetição da resposta Gold real anterior, sessão real e conta existente: rosca com seis setores/14 linhas em 320/390/1440, dois temas, PNG/CSV e zero erros JS. Provas locais ignoradas em frontend/visual.local; conversa criada foi removida. O teste inicial teve seletor ambíguo entre legenda SVG de exportação e legenda visível; corrigido no probe privado para consultar apenas a lista visível, sem alteração do produto.

Backend reiniciado para aplicar o seletor; frontend recebe a alteração pelo bind mount/HMR. Conversas salvas anteriormente mantêm seu gráfico antigo. Nova pergunta usa a seleção nova. Nenhum commit/push nesta fatia.

- Complemento do contrato final: total e percentuais dos setores foram movidos para o Backend, conforme o cartão. A distribuição municipal foi repetida pela API/Gold/Gemini real (16,569s); os 14 pontos continuaram reconciliados com SQL independente. Chromium repetiu esse retorno final e aprovou seis setores, 14 linhas, PNG/CSV, dois temas e três larguras; a conversa foi removida. Os mesmos 36 testes Backend e 47 frontend passaram após a mudança do contrato, assim como build, lint/fronteiras e Ruff. As cinco consultas anteriores não devem ser contadas como cinco rodadas adicionais do contrato final de setores.


## Simplificação do histórico salvo — 03/11/2026

Removidos, por solicitação da pessoa usuária, o banner “Você está vendo respostas salvas” e a ação “Retomar com dados atuais”. A interface não ativa mais refresh_context por botão; novas perguntas conservam o envio normal com false. Estados exclusivos da ação foram removidos. O aviso de requisição interrompida permanece específico ao envio pendente e o teste verifica a ausência da opção removida, a criação de nova tentativa e o envio normal.

`npm test -- --run src/features/assistente/AssistenteSession.test.tsx src/features/assistente/AssistentePage.test.tsx`: 32 testes passaram. Prettier e diff passaram. Alteração disponível no bind mount do frontend, sem commit/push.


## Correção de “entre as classes” — 03/11/2026

A validação de calendário tratava qualquer “entre” restante após remover as datas como um intervalo incompleto. O interpretador agora reconhece “entre [as/os] <dimensão>” no mesmo ponto de agrupamento existente e mascara essa referência antes de verificar extremos temporais. Valores específicos após a dimensão continuam filtros; janelas reais incompletas continuam bloqueadas. Há regressões para a pergunta exata de Olinda/junho2026, consumo entre municípios e intervalo desde março sem extremo final.

- `docker exec dev131-gold-ai-agent-1 python -m pytest -q tests/test_gold_visual_questions.py tests/test_gold_question_filters.py tests/test_gold_receptivity.py tests/test_interpreter.py tests/test_interpreter_rules.py tests/test_gold_temporal.py tests/test_gold_planning_http.py`: 334 passaram. A primeira tentativa encontrou os schemas Backend ausentes na pasta auxiliar usada pelo teste entre processos; a cópia foi corrigida e a mesma suíte passou integralmente, sem ignorar casos.
- Ruff nos dois arquivos alterados e `git diff --check` passaram. A imagem ai-agent foi reconstruída pelo Compose Gold existente (`up -d --build --no-deps ai-agent`), preservando .env, usuários e volume Gold.
- API pública, sessão operator existente e Gemini real: pergunta exata da captura retornou HTTP200/answered, data→complete, tipo donut e cinco classes (15,186s). Cinco pontos da prévia/final conferidos por SQL independente: soma de receita_total_reais em diagnostico_receita, municipio=OLINDA, competencia=2026-06, agrupado por classe_consumo. Nenhuma nova conta, ampliação de permissões ou alteração da publicação.
- Probes e respostas privados em frontend/visual.local, ignorados. Sem commit/push.

### 2026-11-03 — publicação das correções de perguntas, gráficos e histórico

Os três grupos autorizados foram commitados na mesma branch do PR #116: 440b249 fix(ai-agent): interpreta agrupamentos e séries nas consultas Gold; fae2d53 feat(assistente): apresenta distribuições autorizadas em rosca; 8bcc982 fix(assistente): sincroniza progresso e simplifica o histórico. Este registro acompanha a correção documental da ADR-0005. As notas anteriores de ausência de commit descrevem as etapas de validação; os quatro commits estão preparados para push, com verificações observadas registradas nos respectivos corpos. Arquivos privados e segredos permanecem fora do Git. CI remota e merge continuam posteriores à publicação.


### 2026-11-03 — IA-04 / IA-07 — composição setorial e leitura contextual do Panorama

- Ajuste de apresentação na branch `feat/genai-graficos-insights-visuais`: o modal deixa de repetir o total/comparação temporal como gráfico. Prioriza principais pontos e conserva apenas rosca de composição válida por município/classe, com tabela e exportações existentes. Recortes sem partição positiva válida não ganham percentuais artificiais.
- Cartão e modal apresentam valores inicial/final e diferença, além do percentual fornecido pela API. A leitura distingue base zero, estabilidade, ausência de comparação e concentração; composição não oculta a tendência quando ambas existem. Recomendações consideram os filtros já selecionados. Usa os mesmos indicadores/análise autorizados, sem nova chamada ao modelo ou cálculo de métrica no navegador.
- Verificações: 26 testes passaram em `InsightPresentation.test.tsx`, `GoldInsight.test.tsx`, `PanoramaInsight.test.tsx` e `VisualEvidence.test.tsx`; build, fronteiras em 219 arquivos e lint passaram (lint mantém o aviso anterior em AuthProvider.tsx:108). Chromium: três recortes Gold reais, com competência/comparação/filtros distintos, em 1440/390/320px, sem transbordamento ou erros JS; esses recortes não forneceram partição elegível e mantiveram texto sem gráfico. Rosca e tabela conferidas separadamente com fixture demonstrativa nos dois temas e três larguras. Os erros iniciais de preâmbulo/import React pertenciam ao probe isolado; corrigidos sem mudança de produção.
- Estados oficiais IA preservados; conferência de UI não homologa cobertura da fonte. Arquivos privados de captura/probe ignorados. Alteração local, sem commit/push nesta rodada; evidência vinculada ao cartão de gráficos.


### 2026-11-03 — IA-05 / IA-07 — quatro sugestões para explorar gráficos

- As quatro perguntas iniciais do Assistente passam a oferecer distribuição de receita por município (rosca), ranking municipal de consumo (barras horizontais), comparação de consumo entre janeiro/junho (barras verticais) e evolução mensal de janeiro a junho (linha). São as mesmas formulações exercitadas com Gold v2/Gemini e reconciliadas anteriormente nesta branch; o tipo continua condicionado ao resultado autorizado, sem forçar visualizações.
- Mantidos quatro botões, envio existente e FAQ sem repetição das sugestões iniciais. Testes existentes da página atualizados: página/FAQ tiveram 32 testes aprovados. Alteração local, sem commit/push.


### 2026-11-03 — IA-04 / IA-07 — blocos exportáveis sem resumo duplicado

- Por refinamento solicitado, restaurados os blocos de total/comparação e distribuição com tabela/download no modal. Removido somente o resumo superior “Dado observado”, que repetia o total. Distribuição volta a usar rosca ou barras conforme os dados autorizados; a restrição anterior a somente rosca está superada. Textos aprimorados, recomendações e quatro sugestões de gráficos do chat preservados.
- 26 testes de apresentação/insight/visualização passaram após atualizar as expectativas do modal; build e fronteiras (219 arquivos) passaram, lint conserva somente o aviso anterior em AuthProvider.tsx:108. `git diff --check` passou. Sem commit/push nesta rodada; estados oficiais preservados.

- Conferência final no Chromium: recortes Gold em 1440/390/320px mostraram blocos exportáveis, ausência do resumo superior duplicado e nenhuma falha temporária ou transbordamento horizontal. Distribuição em barras reapareceu nos recortes elegíveis; município/classe específicos conservaram somente o total exportável, sem fabricar grupos.

### 2026-11-03 — publicação dos refinamentos do modal e das sugestões

Os refinamentos autorizados foram commitados nesta branch: abaf0fd (modal e leitura) e a92d85b (sugestões de gráficos). As notas anteriores de ausência de commit descrevem etapas históricas. Este registro documental acompanha o terceiro commit, com publicação no PR #116 e CI posterior ao push.


### 2026-11-03 — correção das expectativas numéricas do CI

- O run 41713380946 do PR #116 falhou em GenAI e Backend porque as expectativas ainda usavam casas decimais e espaços do formato antigo. Alinhadas as verificações de comparação, consumo, ranking e satisfação à apresentação vigente em português; preservados os valores esperados, unidades, períodos e sinais. Nenhuma alteração no comportamento do portal ou no cache dos insights.
- GenAI em cópia Linux isolada: `python -m pytest -q` — 4.344 passaram, 4 skips; `python -m ruff check .` e compilação passaram.
- Backend completo antes do último alinhamento: 1.210 passaram, 14 skips e uma falha de formatação no teste de sessão. Após alinhar as demais expectativas do mesmo teste: `python -m pytest -q tests/test_genai_session_postgres.py --tb=short` — 1 passou com PostgreSQL 16 descartável, atravessando sessão, plano, execução, síntese e negação de privilégios; aviso preexistente Starlette/httpx.
- Lint dirigido Backend passou desconsiderando somente EXE002, causado pelo bit executável da cópia Docker; `pip check` passou. Nenhum dado Gold real, segredo ou chamada Gemini nesta correção. CI remoto deve ser reconferido após o push.
