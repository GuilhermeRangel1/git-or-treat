# HNLU — integração real Gemini + Gold v2 — 2026-11-07

## Escopo e ambiente

Prova local na branch `feat/nlu-generativa-hibrida`, usando o projeto Docker isolado `hnlu-validation`. O agente foi iniciado com `GENAI_INTENT_MODE=gemini`; a configuração local confirmou provedor Gemini e chave presente sem exibi-la. A requisição autenticada passou pelo endpoint público do Backend, planejamento interno, publicação Gold v2, executor somente leitura e síntese do GenAI. O teste não altera estado nem habilita escrita.

Publicação observada: `gold-csv-v2`, lote `GOLD_20261103T173853Z_76c37784`, publication ID `5cff9e92-c1e8-4b52-9cb8-787636129ecd`, fingerprint `d1e9d3cb4455895155c09da82865807f5f83a608f832246be91e08063d158856`.

## Caso executado

- Pergunta: “Quanto foi o faturamento total em junho de 2026?”
- Resultado HTTP: `200`, estado `answered`, `is_demo=false`, fonte `gold.local`.
- Interpretação: `billing.revenue`, unidade R$, período `2026-06-01` a `2026-06-30`, sem filtros.
- Resposta: total em reais para junho de 2026; o valor exato foi comparado localmente e não é publicado neste relatório.
- Referência independente, executada diretamente no PostgreSQL Gold v2 local com o papel leitor: `SELECT SUM(receita_total_reais) FROM gold_v2.diagnostico_receita WHERE competencia = '2026-06';`. O total coincide exatamente com a resposta da API; valores Gold reais não são incluídos no artefato versionado.
- O leitor tem `SELECT` somente nas colunas autorizadas da tabela; a verificação de privilégio de tabela retorna falso, e `has_column_privilege` confirma leitura de `competencia` e `receita_total_reais`. Nenhum grant foi ampliado.
- Correlação de auditoria: `a9983cea9c154cd8b076315eca1d52bb`. A trilha registra planejamento Gemini admitido, plano `billing.revenue`, uma linha de evidência Gold, síntese concluída e resposta concluída. Cada etapa mostra uma chamada de modelo na interpretação e uma na síntese; nenhum conteúdo livre foi incluído no relatório.

## Conclusão e limites

Esta execução satisfaz a prova mínima HNLU-04 de integração real Gemini → plano validado → executor Gold v2 → evidência → síntese, para uma pergunta de faturamento mensal suportada. É uma amostra de um caso: não demonstra cobertura de classes, rankings, períodos relativos, domínios além de faturamento, estabilidade estatística ou promoção do modo Gemini. O endpoint de API foi validado; inspeção visual/automação do navegador não foi executada, portanto HNLU-08 continua aberto.

O teste usou conta local de apresentação e a agregação Gold autorizada para este ambiente. O modelo de interpretação recebeu pergunta e metadados autorizados do catálogo/cobertura; o modelo de síntese recebeu a evidência agregada da resposta (um total), não linhas brutas da tabela. Não foram enviados PDF, credenciais ou dados pessoais. A chave permanece somente em `.env`, ignorado pelo Git.
