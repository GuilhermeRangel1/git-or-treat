# TSQL-05 — conferência por caso e aceite pendente

Data: 06/11/2026. Branch `feat/genai-text-to-sql`. IDs IA-01/02/08, estados oficiais preservados.

O gerador foi corrigido em três pontos: precedência da pergunta atual e formato de competência SQL na f1-10; LIMIT literal na f1-11; cobertura independente das duas janelas comparadas na f1-12. O runner agora aceita `--max-output-tokens`, preserva o teto padrão e recusa retomada com limite diferente. O limite de 1.536 tokens permitiu ampliar a observação dentro do orçamento.

## Evidência por caso

Todos os 40 IDs têm uma observação correta após correções: 29 candidatos foram revisados pelo Backend e executados em PostgreSQL 16 artificial contra SQL/cálculos independentes; os outros 11 coincidiram com os estados esperados de esclarecimento/limitação. A última falha corrigida foi F1-C07: a referência de 2025 não estava na cobertura e deveria gerar esclarecimento, não SQL parcial. O Backend recusou os candidatos inválidos anteriores.

**Não é uma matriz uniforme da versão final.** A seleção tem proveniência f1-10/11/12 por caso; capturas inválidas e indisponibilidades anteriores continuam preservadas. Não se publica essa seleção como acurácia 40/40 da f1-12. A comparação de regressões com os 40 casos na versão final continua necessária para concluir TSQL-05.

Artefatos privados em `work/`:

- `text-to-sql-f1-final-case-capture.json`: seleção de candidatos e proveniência por caso.
- `text-to-sql-f1-final-case-review.json`: intenções e diferenças por caso, versões e limites.
- `text-to-sql-f1-final-case-numeric.json`: 29 `exact_reference_match`, 11 `expected_non_query_state`, nenhuma divergência nessa seleção.
- Capturas `f1-10-remaining`, `f1-11-ranking`, `f1-11-retry-*`, `f1-11-second-*`, `f1-11-coverage` e `f1-12-coverage`: tentativas originais preservadas, inclusive 503/429.

Reprodução sem nova chamada remota: em `backend/`, defina `TEST_TEXT_TO_SQL_URL` exclusivamente para PostgreSQL descartável com banco `text_to_sql_f1_test` e execute:

```powershell
python -m tests.text_to_sql_f1_baseline --baseline ../ai-agent/reports/text-to-sql-f1-baseline.json --candidate-observations ../work/text-to-sql-f1-final-case-capture.json --output ../work/final-case-numeric-replay.json
```

O container artificial foi removido ao final. Nenhum SQL gerado nesta continuação foi executado contra Gold real. Não houve ativação do caminho público.

## Orçamento e verificações

A pessoa usuária manteve US$ 2. Foram reconciliadas reservas de saída somente quando havia contagens válidas de tokens totais e de entrada: todos os tokens restantes foram tratados ao preço de saída, sem assumir pensamento ausente como zero. Reservas de entrada e tentativas sem uso conhecido foram mantidas. Uma reconciliação provisória que liberava entrada foi substituída conservadoramente pela liberação apenas de saída. A reserva final US$ 1,945078 inclui essa correção; não ultrapassou o teto. Planilhas JSON privadas: `text-to-sql-budget-reconciled-final.json` e cost guards das capturas subsequentes. Referência de contagem: [documentação oficial Gemini](https://ai.google.dev/gemini-api/docs/generate-content/tokens), consultada via Context7 em 06/11/2026. São estimativas conservadoras com preço pago, não fatura; Free Tier informado pela pessoa usuária.

Em `ai-agent/`, 71 testes de gerador/contrato/captura/telemetria passaram; Ruff passou nos quatro arquivos alterados. Revisor: agente local, sem revisão independente. Próximo aceite: matriz completa f1-12, incluindo os controles, com orçamento que comporte a rodada inteira. O saldo atual não comporta essa matriz; TSQL-05 segue aberta nesse critério.
