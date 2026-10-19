# Engenharia de dados

Pipeline PySpark/Databricks que leva as 8 fontes do case da Landing até a Gold. Contrato e critérios de aceite: [guia do serviço](../docs/services/data-engineering.md) e [PRD](../docs/PRD.md).

## Notebooks

| Notebook | Papel |
| --- | --- |
| [`Landing_to_Bronze.ipynb`](Landing_to_Bronze.ipynb) | lê as 8 fontes brutas, separa o que é malformado, grava a camada Bronze no Delta e reconcilia lidas × rejeitadas × gravadas |
| [`Bronze_perfilamento.ipynb`](Bronze_perfilamento.ipynb) | mede a qualidade do que a Bronze recebeu (nulos, duplicatas, órfãos, grafias divergentes, datas) e grava em `quality.perfil_bronze` |

A transição para a Silver (`Bronze_to_Silver.ipynb`) e a Gold entram depois, como novas tarefas do mesmo Workflow.

## Workflow

[`v-energy-grid-360.yaml`](v-energy-grid-360.yaml) é a definição do job `v-energy-grid-360` no Databricks: as duas tarefas que existem hoje, encadeadas na ordem em que o dado anda.

```text
Landing_to_Bronze ──▶ Bronze_perfilamento
```

A ordem não é decorativa: o perfilador lê as tabelas que a ingestão acabou de gravar. No arquivo, o elo é `depends_on` + `run_if: ALL_SUCCESS` — a segunda tarefa só começa com a primeira bem-sucedida.

### Execução comprovada

![Job v-energy-grid-360 com as duas tarefas concluídas](img/workflow-graph.png)

| Item | Valor |
| --- | --- |
| Execução | `14313419965490`, 18/10/2026, iniciada às 02:46 (manual) |
| Resultado | `Succeeded` |
| Duração total | 21m 03s |
| `Landing_to_Bronze` | 15m 22s |
| `Bronze_perfilamento` | 5m 39s — `Depends on = Landing_to_Bronze`, `Run if dependencies = All succeeded` |
| Compute | serverless, *performance optimized* |

As duas tarefas somam 21m 01s contra 21m 03s de total: rodaram **uma depois da outra**. Se rodassem em paralelo, o job fecharia em torno de 15m 22s, o tempo da tarefa mais longa — o total ser a soma das partes é o que prova a serialização.

O job foi executado 4 vezes em 18/10, todas bem-sucedidas, sem duplicar dado: a Bronze é carregada por sobrescrita e reconciliada com `delta = 0`. No output da ingestão, o autoteste de captura de registro malformado imprime `AUTOTESTE registros malformados: OK`, as oito tabelas fecham com `delta = 0` (`atendimentos` sai como `SEM_BASE`, esperado porque o JSON é indentado) e `bronze.rejeitados` fica vazia.

### Agenda proposta

Mensal, dia 5, às 03:00 (America/Recife). O insumo é mensal por natureza — leituras e faturas são por competência —, então rodar mais de uma vez no mês não traria dado novo, só custo; o dia 5 dá folga para o fechamento da competência anterior chegar íntegro. Reexecutar é seguro, e é a mesma idempotência que motivou carregar com `overwrite` e não com `append`: uma competência retificada entra no lugar da anterior, sem acumular versões.

A agenda está armada no job (`pause_status: UNPAUSED`), mas continua sendo uma **proposta para a operação futura**, não uma integração de produção existente: o case entrega uma extração única. Um gatilho de chegada de arquivo no Volume foi considerado e descartado — os arquivos do Dataset entram em lote, e cada chegada dispararia uma execução, enquanto o agendamento dispara uma vez no dia combinado.

### Como reexecutar

1. Importe os dois notebooks deste diretório no Workspace (Workspace → Create → Import), ou use os que já estão lá.
2. Crie o job com duas tarefas, `Landing_to_Bronze` e `Bronze_perfilamento` (a segunda com `Depends on = Landing_to_Bronze`), em compute serverless — ou aplique [`v-energy-grid-360.yaml`](v-energy-grid-360.yaml) como definição do job.
3. Rode com `Run now`.
4. Confira o resultado: a ingestão lista as 10 tabelas Bronze e imprime a reconciliação com `delta = 0` e `AUTOTESTE_OK`; o perfilador termina sem `AVISO` e grava `quality.perfil_bronze`.

Se o autoteste de parse falhar, as abas de inspeção mudarem, a contagem da quarentena divergir ou alguma reconciliação ficar fora de `OK`/`SEM_BASE`, a ingestão lança erro e o Workflow não inicia o perfilamento. Uma divergência detectada no fim da ingestão pode ocorrer depois da sobrescrita das tabelas Bronze; nesse caso, confira `bronze.reconciliacao` e a versão anterior das tabelas Delta antes de retomar. A publicação atômica do lote ainda não foi implementada.
