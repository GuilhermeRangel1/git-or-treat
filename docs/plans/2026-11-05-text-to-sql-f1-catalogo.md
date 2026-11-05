# TSQL-03 — conferência do catálogo Gold v2 para a F1

Data: 05/11/2026. Escopo revisado: `billing.revenue` na primeira fatia Text-to-SQL. A inspeção não leu linhas do lote Gold nem credenciais.

## Fonte e cópias

- Fonte de autoria do mapeamento semântico/físico: `ai-agent/app/profiles/grid360_gold_mapping.py`, validada junto ao perfil de `grid360_gold.py` e aos requisitos de prontidão v2.
- Artefato de execução do Backend: `backend/app/catalogs/gold_v2.json`. Agora é gerado de forma reproduzível com `python scripts/generate-gold-v2-catalog.py`; CI/teste confere ausência de drift com `--check`.
- O Backend carrega o JSON e confere esquema, versões, capacidades, grão, colunas, tipos e escala contra `backend/app/models/gold_v2.py`. Os testes AI→Backend também serializam o schema dos modelos e chamam `validate_mapping`.
- `docs/dicionario_gold.md` define o significado de negócio; `docs/contracts/gold-csv-v2.md` define pacote, inventário e grão publicado. `dictionary_gold.toml` e o mapeamento v1 não são usados como fonte física da Gold v2. Evita-se promover compatibilidade v1 como fallback.

## F1 conferida

`billing.revenue` / capacidade `faturamento.receita`; schema/tabela `gold_v2.diagnostico_receita`; coluna temporal `competencia` (texto mensal `YYYY-MM`); medida `receita_total_reais` (`Numeric(38,2)`, decimal/R$); agregação aditiva SUM; janela mensal/anual limitada a 1.830 dias. Grão completo: competência, município, classe de consumo, subgrupo tarifário, bandeira tarifária e GD. O total soma todas as linhas desse grão; não deve descartar subgrupo, bandeira ou GD para deduplicar.

Definição documentada: faturamento elegível inclui faturas sem leitura e **não significa valor pago**. Nulo é ignorado pelo SUM; valor todo nulo/sem evidência não vira zero. Zero, ausência, estorno e cobertura não certificada continuam distintos. Dimensões de cadastro descrevem cadastro atual, sem SCD/histórico presumido. Contexto do gerador expõe somente tabela/colunas autorizadas da métrica, município e classe na F1; exclui identificador individual, cadastro pessoal e tabelas operacionais. F1 não permite JOIN.

Conferências correlatas já protegidas por testes: razões usam numerador/denominador compatíveis (não média de médias); DEC/FEC ficam no grão de alimentador e mês, sem soma entre períodos; janela e cobertura exigem competências completas; perfil, versão física `gold-csv-v2`, mapeamento `gold-catalog-v2`, readiness `gold-readiness-v2`, schema `gold_v2` e unidade de envelope permanecem conceitos distintos.

## Provas executadas

- `python scripts/generate-gold-v2-catalog.py --check`: passou.
- AI Agent: `python -m pytest tests/test_gold_catalog_v2.py tests/test_gold_catalog_backend_contract.py -q -p no:cacheprovider --tb=short`: 57 passaram na rodada final, incluindo a checagem do gerador.
- Backend: `../work/p0-validation-venv/Scripts/python.exe -m pytest tests/test_gold_catalog.py tests/test_genai_sql_context.py -q -p no:cacheprovider --tb=short`: 47 passaram.

## Limite e pendências

Isto prova consistência entre metadados versionados, mapeamento, artefato JSON e modelos instalados, não inspeção `information_schema` da instância Gold publicada. O contexto da geração declara explicitamente `schema_basis=installed_models_and_versioned_catalog_not_live_database`. Não havia publicação Gold local ativa disponível nesta rodada. TSQL-03 permanece parcial até conferir, sem dados de linhas, metadados da instância aprovada e grants/permissões do papel leitor; aplicar migração de teste não seria equivalente à publicação real.

Também fica para fases posteriores a catalogação de cardinalidades entre fatos para JOINs futuros. Tabela existente não concede JOIN: F1 permanece fechado a uma tabela e sem resolver combinações por suposição.
