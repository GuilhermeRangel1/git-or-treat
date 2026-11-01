# DEV-13.1 — evidência da implementação da API Gold

Data: 28/10/2026. Escopo: backend de Panorama, fila/criação de Ordens e Operação. Dois implementadores GPT-6 Luna/high, conforme solicitado; revisão de requisitos, padrões, integração e verificações pelo agente principal. Sem alteração de telas, `.env`, CSVs ou banco Gold real nesta implementação. Sem commit/push.

## Resultado e rastreabilidade

Implementação sobre a branch `dev13.1`, base `026cb33`, usando o [dicionário](../dicionario_gold.md), o [mapeamento](2026-10-28-dev13-1-gold-api-mapeamento.md) e o [plano](2026-10-28-dev13-1-gold-api-plano.md). Contrato executável descrito em [API Gold v2](../contracts/analytics-gold-dev13-1.md) e decisões em [ADR-0021](../decisions/0021-api-gold-dev13-1.md).

| Caminho executável | Composição e comportamento |
| --- | --- |
| Panorama | endpoint → contexto Gold → `GoldPanoramaRepository` → agregados SQL de diagnóstico → `build_gold_panorama` → métricas, comparação observada, base UC mensal, série e opções reais |
| Operação | endpoints → mesmo contexto → `GoldOperationsRepository` → agregados por alimentador/mês → cálculo compartilhado de série, ranking, resumo e detalhe; Panorama reutiliza esse cálculo |
| Fila | endpoints → contexto Gold → `GoldInspectionRepository` → fila com junções 1:1 → categorias/evidências, variação fixa e paginação SQL |
| Criação de ordem | autenticação → replay operacional → trava compartilhada da publicação → validação de lote/fingerprint/regra e detalhe → snapshot v2 → ordem e evento na mesma transação |
| Ordem existente | consulta/ciclo/histórico/replay → persistência operacional, sem dependência da presença da UC na publicação atual |

`ANALYTICS_SOURCE=gold` é explícito; contratos retornam lote, fingerprint e esquema. Fonte sintética preservada, sem fallback no modo Gold. Leituras reais exigem controle de leitura no servidor; modo demo continua restrito a dados sintéticos. Receita/UC/KPIs/insight ainda não adaptados falham explicitamente no modo Gold.

## Verificações automatizadas

Ambientes descartáveis, usuário sem superusuário e quatro bancos distintos terminados em `_test`: migrações, carga, analytics e ordens. Gold real não foi usada nas cargas de teste. Imagem local `git-or-treat-backend:dev07-validation312`, Python **3.12.15**, fontes atuais montados somente leitura; PostgreSQL **16** em contêiner temporário. A execução não reconstrói a imagem nem comprova execução remota da CI.

Com as quatro URLs efêmeras configuradas no processo, sem exibi-las:

```powershell
docker run --rm --mount type=bind,source=D:/git-or-treat/backend,target=/app,readonly --workdir /app --env TEST_POSTGRES_URL --env TEST_GOLD_POSTGRES_URL --env TEST_GOLD_ORDERS_POSTGRES_URL --env TEST_GOLD_ANALYTICS_POSTGRES_URL --env ORDERS_AUTH_MODE --env APP_ENV --env ANALYTICS_SOURCE --entrypoint python git-or-treat-backend:dev07-validation312 -m pytest -q -p no:cacheprovider
```

**Resultado:** 501 aprovados, 1 ignorado, 1 aviso preexistente de depreciação Starlette/httpx; 69,18 s.

Após a revisão do caso adicional de município com dados financeiros e sem base de continuidade, foram executados os testes diretamente afetados no mesmo alvo:

```text
python -m pytest -q -p no:cacheprovider tests/test_gold_analytics_postgres.py tests/test_panorama.py tests/test_operations_dev08.py tests/test_operations_summary.py
```

**Resultado:** 102 aprovados, 1 aviso preexistente; 6,42 s. O comando foi executado pela mesma imagem, com o banco analytics descartável. Essa correção preserva HTTP 200 e os números financeiros e retorna continuidade indisponível para o recorte sem base.

Outras verificações observadas:

- `backend/venv/Scripts/python.exe -m compileall -q app tests scripts`: passou.
- `git diff --check`: passou, com aviso preexistente de conversão LF/CRLF do checkout.
- `node frontend/node_modules/prettier/bin/prettier.cjs --check --end-of-line auto .github/workflows/quality.yml`: passou. A primeira chamada com final de linha padrão advertiu sobre CRLF; nenhuma reformatacão ampla foi feita.
- A CI passou a provisionar bancos próprios e encaminhar `TEST_GOLD_ANALYTICS_POSTGRES_URL` e `TEST_GOLD_ORDERS_POSTGRES_URL` ao runner e ao contêiner. Execução remota dessa mudança permanece não observada.

Os testes novos verificam publicação/fingerprint obsoletos, controle de leitura, nulos, opções e lacunas; `REPEATABLE READ`/`READ ONLY` reais com publicação concorrente em outra conexão; indicadores com base variável/nula e numerador ausente; criação/ciclo/replay de ordens; carga nova/repetida/inválida; remoção da UC sem perda do snapshot/histórico; e replay de intenção anterior à introdução de fingerprint. A prova concorrente operacional observa a espera em `pg_locks`, publica lote/fingerprint sob trava exclusiva e confirma conflito sem ordem/evento parcial.

## Diagnósticos e correções da validação

1. Primeira suíte local Python 3.11/PostgreSQL 16: 498 aprovados, 1 ignorado, 1 falha e 2 erros. A falha era o teste de continuidade ainda substituindo a dependência anterior; o cenário/assertions foram preservados e o seam foi atualizado. Os erros decorreram de resíduos no banco descartável de ordens após um teste concorrente interrompido. A prova passou a exercitar o serviço real em sessão independente e liberar a trava antes de esperar a thread; limpeza conferida pelo implementador.
2. Primeira execução completa na imagem Python 3.12: 498 aprovados, 1 ignorado e 3 erros de preparação. Uma guarda de teste fixava host/portas locais, incompatíveis com a rede Docker e CI. Foram mantidas as guardas de banco `_test`, role não privilegiada e schema vazio, retirando a restrição de rede específica. A limpeza DDL agora só ocorre depois de a própria fixture criar as tabelas. A execução completa posterior passou conforme acima.
3. Primeiro script independente de reconciliação precisou corrigir sua própria divisão entre `float` e `Decimal`; isso não alterou a API. A checagem final usa comparação numérica explícita e omite identificadores individuais nas evidências.

## Reconciliação com a Gold real — somente leitura

Lote `GOLD_20261028T024507Z_7f5f4fda`, esquema `gold-csv-v1`, banco local PostgreSQL 18 já carregado. O ambiente real continua em `git-or-treat-db-dev131`, porta local 55432, volume existente. A versão 16 aprovada na ADR-0017 foi exercitada nos testes; a infraestrutura real 18/public e a pendência do papel/schema da ADR anterior não foram migradas por esta fatia.

O agente principal executou requisições HTTP com FastAPI `TestClient`, credencial efêmera de leitura e engine real. Não substituiu repositórios por mocks e não criou ordens reais. Controles independentes consultaram a série mensal para confrontar Panorama e numeradores/populações de continuidade para confrontar Operação. Filtros, lote e fingerprint foram conferidos em todas as respostas analíticas bem-sucedidas.

- Receita e consumo do último mês do Panorama conferiram com somas independentes de `consumo_mensal_uc`; recorte município/classe conferiu com consulta SQL independente.
- Resumo anual de Operação conferiu duração, frequência, população e razões; ranking trouxe 122 alimentadores e série anual 1.464 pontos. Detalhe informou ocorrências indisponíveis.
- Fila: total de 45.000 UCs, primeira página com 20 itens, detalhe real e página além do total; recuperação nula e temporalidade de snapshot.
- Lote obsoleto retornou HTTP 409. Leitura sem credencial retornou 401. Nenhuma escrita foi executada sobre o banco real.
- A consistência financeira interna por 48 competências já está documentada no [mapeamento e SQL reproduzível](2026-10-28-dev13-1-gold-api-mapeamento.md#evidência-observada-no-postgresql); isso não comprova a exportação Delta → CSV.

Observações finais de uma execução local, sem concorrência nem orçamento de latência homologado:

| Requisição | Comandos SQL, incluindo contexto | Tempo observado |
| --- | --- | --- |
| Panorama geral / recorte por município e classe | 11 / 6 | 132,88 / 31,23 ms |
| Operação resumo / ranking / série anual | 4 / 4 / 4 | 187,19 / 90,79 / 222,85 ms |
| Detalhe agregado do alimentador | 7 | 267,31 ms |
| Fila com 20 itens / detalhe | 9 / 3 | 131,37 / 23,83 ms |
| Página da fila além do total | 9 | 357,80 ms |

Não foi observado crescimento de consultas por item/mês/alimentador nas rotas exercitadas. Não se trata de percentil, carga concorrente ou SLA aprovado.

`EXPLAIN (ANALYZE, BUFFERS)` em consultas representativas somente leitura encontrou: agregado mensal do diagnóstico 1,23 ms; última página com junções cadastrais 285,32 ms; fila por categoria 91,12 ms; agrupamento anual de continuidade 9,97 ms. PKs e índice mensal foram inventariados; nenhum índice novo foi criado sem justificativa. A medição não declara otimalidade nem substitui o plano de capacidade futura.

## Revisão e limites de aceite

Revisão manual em dois eixos pelo principal:

- **Requisitos:** grãos/chaves, distinção faturado/medido/pago, base cadastral, prioridade categórica, recuperação ausente, filtro compatível, lote/fingerprint, snapshot, replay e preservação. Corrigidos joins/consultas repetidas, filtros sem efeito, acoplamento do snapshot a DTO vivo, hash retrocompatível e independência do financeiro quando continuidade falta.
- **Padrões:** fronteiras HTTP/serviço/repositório, acesso SQL parametrizado, DI, ausência/zero, controle de acesso e compatibilidade sintética. A revisão rejeitou consulta manual ao mapa de overrides em código de produção e exigiu seam injetável normal; não restou esse mecanismo na implementação.

Etapas 1–4 do plano têm implementação executável na API e provas acima. A etapa 5 tem reconciliação e medição local, sem SLA/ensaio concorrente volumétrico nem CI remota observada. Etapa 6, integração visual, não foi executada nesta rodada. Requisitos WEB/DE mantêm seus estados oficiais.

Permanecem ausentes na exportação: pagamento, energia faturada independente, estimativa recuperável e eventos individuais; cadastro não fornece atividade histórica mensal. Receita/UC 360 e insight não foram adaptados. Autorização por área/território, homologação de negócio/regulatória e amostras Delta → CSV → API → portal continuam dependências do aceite integral. A API não conclui sozinha DEV-13.1 ou WEB-01 a WEB-07.

Ao encerrar, os dois contêineres descartáveis de testes foram removidos e o arquivo local com suas credenciais efêmeras foi apagado. O contêiner da Gold real permaneceu em execução na porta 55432; frontend, `.env` e dataset não aparecem no diff desta implementação.

Trello: consulta ao quadro oficial retornou recurso inexistente ou sem acesso. Sincronização pendente; PRD continua sendo a fonte de verdade.

## 2026-10-29 — revisão final após correções e integração da develop

Os três P2 encontrados após a primeira entrega foram corrigidos por dois implementadores GPT-6 Luna/high e revisados pelo principal. Panorama calcula diferenças e percentuais com Decimal antes de arredondar a apresentação e usa contexto local de precisão 100 para valores Numeric(38,2), sem alterar o contexto global. DEC e FEC preservam numeradores válidos independentemente; resumo informa denominadores e alimentadores por indicador, anulando campos genéricos quando as populações diferem. Ranking informa o estado do indicador solicitado.

Verificações finais observadas sobre `c9580cd` mais o diff local:

- `docker run ... python -m pytest -q -p no:cacheprovider`, imagem local Python 3.12, PostgreSQL 16 descartável e role sem privilégios: **548 passed, 1 skipped, 1 warning em 60,41 s**. Aviso de depreciação Starlette/httpx; nenhuma falha.
- `backend/venv/Scripts/python.exe -m compileall -q app tests scripts`, executado em backend: passou.
- `node frontend/node_modules/prettier/bin/prettier.cjs --check --end-of-line auto .github/workflows/quality.yml`: passou.
- `git diff --check`: passou. Varredura de 42 arquivos candidatos não encontrou nomes sensíveis, padrões fortes de credenciais ou alterações frontend.
- Reprodução independente: preço 100/300 → 101/300 varia 1%; receita 1e33 aceita; FEC 0,3 preservado quando duração ausente torna DEC nulo.
- `git fetch origin develop` e `git rev-list --left-right --count HEAD...origin/develop`: **0 0**, base `c9580cd`. Índice sem alterações preparadas e sem conflitos restantes.

A primeira tentativa desta rodada foi interrompida: Docker Desktop estava desligado e o banco descartável, indisponível. Após iniciar Docker e restabelecer as bases tmpfs de teste, a suíte completa acima passou. Nenhuma falha dessa tentativa foi tratada como evidência de produto. O contêiner da Gold real foi restabelecido sem recarga ou alteração de dados.

**Aprovação do revisor: camada API pronta para commit/push.** O relatório temporário pré-commit foi removido por solicitação da pessoa usuária. Esta aprovação não conclui DEV-13.1 integral: adaptação das telas, capacidades ausentes da exportação, homologação de negócio e demais limites registrados acima continuam pendentes. Nenhum commit ou push foi executado nesta revisão.