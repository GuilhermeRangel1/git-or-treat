# Amostras e provas técnicas da matriz — 02/11/2026

Escopo: IA-01/02/03/06, continuação na branch `fix/genai-prontidao-gold-local`. Integração executável e revalidação de casos Gold v2; os estados oficiais dos requisitos não mudam.

## Correção da seleção de amostras

O runner escolhia primeiro a última competência de receita/consumo e procurava valores nulos apenas nesse mês. A conferência somente leitura de todas as competências revelou amostras legítimas em meses anteriores. Os casos FAT-12/13/15 e CON-10 agora usam `COMPETENCIA_DA_AMOSTRA`: competência, município e classe são selecionados juntos, priorizando a competência mais recente que satisfaz a condição. O mês por extenso e o ano da pergunta vêm dessa mesma linha; nenhum parâmetro do mês mais recente é reaproveitado. Competência inválida falha antes da chamada pública.

FAT-15 agora exige ao menos um denominador observado e soma exatamente zero. A seleção anterior usava `COALESCE(SUM(...), 0)` e aceitava denominador inteiramente nulo como base zero. A correção preserva a distinção do dicionário e não altera cálculo, fonte, permissões ou cobertura do Assistente.

## Documentação e notebooks confrontados

- [Dicionário Gold](../dicionario_gold.md), seções 1 e cobertura: ausência de uma fonte pode produzir medida nula; nulo não é zero. Contagem de registros não certifica fechamento.
- [Silver_to_gold.ipynb](../../data-engineering/notebook/Silver_to_gold.ipynb): `agregacoes_faturamento` soma fontes separadas e preserva ausência; a célula de diagnóstico calcula tarifa somente com denominador presente e diferente de zero. A reconciliação das parcelas financeiras mantém grupos somente de leitura com receita nula. Nenhuma regra proíbe os casos de receita/consumo nulos em geral.
- [Cobertura_Declaracao.ipynb](../../data-engineering/notebook/Cobertura_Declaracao.ipynb): `DOMINIOS` contém apenas consumo/leituras e faturamento/faturas. Esse notebook não fornece declaração de fechamento para atendimento nem ocorrências.
- [Contrato de cobertura](../contracts/gold-cobertura-v1.md) e [prontidão](../gold-readiness.md): ausência de linha de continuidade não prova zero; zero de atendimento exige competência fechada e confirmação explícita.

## Resultados por caso

| Caso | Resultado desta rodada | Evidência e pendência |
| --- | --- | --- |
| FAT-13 | PASS na API pública Gold v2 | Amostra nula real encontrada em outra competência; HTTP 200 `needs_clarification`, sem número inventado. |
| CON-10 | PASS na API pública Gold v2 | Amostra nula real encontrada em outra competência; HTTP 200 `needs_clarification`, sem número inventado. |
| FAT-12 | SEM_AMOSTRA_NO_LOTE | Nenhum agregado município/classe/mês com receita observada e soma zero em todas as competências. |
| FAT-15 | SEM_AMOSTRA_NO_LOTE | Nenhum agregado com denominador observado e soma zero. Denominador nulo não serve como substituto. |
| INT-06 | SEM_AMOSTRA_NO_LOTE | Nenhuma linha com DEC nulo em todas as competências; cobertura de ocorrências também não está certificada. |
| INT-07 | SEM_AMOSTRA_NO_LOTE | Não há combinação alimentador/competência ausente entre os alimentadores e meses publicados; cobertura não certificada. Não criar alimentador fictício na Gold. |
| ATE-02 | SEM_AMOSTRA_NO_LOTE, caso opcional | Não há competência de atendimento fechada com zero confirmado. Não promover tabela vazia ou ausência de eventos a zero. |
| SEG-06 | Prova técnica separada aprovada | Teste PostgreSQL de sessão/SQL/permissões/falhas e runtime Gold; não é resposta numérica do lote real. |
| SEG-07 | Prova técnica separada aprovada | Gate de segurança e perguntas legítimas: suíte específica aprovada, sem novas chamadas externas. |

Rodada pública `20261102T121234_564139Z`: FAT-13 e CON-10 passaram em 13,87 s e 14,06 s. Rodada `20261102T121636_068419Z`: os cinco restantes confirmaram ausência de amostra antes da consulta de resposta e da síntese. Sessões/contas temporárias removidas nos dois encerramentos. Artefatos privados ficam ignorados em `work/genai-edge-validation`; nenhuma linha bruta ou credencial é versionada. Não houve nova ingestão, alteração de grants ou chamadas adicionais ao Gemini nesses casos de esclarecimento/sem amostra.

## Verificações e limites

- `python -m pytest ai-agent/tests/test_gold_domain_scenarios.py ai-agent/tests/test_gold_domain_runner_integration.py -q --tb=short`: 274 passaram. Inclui mês da amostra, competência inválida e execução do SQL de seleção que distingue zero de nulo.
- Seleção final dos quatro arquivos `test_gold_domain_scenarios.py`, `test_gold_domain_runner.py`, `test_gold_domain_runner_integration.py` e `test_gold_domain_runner_postgres.py`: 316 passaram, 1 skip por DSN opt-in não configurado para a prova específica do runner. As duas consultas de amostra nula foram exercitadas no PostgreSQL real pela rodada pública descrita acima; a prova Backend PostgreSQL abaixo é distinta desse teste opcional.
- Em ambiente sem configuração privada, `python -m pytest .../tests/test_safety_gate.py .../tests/test_gold_runtime.py -q -p anyio --tb=short`: 1.751 passaram. Provas determinísticas; sem fonte/modelo real.
- Backend `python -m pytest -q -p no:cacheprovider tests/test_genai_session_postgres.py --tb=short`: 1 passou em 102,35 s, com aviso Starlette preexistente. PostgreSQL 16 descartável sem porta pública ou volume, papéis preparados pelo script de CI e container removido ao terminar. Modelo/transporte de integração controlados, SQL/sessão/ACL/auditoria reais. A prova chama `assert_first_question_failures` e verifica falha de fonte, modelo e auditoria, revogação e recuperação. Duas expectativas de apresentação de atendimento foram atualizadas de `2.0/3.0 protocolos` para o texto legível; unidade `protocolos` continua explicitamente conferida no contexto.
- Tentativas iniciais da prova falharam por dependência `sqlglot` ausente na imagem Backend e configuração GenAI privada herdada; após isolar variáveis/mascarar `.env`, o teste revelou as expectativas antigas acima. A execução final usa dependência declarada em `ai-agent/pyproject.toml`, configuração limpa e modelo controlado. Nenhuma dessas tentativas altera a publicação usada pelo portal.
- `python ai-agent/scripts/run_gold_domain_scenarios.py --dry-run`: 57 IDs válidos; Ruff por módulo e `git diff --check` passaram.

Os resultados históricos de 57 casos continuam preservados; esta rodada revalida os sete casos de amostra e as provas técnicas separadas, sem declarar uma nova matriz completa ou encerrar os seis requisitos obrigatórios. Os cinco casos ainda sem amostra mantêm seu aceite Gold pendente. Fonte inexistente e cobertura não certificada não são resolvidas alterando uma classificação.
