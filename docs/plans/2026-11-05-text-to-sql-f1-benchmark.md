# TSQL-02 — benchmark F1 e linha de base

Data: 05/11/2026. Base commit usada: `3a739a89d9fc9e0962568a20e1c9c2adc46e2c22`. A árvore tinha alterações locais; o relatório guarda SHA-256 do benchmark, referências, avaliador e módulos GenAI. Os JSON por caso são artefatos de reprodução desta rodada.

## Limite da prova

Perguntas e publicação Gold são artificiais. A primeira execução mede a borda HTTP ASGI do planner antigo com `FakeModelAdapter`; não chama Gemini, sintetizador, API pública, sessão de usuário ou prontidão de publicação real. A segunda compila o SQL legado e executa no PostgreSQL 16 efêmero, comparando com SQL manual e cálculo Decimal independente. O avaliador de candidatos aceita capturas futuras, revisa AST/intenção, executa apenas no banco descartável e confere valores/oráculo. Isso torna a comparação reproduzível, mas não converte a linha de base determinística em benchmark de respostas Gemini.

## Resultado observado

- 40 casos de desenvolvimento: 32 perguntas/variações quantitativas e 8 controles de cobertura, ambiguidade e escopo.
- Planejamento: 17 casos coincidiram nos campos que o contrato antigo expõe; 23 divergiram; 21 divergências foram de estado e duas foram operação (comparação mensal produzida para uma pergunta de total).
- Sem plano no fluxo antigo: 27 casos. Não são 27 recusas indevidas: incluem pedidos que deveriam esclarecer/recusar e lacunas de cobertura. A conferência por caso está no relatório JSON.
- SQL legado contra referência: 8 coincidências exatas, 5 divergências e 27 não executados porque não houve plano.
- Falhas numéricas reproduzíveis: F1-03 retorna seis linhas mensais em vez do total R$ 950; F1-02 interpreta o ano incompleto como junho (R$ 200) em duas paráfrases; F1-05, em uma paráfrase, retorna apenas janeiro e junho em vez de seis linhas.
- 52 testes passaram em PostgreSQL 16 descartável: consultas de referência, ano parcial/completo, zero/nulo/ausência, estorno, contrafactuais de grão/cidade/período, grupo sem base comparativa, congelamento e adaptador de candidatos (inclui intenção errada com SQL estruturalmente válido e SQL de escrita rejeitado).
- Chamadas ao provedor: zero; tokens e custo do Gemini não se aplicam/não foram medidos. Latência ASGI local é registrada caso a caso, mas não representa latência real do modelo. Meta futura: uma chamada limitada a 4096 tokens; teto monetário continua requisito operacional antes da promoção com provedor real.

## Integridade e exposição

As 40 perguntas avaliadas são desenvolvimento e estão expostas. O conjunto de oito perguntas autorais reservado está versionado separadamente, não foi executado e não é holdout independente ou secreto. A fixture de congelamento impede alterações silenciosas às perguntas e referências. Metas fixadas: acerto de 100% dos campos F1 e dos números, zero execução não autorizada, zero recusa falsa, zero esclarecimento desnecessário e zero regressão; prazo total 60 s e SQL 5 s. São critérios de promoção, não resultados desta linha de base. Casos de mês máximo, percentual e pedido causal composto ficam no inventário de expansão.

## Matriz por caso

| Caso | Interpretação observada | SQL legado |
|---|---|---|
| F1-01-V0 | `observed_fields_match`; campos observados coincidem | `exact_reference_match` |
| F1-01-V1 | `observed_fields_match`; campos observados coincidem | `exact_reference_match` |
| F1-01-V2 | `observed_fields_match`; campos observados coincidem | `exact_reference_match` |
| F1-01-V3 | `divergent`; status | `not_executed_no_plan` |
| F1-02-V0 | `divergent`; status | `divergent` |
| F1-02-V1 | `divergent`; status | `divergent` |
| F1-02-V2 | `observed_fields_match`; campos observados coincidem | `not_executed_no_plan` |
| F1-02-V3 | `observed_fields_match`; campos observados coincidem | `not_executed_no_plan` |
| F1-03-V0 | `observed_fields_match`; campos observados coincidem | `divergent` |
| F1-03-V1 | `divergent`; operation | `divergent` |
| F1-03-V2 | `divergent`; status | `not_executed_no_plan` |
| F1-03-V3 | `divergent`; status | `not_executed_no_plan` |
| F1-04-V0 | `divergent`; status | `not_executed_no_plan` |
| F1-04-V1 | `divergent`; status | `not_executed_no_plan` |
| F1-04-V2 | `divergent`; status | `not_executed_no_plan` |
| F1-04-V3 | `divergent`; status | `not_executed_no_plan` |
| F1-05-V0 | `observed_fields_match`; campos observados coincidem | `exact_reference_match` |
| F1-05-V1 | `divergent`; status | `not_executed_no_plan` |
| F1-05-V2 | `divergent`; operation | `divergent` |
| F1-05-V3 | `observed_fields_match`; campos observados coincidem | `exact_reference_match` |
| F1-06-V0 | `divergent`; status | `not_executed_no_plan` |
| F1-06-V1 | `divergent`; status | `not_executed_no_plan` |
| F1-06-V2 | `divergent`; status | `not_executed_no_plan` |
| F1-06-V3 | `divergent`; status | `not_executed_no_plan` |
| F1-07-V0 | `divergent`; status | `not_executed_no_plan` |
| F1-07-V1 | `observed_fields_match`; campos observados coincidem | `exact_reference_match` |
| F1-07-V2 | `divergent`; status | `not_executed_no_plan` |
| F1-07-V3 | `divergent`; status | `not_executed_no_plan` |
| F1-08-V0 | `divergent`; status | `not_executed_no_plan` |
| F1-08-V1 | `divergent`; status | `not_executed_no_plan` |
| F1-08-V2 | `observed_fields_match`; campos observados coincidem | `exact_reference_match` |
| F1-08-V3 | `observed_fields_match`; campos observados coincidem | `exact_reference_match` |
| F1-C01 | `observed_fields_match`; campos observados coincidem | `not_executed_no_plan` |
| F1-C02 | `observed_fields_match`; campos observados coincidem | `not_executed_no_plan` |
| F1-C03 | `observed_fields_match`; campos observados coincidem | `not_executed_no_plan` |
| F1-C04 | `observed_fields_match`; campos observados coincidem | `not_executed_no_plan` |
| F1-C05 | `observed_fields_match`; campos observados coincidem | `not_executed_no_plan` |
| F1-C06 | `divergent`; status | `not_executed_no_plan` |
| F1-C07 | `observed_fields_match`; campos observados coincidem | `not_executed_no_plan` |
| F1-C08 | `divergent`; status | `not_executed_no_plan` |

## Comandos reproduzíveis

Executar de `ai-agent` com o PostgreSQL de teste `text_to_sql_f1_test` em `TEST_TEXT_TO_SQL_URL`:

```powershell
python -m tests.text_to_sql_f1_baseline --output reports/text-to-sql-f1-baseline.json
python -m pytest tests/test_text_to_sql_f1_reference.py tests/test_text_to_sql_f1_benchmark.py -q -p no:cacheprovider --tb=short
```

De `backend`, usando o mesmo URL artificial:

```powershell
..\work\p0-validation-venv\Scripts\python.exe -m tests.text_to_sql_f1_baseline --baseline ..\ai-agent\reports\text-to-sql-f1-baseline.json --output ..\ai-agent\reports\text-to-sql-f1-sql-baseline.json
..\work\p0-validation-venv\Scripts\python.exe -m pytest tests/test_text_to_sql_f1_benchmark.py -q -p no:cacheprovider --tb=short
..\work\p0-validation-venv\Scripts\python.exe -m tests.text_to_sql_f1_baseline --baseline ..\ai-agent\reports\text-to-sql-f1-baseline.json --output ..\work\text-to-sql-f1-benchmark-contexts.json --export-contexts
```

Depois de coletar candidatos fora do baseline, forneça JSON com `benchmark_sha256` idêntico ao relatório de planejamento e mapa `candidates` indexado por ID; rode o primeiro comando Backend com `--candidate-observations caminho.json`. Capturas não devem conter credenciais, linhas reais ou payloads brutos do provedor.
