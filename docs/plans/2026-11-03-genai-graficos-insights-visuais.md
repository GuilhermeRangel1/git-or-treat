# Gráficos e insights visuais — evidência da implementação

Branch `feat/genai-graficos-insights-visuais`, base develop `77fa425`. Cartão https://trello.com/c/OGgXnYfa. Estado: em desenvolvimento; sem commit/push. Quatro dos 18 critérios têm aceite técnico local nesta fatia: metadados do chat, PNG, CSV e apresentação pt-BR. Os demais permanecem abertos, mesmo quando parte do código já está implementada.

## Composição e resultado

O Backend monta o campo opcional versionado do chat depois da consulta e síntese existentes, com pontos exatos da evidência e dados do catálogo. Fonte/plano/filtros/unidade/período/publicação são conferidos; o serviço GenAI não pode fornecer gráficos. O consumidor valida o JSON e usa `VisualEvidence`, compartilhado com o modal do Panorama. Suporta indicador, barras, ranking horizontal, linha temporal e rosca de participação válida.

Panorama mantém o cartão compacto. Modal responsivo com comparação temporal e distribuição por município/classe; filtros específicos são preservados. Cinco maiores + Demais no servidor; lista completa até 1000, gráfico com até seis setores/dez barras e tabela de vinte linhas por página. Chat conserva até 100 pontos, visualiza até 24/dez conforme tipo e exporta a lista retornada, explicitando o alcance. Sem chamada de modelo adicional.

PNG/CSV revalidam identidade, escopo e publicação no servidor antes de salvar. Troca de conta, permissão, lote ou desmontagem bloqueia o arquivo antigo. Histórico conserva gráfico somente com publicação/escopo atuais; memória e acompanhamento seguem consultando a fonte atual. Os gráficos do modal já aparecem antes da interpretação; o chat ainda aguarda a síntese.

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

## O que continua aberto

- Dados/gráfico antes da síntese no chat, com falha/cancelamento do modelo sem perder os agregados válidos; não simular streaming.
- Leitura ampliada específica do gráfico, proporcional à evidência e sem inferência causal.
- Benchmark comparável de dados/primeiro gráfico/insight e número de chamadas.
- Reconciliação e jornada do novo chat com Gold/modelo real, histórico/retomada/downloads no mesmo ambiente, além dos testes controlados.
- Revisão integral dos 18 critérios, incluindo zoom/leitor de tela e falhas ainda não exercitadas. Não marcar esses itens pelo número de testes.

Estados IA-03/IA-04/IA-05 preservados. Nenhuma chamada Gemini nova ou homologação de cobertura. DEC503 e avisos de consumo continuam com a colega, fora desta mudança.
