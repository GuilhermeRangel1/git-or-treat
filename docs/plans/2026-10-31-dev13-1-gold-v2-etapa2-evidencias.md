# DEV-13.1 — etapa 2: revisão semântica dos leitores Gold v2

Data: 31/10/2026. Branch: `dev13.1`. Escopo: mapear grãos, filtros, agregações e ausências do contrato físico v2 aos consumidores analíticos do Backend; não ativar a fonte real.

## Mudanças

- **Panorama:** receita e consumo usam `receita_base_comparavel_reais` e `consumo_base_comparavel_kwh` em KPI, preço, comparação e série. Totais independentes não são usados como fallback. As fórmulas e definições da resposta identificam a base comparável.
- **Contagem de UCs faturadas:** `ucsFaturadasNoMes` retorna indisponível e nulo. A Gold publica uma contagem distinta por linha dimensional, sem identificadores que permitam deduplicar UCs ao agregar linhas; somar as contagens pode repetir uma UC. O contrato e o guia do Backend registram essa limitação.
- **Fila de inspeção:** `motivo_prioridade` alimenta o motivo da API. O item inclui `posicao_fila_inspecao`; no Gold, a ordenação padrão é posição ascendente, aplicada no banco antes da paginação, com desempate por UC. Ordenação por categoria textual e por UC continuam explícitas. O caminho sintético conserva o padrão anterior.
- **Recuperação:** referência, intervalo, estado e método v2 são preservados como evidência. A energia individual permanece nula e a explicação deriva de `estado_estimativa_recuperacao`; médias históricas não são extrapoladas para uma UC.
- **Operação:** revisão sem alteração de código. Os agregados respeitam o grão alimentador/mês, aplicam filtros aos numeradores e mantêm elegibilidade separada para DEC e FEC; ausências, denominador inválido/variável e competências sem linha continuam limitando os indicadores conforme o contrato.

Execução por subagentes GPT-6 Luna/high e revisão pelo agente principal. Nenhum decoder ou tela frontend foi alterado nesta etapa.

## Verificações

Ambiente de teste criado para esta execução: PostgreSQL 16 descartável, sem porta publicada nem volume, em rede temporária isolada; bancos `grid360_analytics_test` e `grid360_orders_test`; papel `grid360_test` sem superusuário. O contêiner, a rede e os bancos temporários foram removidos após a execução. Fixtures artificiais; nenhum CSV Gold real ou banco local do projeto foi usado.

```text
python -m pytest -q --tb=short -p no:cacheprovider tests/test_gold_context_v2.py tests/test_gold_inspection_repository.py tests/test_gold_analytics_postgres.py tests/test_gold_operations_http_postgres.py tests/test_gold_inspections_orders_postgres.py tests/test_panorama.py tests/test_operations_dev08.py tests/test_operations_summary.py tests/test_inspection_queue_dev05.py
```

Resultado: **130 passaram**, 1 aviso preexistente Starlette/httpx, 14,06 s. `git diff --check`: passou. Ruff não executado: a imagem Backend temporária não contém o módulo `ruff` (`No module named ruff`). As falhas de fixture encontradas nos ensaios iniciais foram corrigidas antes da execução final.

## Limites e próxima etapa

Etapas 1 e 2 concluídas tecnicamente; não concluem DEV-13.1 nem requisitos WEB/DE. A API continua sem ativação Gold nesta etapa. A etapa 3 precisa ativar a fonte e validar respostas contra o lote real `GOLD_20261031T020143Z_fd69c375`, depois de verificar que a configuração e a publicação correspondem. A etapa 4 precisa reconciliar amostras CSV/API/portal, medir desempenho no volume real e demonstrar preservação de ordens existentes em recarga.