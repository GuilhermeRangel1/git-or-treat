# DEV-13.1 — etapa 3: API em modo Gold contra o lote real

Data: 31/10/2026. Branch: `dev13.1`. Escopo: ativar `ANALYTICS_SOURCE=gold` no processo de validação e conferir respostas HTTP do Backend contra a publicação v2 que já estava carregada. Nenhuma carga ou migração foi executada.

## Ambiente e identidade

A validação usou a configuração `DATABASE_URL` já existente em `backend/.env`, com destino analisado sem revelar credenciais: PostgreSQL 18.1 local, banco `v_energy`, acessado pelo container Backend via `host.docker.internal:5432`. O processo descartável recebeu `ANALYTICS_SOURCE=gold`, `APP_ENV=development`, `ORDERS_AUTH_MODE=service` e tokens temporários distintos para leitura/escrita; apenas o token de leitura foi usado. O container de validação montou o código como somente leitura. O arquivo `.env`, serviços e banco não foram alterados.

Identidade retornada de forma consistente pelas consultas:

- Lote: `GOLD_20261031T020143Z_fd69c375`
- Schema: `gold-csv-v2`
- Fingerprint: `9ac9406031f5e71bd657ca285326b73640965cc4c0b1c47f145a74cc7d02b99a`

## Verificações HTTP somente leitura

Usando `fastapi.testclient.TestClient` sobre a aplicação e conexão real à publicação:

- `GET /api/v1/panorama?comparacao=nenhuma`: HTTP 200; metadados do lote/schema/fingerprint corretos; fórmulas da receita, consumo e preço apontam à base comparável; `ucsFaturadasNoMes` retorna `null`/`unavailable` conforme a limitação do grão.
- `GET /api/v1/inspections/queue?page=1&page_size=20`: HTTP 200; 20 itens verificados com motivo, posição canônica e estado da recuperação; a energia individual permanece nula.
- `GET /api/v1/operations/options`: HTTP 200; 48 competências observadas.
- `GET /api/v1/operations/summary?periodo=<última competência observada>`: HTTP 200.
- Repetidas chamadas de Panorama, fila e resumo de Operação com `expected_lote` e `expected_fingerprint`: HTTP 200; as guardas aceitaram a publicação esperada.

Os valores de negócio e identificadores de UC não foram impressos. Apenas requisições GET foram realizadas; nenhuma ordem foi criada e nenhuma gravação foi feita.

A execução usou a aplicação via TestClient em processo descartável, não deixou um servidor ativo nem alterou a seleção em `backend/.env`, que continua `ANALYTICS_SOURCE=synthetic` e `ORDERS_AUTH_MODE=demo`. Para usar Gold em uma execução posterior, a fonte e o modo de autenticação devem ser definidos no processo/Compose conforme o [guia Backend](../services/backend.md) e o [README do Backend](../../backend/README.md).

## Limites e próxima etapa

A etapa 3 confirma consultas HTTP ao lote real existente, não reconcilia valores amostrais independentemente com os CSVs nem valida os decoders do portal. A etapa 4 deve reconciliar CSV → API → portal, observar estados de erro/carregamento/vazio, medir desempenho com o volume recebido e exercitar preservação de ordens em uma recarga controlada com ordens de teste. Nenhum critério WEB/DE ou DEV-13.1 foi marcado como concluído integralmente.