# Comparação local HNLU — 2026-11-06

## Escopo e proveniência

Comparação offline do baseline limpo no commit `051123248be443537346544a6ee71617ed1d94cc` com a árvore de trabalho da branch `feat/nlu-generativa-hibrida`, baseada no mesmo commit. A árvore HNLU estava suja e foi montada somente para leitura. Os dois lados usaram modo determinístico, sem provedor, SQL real ou consulta à publicação Gold. A cobertura e os dados dos avaliadores são artificiais.

## Resultados

| Conjunto | Base limpa | Árvore HNLU | Observação |
| --- | ---: | ---: | --- |
| `gold_language_eval.json` | 32/32 | 32/32 | Sem diferença no planejador determinístico. |
| `gold_language_holdout.json` | 16/16 | 16/16 | Foi executado e não é mais um holdout cego. |
| `gold_p0_user_reported.json` | 4/7 | 4/7 | Mesmos desvios: `REAL-01`, `REAL-02` (`clarification_reason`) e `REAL-02C` (estado/plano da continuação). |
| Regressão ampliada | 160/163 | 160/163 | Mesmas falhas conhecidas: `LEGACY-near_miss_falta_de_luz_por_municipio_no_evidence`, `LEGACY-near_miss_interrupcoes_em_olinda_por_classe_no_evidence` e `LEGACY-scope_breakdown_by_municipality_no_evidence`. |

Isso confirma que a bateria determinística reproduz a base, mas não mede a proposta Gemini. Em sete rodadas completas dos seis casos sintéticos, as pontuações originais do Gemini variaram de 1/6 a 4/6; o determinístico marcou 6/6 em todas. A revisão do comparador confirmou que `GUARD-04` exige esclarecimento, mas não fixa o motivo interno: `ambiguous_metric` e `multiple_metrics` são válidos para a pergunta que combina faturamento e recebimento. Recalculada com esse critério, a última rodada fica em 5/6, contando o erro 503 como incorreto. Portanto, ainda não há evidência de ganho generativo nem promoção para uso. Nenhuma execução validou resposta numérica.

## Primeira medição com Gemini

O auto-review bloqueou a primeira tentativa. Após autorização explícita do payload exato, foram feitas sete rodadas completas de seis chamadas ao `gemini-3.5-flash-lite`, mantendo a amostra `REV-02`, `ENE-02`, `RANK-03`, `DEC-01`, `GUARD-04` e `GUARD-07`. As notas Gemini no oráculo original foram 3/6, 3/6, 2/6, 4/6, 3/6, 1/6 e 4/6; o baseline determinístico marcou 6/6. Na última, `multiple_metrics` em `GUARD-04` foi aceito após corrigir o comparador: a expectativa requer esclarecimento, sem exigir um motivo interno específico; a pontuação recalculada é 5/6, contando o 503 como erro. As falhas observadas incluíram 503, respostas inválidas por JSON/contrato e filtros/períodos inicialmente perdidos. Foram corrigidos os casos de competência numérica, filtro obrigatório exato, normalização da versão/`null` e o falso negativo do comparador; a instabilidade do provedor permanece. A última rodada registrou p50 2.131 ms, p95 3.854 ms e 25.651 tokens. Os sete relatórios completos informaram 147.361 tokens; uma chamada diagnóstica parcial não persistiu o uso.

O artefato sanitizado da última rodada, com fingerprint e hashes das fontes, está em [hnlu-gemini-sample-2026-11-06.json](hnlu-gemini-sample-2026-11-06.json). Ele contém IDs, estados, campos estruturados, métricas e metadados de execução; não contém perguntas/respostas brutas, SQL, linhas Gold ou segredos. As sete rodadas não são independentes: usaram a mesma fixture e várias ocorreram após ajustes no prompt/planner. A última árvore estava suja, baseada no commit `0511232`.

## Regressões executadas na árvore HNLU

- GenAI completo, Docker offline, provedor desativado, diretório neutro para não carregar `ai-agent/.env`: `python -m pytest -q -p no:cacheprovider --tb=short ai-agent/tests` — **4.577 passaram, 4 skips**.
- Backend completo, Docker offline: `python -m pytest -q -p no:cacheprovider --tb=short backend/tests` — **1.219 passaram, 114 skips, 1 aviso de depreciação**.
- Provedor/planner/benchmark/rota, calendário, filtros e normalização de contrato: **90 passaram**.
- Continuação, contrato interno, cliente e teste de planejamento real opcional do Backend: **143 passaram, 1 skip**.
- Tela Assistente: `npm test -- --reporter=dot src/features/assistente` — **65 passaram**.
- Suíte completa frontend: **551 passaram, 1 falha e 1 erro não tratado** porque o `node_modules` local não contém `leaflet` (`leaflet` e `leaflet/dist/leaflet.css` não resolvidos). O Chromium em cache iniciou com `PLAYWRIGHT_BROWSERS_PATH`, mas `npm run test:invalidation` não conseguiu acessar o Vite local: a rede do sandbox negou a conexão; uma tentativa elevada expirou.

## Revisão humana e dependências pendentes

- Revisar as expectativas rascunhadas em `ai-agent/tests/fixtures/gold_p0_reserved.json` antes de pontuar; manter a amostra fora dos ajustes enquanto isso.
- Validar os três relatos que falham para confirmar o esclarecimento esperado e a semântica da continuação.
- O oráculo de `GUARD-04` foi ajustado para aceitar os dois motivos de esclarecimento adequados; a execução da bateria completa continua usando a mesma pergunta sintética.
- Repetir o benchmark após estabilizar os 503; a melhor rodada pontuada é 5/6 e não atinge a meta de promoção.
- Disponibilizar publicação Gold v2 de teste, leitor autorizado e configuração de serviço para provar execução, números, auditoria e continuidade ponta a ponta.
- Completar a instalação local do frontend e permitir que o browser de teste alcance o Vite local para repetir a regressão visual.

Os skips Backend incluem integração que exige banco e publicação privados. Nenhuma alteração foi feita nos estados oficiais de requisitos IA no PRD.
