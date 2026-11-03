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
