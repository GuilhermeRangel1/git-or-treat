# DEV-13.1 — etapa 4: reconciliação CSV, API e portal

Data: 31/10/2026. Branch: `dev13.1`. A etapa valida as jornadas do portal contra o pacote Gold v2 real e mede consultas sem alterar a publicação local.

## Integração do portal

- Panorama exige `gold-csv-v2`, escopo mensal e filtros Gold coerentes com os filtros aplicados. A métrica `ucsFaturadasNoMes` é obrigatória no contrato Gold e mantém `null/unavailable`.
- Inspeções agora decodifica e mostra `queue_position` em desktop/mobile, ordena por posição oficial ascendente por padrão e exibe os indicadores disponíveis de GD, cadastro, atendimento e interrupções. A energia recuperável permanece indisponível quando não estimada. Variação de consumo aceita valores com sinal; médias e contagens continuam não negativas. Criação de ordem exige fingerprint na origem Gold.
- Operação exige schema v2 e escopo temporal compatível. Zero, base inválida, vazio e indisponibilidade têm estados distintos; ocorrências individuais continuam indisponíveis.
- Os consumidores sintéticos foram mantidos. A etapa previa um teste opt-in para decodificar Panorama, fila e Operação com respostas HTTP reais e confirmar identidade única de lote/fingerprint; esse teste foi removido e não integra mais a suíte.

## Reconciliação independente

O Backend temporário consultou a publicação já carregada em `v_energy`, com `ANALYTICS_SOURCE=gold` e credencial de leitura temporária. O CSV foi montado somente para leitura. A saída do reconciliador omitiu valores de negócio e identificadores:

- Panorama: soma independente de `receita_base_comparavel_reais` e `consumo_base_comparavel_kwh` nas 161 linhas CSV da competência selecionada igualou os dois KPIs da API.
- Fila: total da API igualou a contagem de linhas CSV; motivo, categoria e posição oficial dos 20 itens da primeira página coincidiram com as linhas correspondentes no CSV.
- Operação: duração e frequência de uma linha alimentador/competência foram reconciliadas entre CSV e detalhe da API.
- As quatro respostas usadas na reconciliação mantiveram o mesmo lote `GOLD_20261031T020143Z_fd69c375` e fingerprint `9ac9406031f5e71bd657ca285326b73640965cc4c0b1c47f145a74cc7d02b99a`.

O teste opt-in do importador leu o pacote completo de 1,12 GB em SQLite temporário: uma carga inicial, repetição idempotente (`unchanged`), contagens iguais aos controles do manifesto e recusa de manifesto inválido. **2 testes passaram em 751,04 s**, incluindo a verificação de cabeça única do Alembic. O banco SQLite temporário foi removido.

Os scripts de reconciliação e planos SQL usados nesta etapa não continham dados embutidos e foram mantidos localmente no diretório ignorado `work/dev131-stage4-validation/`; eles não fazem parte do repositório.

## Preservação de ordens

O teste `tests/test_gold_inspections_orders_postgres.py` foi executado em PostgreSQL 16 descartável, sem porta publicada ou volume persistente, usando papel sem superusuário e dados artificiais. O fluxo HTTP criou uma ordem com snapshot, repetiu a requisição, recarregou a publicação, simulou entrega inválida e substituiu a UC; a ordem e o snapshot foram preservados. **2 testes passaram em 3,04 s.** O contêiner e a rede foram removidos. A base local `v_energy` não recebeu escritas.

## Volume e desempenho observado

Oito requisições GET sequenciais por endpoint, em cache aquecido. A amostra é pequena: o P95 informado é o maior valor das oito medições e não constitui orçamento de latência.

| Jornada | P50 | P95 observado | Resposta |
|---|---:|---:|---:|
| Panorama | 237,6 ms | 369,3 ms | 18.336 bytes |
| Fila de inspeção (20 itens) | 426,1 ms | 513,3 ms | 36.557 bytes |
| Opções de Operação | 79,0 ms | 98,2 ms | 7.053 bytes |
| Resumo de Operação | 119,7 ms | 259,3 ms | 7.152 bytes |

`EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON)` executado dentro de transação `READ ONLY` no PostgreSQL real:

| Consulta | Execução SQL | Linhas estimadas/observadas | Blocos compartilhados hit/read |
|---|---:|---:|---:|
| Agregado mensal do Panorama | 0,505 ms | 1 / 1 | 110 / 0 |
| Página inicial da fila com joins | 39,036 ms | 20 / 20 | 7.506 / 0 |
| Agregado mensal de Operação | 0,788 ms | 78 / 122 | 68 / 0 |

Não foi combinado um SLA e os planos foram coletados em cache aquecido; os tempos são descritivos, não aprovação formal de desempenho. Nenhum índice foi alterado.

## Verificações

- `frontend`: **331 passaram, 1 ignorado** em 44 arquivos; o teste live passou separadamente contra a API real.
- `npm.cmd run check:boundaries`: passou em 166 arquivos.
- `npm.cmd run format:check`: passou.
- `npm.cmd run lint`: passou; permaneceu um aviso preexistente `react(set-state-in-effect)` em `shared/auth/AuthProvider.tsx`.
- `npm.cmd run build`: TypeScript e Vite passaram.
- `backend/tests/test_migrations.py`: **8 passaram, 1 ignorado**; a migração de junção mantém uma única cabeça e o ciclo upgrade/downgrade passa.
- `git diff --check`: resultado registrado na revisão final da etapa.

## Limites e aceite

Uma migração vazia de junção foi adicionada em `backend/alembic/versions/merge_gold_v2_and_local_auth.py`, pois as revisões de autenticação local e Gold v2 formavam duas cabeças e impediam `alembic upgrade head`. A regressão agora verifica uma cabeça única.

A API temporária usou variáveis de processo; `backend/.env` permaneceu em modo sintético/demo. Não houve carga, sessão, ordem ou alteração da publicação na base local. Não foram impressos IDs de UC, alimentador ou valores analíticos.

A revisão visual no navegador não pôde ser executada: a ferramenta CUA falhou ao inicializar o kernel (`failed to write kernel assets`, caminho ausente) e o navegador local não expôs a porta de depuração. Portanto não há captura nem comprovação de tema/teclado nesta etapa. O teste visual permanece pendente, e DEV-13.1 e requisitos WEB/DE continuam sem aceite integral.
