# IA-08 — avaliação automática ampliada

**Estado: Em validação.** A avaliação está na branch `feat/genai-avaliacao-ampliada`, baseada em `develop` no merge `8e595bc`. A amostra Gold e a revisão humana têm critérios próprios.

O [runner existente](../../ai-agent/tests/test_genai_regression.py) conserva as execuções sintética e de linguagem. O modo ampliado reúne perguntas e insights da composição sintética, planejamento Gold v2 com cobertura artificial e planejamento/síntese pela borda HTTP Gold v2 com evidências artificiais. As 16 formulações de holdout são identificadas separadamente. Antes da ampliação, faltavam uma matriz numérica com expectativas independentes, comparação por categoria e uma forma de incluir as fronteiras do Backend no relatório.

O [conjunto numérico](../../ai-agent/tests/fixtures/gold_evaluation_numeric.json) fixa perguntas, filtros, janelas, estados, agregados, expectativas e a tolerância zero para valores artificiais. Cobre Receita, Consumo, Atendimento, DEC/FEC, zero observado, evidência ausente, lote divergente, falha de provedor e recorte não autorizado. Perguntas sobre energia faturada e energia recuperável verificam que a resposta não infere esses valores de consumo medido. As fixtures legadas preservam casos de escrita, dados pessoais e injeção.

## Reproduzir a comparação

Em `ai-agent/`, com as dependências de desenvolvimento instaladas:

```powershell
python -m tests.test_genai_regression --expanded --baseline reports/expanded-regression-baseline.json --output ../work/evaluation/expanded-regression-report.json
python -m pytest -q tests/test_expanded_evaluation.py tests/test_gold_language_evaluation.py tests/test_genai_regression.py
```

O comparativo mostra denominadores antes e depois por categoria e checks individuais. O controle técnico adotado bloqueia caso ou check omitido, perda de um acerto, nova falha, mudança de falha conhecida e mistura de escopos/conjuntos. As três falhas conhecidas permanecem no denominador, em cenários sintéticos legados de interrupções por geografia ou classe. Uma alteração intencional do conjunto exige revisar e registrar um novo baseline. A pessoa usuária aprovou a amostra e esse limiar para a entrega local em 04/11/2026.

O CI usa os testes existentes do Backend para gerar JUnit temporário e extrai somente as fronteiras de autorização, cobertura e permissões. O relatório público contém IDs opacos, categorias e resultados booleanos. A configuração não carrega a chave local. Para repetir a extração, rode os três módulos selecionados em `backend/` e passe o JUnit ao runner no diretório `ai-agent/`:

```powershell
python -m pytest -q tests/test_genai_continuity_observed.py tests/test_genai_profile_access.py tests/test_platform_authorization.py --junitxml=../work/evaluation/backend-quality.private.xml
python -m tests.test_genai_regression --backend-junit ../work/evaluation/backend-quality.private.xml --baseline reports/backend-evaluation-baseline.json --output ../work/evaluation/backend-evaluation.json
```

## Evidências separadas

| Escopo | Resultado observado |
| --- | --- |
| Composição offline e bordas HTTP | 160/163, três falhas legadas conhecidas. Comparativo sem nova regressão. Inclui 48 formulações Gold e 14 casos numéricos e de segurança com evidência artificial. |
| Backend em Docker | 118 testes dirigidos passaram, incluindo o executor e permissões. O relatório das fronteiras selecionadas registra 44 testes e uma checagem de presença das três suítes, 45/45. |
| Provedor real com agregados artificiais | `--expanded --real-sample 6`, com `GENAI_RUN_LIVE_SMOKE=1`, chave local e sem fallback de provedor. Gemini Flash Lite passou em 6/6, em 69.484 ms no total. O custo financeiro ficou indisponível. O relatório local fica fora do CI público. |
| Gold privada | Receita, DEC e FEC da amostra WEB-10 reconciliados novamente com SQL independente na mesma publicação Gold v2. DEC e FEC coincidiram com os numeradores divididos pela população positiva, tolerância absoluta `1e-8`. A guarda atual aceitou o recorte observado e o leitor restrito manteve acesso aos índices, com cobertura detalhada e cadastro bloqueados. |

Para repetir a conferência privada, use o roteiro e a publicação descritos na [evidência WEB-10](2026-11-01-web10-perfis-evidencias.md). Em transações somente leitura, compare a soma de `diagnostico_receita.receita_total_reais` no recorte com o controle anterior. Use a conexão operacional da prontidão para os numeradores e denominador de `indicadores_dec_fec` e para a guarda de `cobertura_dominios`. Compare `DEC` e `FEC` sob o leitor dedicado na mesma publicação e confira as permissões pelo catálogo PostgreSQL. Os resultados booleanos foram preservados em `work/evaluation/gold-reconciliation.json`; as respostas históricas e os valores permanecem privados. A rodada de reconciliação não solicitou novas respostas ao Gemini com dados Gold.

A prova privada detectou uma regressão do merge WEB-10. A guarda de cobertura tentava ler metadados com a credencial restrita do executor. A verificação agora roda na conexão operacional de prontidão, em snapshot somente leitura da publicação esperada. O executor usa o leitor dedicado e confirma a mesma publicação antes da consulta de valores. A regressão da composição cobre o aceite e o bloqueio e não exige ampliar permissões do leitor.

## Revisão de utilidade e aceite

| Estrato da amostra | Conferência para Dados e Negócio |
| --- | --- |
| Receita e consumo | A resposta mantém unidade, período, filtro e origem. `NUM-REV` soma 12,50 e 7,50, `NUM-CONS` soma 100,25 e 49,75. |
| Continuidade | DEC/FEC observados preservam o recorte e a ressalva pública. Cobertura parcial e linhagem divergente bloqueiam a exceção. |
| Ambiguidade e ausência | Energia faturada e energia recuperável pedem esclarecimento. Ausência de evidência permanece distinta de zero. |
| Segurança | Escrita, injeção e dados pessoais são recusados. O perfil sem acesso à dimensão não recebe resposta nem evidência. |

A revisão humana estratificada e o limiar local foram aprovados pela pessoa usuária em 04/11/2026. Resta observar a primeira publicação sanitizada no CI da branch para concluir o cartão.


## Revalidação final — 04/11/2026

- Suíte GenAI completa em ambiente sem carregar `.env` local, 4.488 passaram e 5 skips de integração opt-in. Depois dela, três regressões de envelope do avaliador foram adicionadas e passaram na suíte dirigida final de 52 testes. A primeira execução carregou token local e uma expectativa de serviço sem token falhou. A execução isolada também revelou colisão de diretório do runner Gold no Windows, corrigida com criação atômica de diretório exclusivo.
- Matriz oficial com 57 IDs válidos. INT-01 e INT-02 agora consultam a elegibilidade observada e comparam número, publicação e ressalva quando o recorte é elegível. Em caso contrário, a expectativa de bloqueio é preservada. 286 testes dirigidos do runner, matriz e avaliador passaram.
- Ruff completo, compileall, YAML do workflow, verificador documental do CI com links em 180 documentos e `git diff --check` aprovados.
- A amostra e o limiar local foram validados pela pessoa usuária. Os três casos legados com falha conhecida seguem expostos no baseline como falhas.

- Revisão final separada por padrões e especificação concluída. Standards sem achados materiais. O achado Spec de envelope malformado foi corrigido com tratamento por caso e regressões para resposta vazia e plano inválido. A rodada dirigida posterior passou em 52 testes, e o comparativo preservou 160/163 com as três falhas conhecidas.
- Fluxo Backend ampliado para prazos, falhas HTTP, cobertura, execução e permissões, 118 testes aprovados com um aviso preexistente Starlette/httpx. Relatório de provedor real fora de `work/` foi recusado antes de qualquer chamada.
- Trello atualizado para 9/10. O item de publicação sanitizada no CI aguarda autorização de commit e push. A pessoa usuária pediu revisão antes de publicar, portanto a branch segue com alterações locais.
