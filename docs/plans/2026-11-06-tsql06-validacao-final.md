# TSQL-06 — validação final do subconjunto F1

Data: 06/11/2026. Branch: `feat/genai-text-to-sql`, após `4e71fc6`.
Estado: concluída no escopo de aprovação determinística F1 e integração interna com executor.

## Caminho comprovado

`prepare_sql_candidate` → `admit_sql_candidate` → `review_sql_structure` / `review_sql_semantics` → `revalidate_sql_admission` → `execute_sql_admission` → snapshot PostgreSQL somente leitura. Ainda não existe coordenação pública generativa; essa integração pertence à TSQL-07 e seguintes.

## Regras e limites

- Uma fonte física: `gold_v2.diagnostico_receita`; receita aditiva, dimensões e competências autorizadas pelo contexto Backend. A resolução de aliases/colunas é inequívoca nesse único escopo. CTEs, subconsultas correlacionadas, JOIN, shadowing por escopos aninhados e outras fontes são rejeitados, sem habilitação implícita futura.
- Allowlist positiva de nós e argumentos AST; somente SUM e comparação por dois SUM FILTER com diferença verificável. Casts, funções externas, catálogos, sequências, razões, percentuais e multiplicação por JOIN não pertencem ao subconjunto e são recusados. Não há igualdade obrigatória com templates SQL.
- Parâmetros nomeados extraídos da AST, sem literais de filtros; round-trip PostgreSQL e uso real de placeholders psycopg. Colunas e dependências vêm da AST, não de listas declaradas pelo modelo.
- Períodos, filtros, dimensões, agregação e ranking conferidos contra intenção estruturada; cobertura de ambas as janelas e capacidade `faturamento.receita` disponíveis. Isso não demonstra compreensão da pergunta natural.
- A exceção `observed_uncertified` da ADR-0024 não se aplica à receita F1. Continuidade e outros domínios não recebem liberação transitiva.
- Máximo de 512 nós, profundidade 32, tamanho limitado pelo contrato, ranking 1–100, materialização até 100 linhas/16 KiB, prazo SQL até 5 s e prazo global. Essa política limita recursos e recusa construções amplificadoras; não estima custo via EXPLAIN nem garante latência sob qualquer carga.
- Admissão liga contexto, identidade/escopo, SQL canônico, parâmetros, catálogo, política, publicação, prontidão e prazo. É refeita no uso sem renovar validade. Snapshot confere publicação, schema/grants e identidade efetiva do leitor.

## Correções desta rodada

A fixture PostgreSQL antiga tinha só quatro colunas e passou a ser corretamente recusada após a introdução do guard físico. Ela agora usa o modelo Gold v2 completo com grão real e apenas registros artificiais. A prova encontrou um bug real: SQLAlchemy Float herda Numeric e PostgreSQL reflete precisão binária 53; o guard comparava essa precisão com escala decimal. A comparação decimal agora exclui Float, mantendo a checagem de família física e precisão/escala de Numeric.

## Verificações reproduzíveis

Em `backend/`, com PostgreSQL 16 novo descartável e `TEST_TEXT_TO_SQL_URL` apontando exclusivamente para `text_to_sql_f1_test`:

```powershell
python -m pytest tests/test_genai_sql_executor_postgres.py tests/test_genai_sql_structure.py tests/test_genai_sql_parameters.py tests/test_genai_sql_semantics.py tests/test_genai_sql_comparison.py tests/test_genai_sql_admission.py tests/test_genai_sql_executor.py tests/test_genai_sql_live_catalog.py -q -p no:cacheprovider --tb=short
python -m ruff check app/services/genai_sql_live_catalog.py tests/test_genai_sql_executor_postgres.py
python -m compileall -q app/services/genai_sql_live_catalog.py tests/test_genai_sql_executor_postgres.py
```

Resultado: 152 testes passaram em 4,38 s, incluindo 13 PostgreSQL; Ruff e compileall passaram. A primeira execução reproduziu a fixture incompatível; a segunda revelou a comparação Float/Numeric. Repetição final aprovada após as correções.

Os 13 casos PostgreSQL cobrem total 150.03, comparação 150.03/80.00/diferença 70.03, cursor server-side, READ ONLY, recusa de DELETE, timeout com rollback, sete mutações (SQL, parâmetro, identidade, publicação lógica, política, expiração e digest), grant revogado e drift físico. Um teste adicional confirma que prontidão `observed_uncertified` de DEC/FEC não autoriza admissão de faturamento: a receita precisa estar `available`, antes de consultar metadados Gold. As sete mutações não enviam nenhuma instrução ao leitor; drift/grant permitem apenas metadados, sem executar o candidato. Pool sem checkout ao final.

## Limites do aceite

Metadados e prontidão da admissão usam `Environment` artificial; snapshot, introspecção física/grants, execução, streaming e timeout são reais no PostgreSQL descartável. Isso encerra a matriz do validador F1, mas não a admissão operacional completa, o chat autenticado, o portal, a síntese generativa ou o aceite de dados Gold reais. Requisitos oficiais IA/WEB permanecem com seus estados anteriores. Não houve chamada Gemini nem consumo adicional do teto de API. Banco do portal preservado; container descartável removido ao final.
