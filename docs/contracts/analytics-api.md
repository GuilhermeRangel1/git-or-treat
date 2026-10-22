# DEV-01 — Contratos de consumo analítico

> **DEV-03 verificada com fonte sintética:** a jornada Receita usa 1.1.0, conforme o [contrato de Receita](revenue-dev03.md) e as [evidências integradas](../plans/2026-10-21-dev03-evidence.md). Os demais endpoints preservam 1.0.0. A verificação demonstrativa não conclui a integração Gold.

**Versão:** 1.0.0 nas jornadas DEV-01, 1.1.0 em Receita conforme DEV-03 · **Fonte sintética atual:** `dev03-v1` (substitui `dev01-v1` como lote de demonstração).
**Escopo:** preparação de WEB-01 a WEB-07 e IA-01 a IA-06. As formas JSON são contratos de aplicação; não representam o esquema físico ou as fórmulas oficiais da Gold.

[Desenho](../design/2026-10-20-dev01-design.md), [plano](../plans/2026-10-20-dev01-plan.md), [ADR-0004](../decisions/0004-contratos-analiticos-e-fonte-sintetica.md) e [PRD](../PRD.md) registram motivação, decisões e aceite. O OpenAPI servido em `/openapi.json` e `/docs` é a referência executável dos schemas e parâmetros.

## Configuração e fronteira

Configurar `ANALYTICS_SOURCE=synthetic` explicitamente no processo do backend. O padrão `unavailable` não produz valores demonstrativos: as rotas analíticas retornam 503. Uma escolha desconhecida de fonte é erro de configuração, sem fallback. O frontend usa `VITE_API_URL` e o transporte HTTP existente; não lê arquivos ou banco.

Fluxo de leitura: rota FastAPI → serviço analítico → interface de repositório → implementação sintética. Ordens usam sua própria persistência operacional. O serviço de IA preserva seus próprios contratos; não recebe permissão de escrita ou acesso SQL por esta mudança.

## Contexto comum e disponibilidade

O envelope contém `data` tipado por jornada e `metadata` com `contract_version`, `status`, `period`, `filters`, `source` e `limitations`. `source` identifica tipo, versão, `is_demo` e atualização fixa do lote de demonstração. Cada métrica inclui `id`, `label`, `value`, `unit`, `status` e `limitations`.

| Estado | Significado | Representação de valor |
| --- | --- | --- |
| `available` | Medida conhecida no recorte | Número finito, inclusive zero |
| `empty` | Sem registros pertinentes ao recorte | `null`, sem fabricar zero |
| `partial` | Há dados, mas a cobertura é incompleta | Subtotal conhecido ou `null`, com limitação |
| `unavailable` | Fonte ou base necessária não disponível | `null` e motivo |

Uma indisponibilidade parcial de seção não elimina as outras seções válidas. Uma fonte analítica inteira indisponível gera erro 503. Faturado/pago e energia apurada/faturada são métricas distintas. Não calcular preço observado com energia apurada quando a definição exige energia faturada.

`period` é uma janela inclusiva de competências, com `start` e `end` em `YYYY-MM` e `granularity: month`. Defaults de demonstração: janeiro a fevereiro de 2025. Filtros comuns são `competencia_inicio`, `competencia_fim`, `municipio`, `bairro`, `classe` e `alimentador`, conforme o endpoint. As respostas repetem o recorte realmente aplicado.

Receita declara `currency_unit: BRL` e `energy_unit: kWh`; faturas também declaram sua moeda. Campos com sufixos `_kwh`, `_kw`, `_hours`, `_hours_per_uc` e `_interruptions_per_uc` identificam respectivamente energia, potência, duração, DEC e FEC. Não aplicar conversão implícita entre essas grandezas.

## Mapa das jornadas

| Jornada | Operação | Consumo preparado | Pendência de integração com Gold |
| --- | --- | --- | --- |
| Panorama | `GET /api/v1/kpis` | Métricas com unidade, disponibilidade, contexto e origem; consulta por competências e recorte | Definições oficiais, comparação e reconciliação do lote real |
| Receita | `GET /api/v1/revenue` | Totais, série inclusiva, extremos, preço observado, decomposição e recortes demonstrativos conforme [1.1.0](revenue-dev03.md) | Método e população Gold, janelas anuais e reconciliação com lote real |
| Atendimento | `GET /api/v1/ucs` e `GET /api/v1/ucs/{uc_id}` | Busca/listagem e cadastro, consumo, faturas, medidores, GD, interrupções e chamados | Chave/vigência real, cobertura de fontes e paginação de históricos volumosos |
| Perdas | `GET /api/v1/inspections/queue` | Fila, prioridade, motivo, indicadores e estimativa demonstrativos | Regra e estimativa auditáveis sobre a Gold |
| Ordens | `GET/POST /api/v1/inspections/orders` e `PATCH /api/v1/inspections/orders/{order_id}` | Schemas e persistência existentes, separados dos dados analíticos | Ciclo de estados, histórico, idempotência e UI nos cards DEV-06/07 |
| Operação | `GET /api/v1/operations/continuity` | Indicadores por alimentador, denominador e lacunas | Fórmula/denominador por período conforme DE-05 e dados reais |
| Conversa IA | `POST /api/v1/questions`, no serviço `ai-agent` | Contrato existente de pergunta, contexto limitado, resposta e evidências | Integração backend/portal e consultas Gold nos cards DEV-09/11/14 |
| Insight IA | `POST /api/v1/insights`, no serviço `ai-agent` | Contrato existente de contexto estruturado, observação e hipótese | Contexto autorizado vindo do backend e vínculo com o recorte no DEV-10 |

### Listagem e erros

Parâmetros por operação:

| Operação | Entrada preparada |
| --- | --- |
| `/kpis` | Janela comum, município/bairro/classe/alimentador; `competencia` aceita uma competência única e não pode ser combinado com a janela |
| `/revenue` | Janela comum e município/bairro/classe/alimentador; comparação demonstrativa usa os extremos solicitados, sem substituí-los por meses disponíveis |
| `/ucs` | `q`, `page`, `page_size`, `order_by`; busca parcial somente no número da UC |
| `/ucs/{uc_id}` | Identificador no caminho; histórico sintético completo de janeiro/fevereiro, sem parâmetro de janela nesta etapa |
| `/inspections/queue` | Município/bairro/classe/alimentador, `page`, `page_size`, `order_by`, `direction`; fila do snapshot sintético; [regra DEV-05 e detalhe por UC](inspection-dev05.md) |
| `/operations/continuity` | Janela comum e `alimentador`; alias `periodo` para competência única |

Filtros vazios, desconhecidos ou geografia contraditória são inválidos; combinações válidas sem fatos geram ausência explícita. A busca `q` repete seu comportamento no resultado, sem aceitar pesquisa de documento pessoal.

Listagens paginadas usam `page` a partir de 1 e `page_size` de 1 a 100. `data.items` contém a página e `pagination` informa `page`, `page_size`, `total` e `total_pages`. Página além do final mantém totais e devolve itens vazios. Ordenação só aceita campos declarados, com desempate determinístico; ver parâmetros de cada operação no OpenAPI.

Busca de UC utiliza `q` para o identificador fictício; não pesquisa CPF ou dados pessoais. Um recorte sem resultados é uma resposta vazia; um detalhe de UC inexistente retorna 404. Histórico sem registros aparece como seção vazia, sem representar consumo zero.

Erros analíticos possuem `error.code`, `error.message` e `error.details` (itens com `field` e `message`). Entrada inválida retorna 422, recurso inexistente 404 e fonte não configurada/indisponível 503. Não expor SQL, stack ou credenciais. Erros e schemas operacionais existentes não são alterados por essa política de leitura.

### Contratos de ordens e IA reaproveitados

- Ordem: criação recebe `uc_id`, `reason`, `priority` e `notes`; atualização recebe `status`, `notes` e `result`. A resposta inclui ID, UC, motivo, prioridade, estado, observações, resultado e datas de criação/alteração. A listagem atual retorna uma lista, não o novo envelope analítico paginado; essa compatibilidade é intencional até DEV-06.
- Pergunta: recebe `question` e `context` opcional com até três turnos. Responde `status`, `answer`, `message`, `evidence` e `limitations`. Estados existentes: `answered`, `needs_clarification`, `refused`, `no_evidence` e `recoverable_error`.
- Insight: recebe `screen` com métrica, unidade, período, filtros, observações, referência e limitações. Responde contexto, valores observados, hipótese, evidências e limitações; mantém referência sintética nesta etapa. O endpoint não autentica nem autoriza o consumidor por si só.
- `/api/v1/ai/query` no backend continua um placeholder legado. A lista de tabelas ali presente não é contrato real da Gold nem comprovação de executor seguro; DEV-11 é responsável por essa implementação.

## Conferência com o protótipo

Consultas ao Figma em 20/10/2026 confirmaram os frames de Panorama (`15:164`/`16:1129`), Receita (`15:331`), busca UC (`15:582`) e Operação (`16:735`). As duas apresentações do Panorama foram inspecionadas visualmente.

| Necessidade desenhada | Decisão de contrato |
| --- | --- |
| Valor faturado, energia faturada, consumo apurado e base de UCs separados | IDs/unidades distintos, sem misturar grãos ou nomes |
| Competência, comparação, território e classe visíveis | Janela e filtros efetivos são metadados; comparação completa permanece na jornada do próximo card |
| Fundamento, atualização e limitações | Origem, versão, atualização e limitações no envelope |
| Receita com preço, volume, interação e total | DEV-03 registra método demonstrativo, ajuste explícito e indisponibilidade conforme cobertura/denominadores; método Gold permanece pendente |
| Busca pelo número da UC e ausência explícita | Busca restrita à UC, detalhe 404 e estados das seções |
| DEC/FEC, base atendida e cobertura | Denominador e disponibilidade explícitos, sem alegar conformidade regulatória |

A rota `/dev/contratos` é uma ferramenta interna de verificação aprovada para DEV-01; não é o Panorama final nem reproduz seus gráficos. Ela reutiliza paleta, tipografia, tokens e controles acessíveis, sem adicionar navegação ou conteúdo às páginas do produto. Números da fixture da API não precisam ser iguais aos exemplos ilustrativos do Figma.

## Controles sintéticos e fórmulas provisórias

O lote atual `dev03-v1`, definido em `backend/app/synthetic/fixtures.py`, contém dez UCs fictícias e dezesseis faturas, com oito UCs faturadas em cada extremo. Evolui a amostra DEV-01 para permitir exploração com base suficiente; registros de progresso anteriores preservam os controles históricos `dev01-v1`. Os totais abaixo são controles literais para janeiro–fevereiro de 2025, sem filtros:

| Controle | Resultado esperado |
| --- | --- |
| Valor faturado | BRL 1.727; extremos BRL 800 → BRL 927 |
| Valor pago conhecido das faturas selecionadas | BRL 1.710 |
| Energia faturada | 1.585 kWh; extremos 730 → 855 kWh |
| Energia medida conhecida | 407 kWh; estado parcial pela leitura ausente de UC-1004 e UCs da demonstração sem histórico de leitura |
| Base ativa | 10 UCs no snapshot; não é uma população histórica homologada |
| Olinda, janeiro | Fatura e leitura de zero conhecido; estado disponível |
| Paulista | KPI legado vazio/nulo por ausência de fatos; Receita 1.1 publica zero financeiro observado com base zero porque sua fonte declara cobertura financeira completa. Sem essa cobertura, Receita publica nulo. |
| AL-03, fevereiro | Leitura registrada com valor ausente; medida indisponível, diferente de ausência de registro |
| AL-01, janeiro–fevereiro | Duas UCs no denominador, duas interrupções individuais somando três horas: DEC 1,5 h/UC e FEC 1 interrupção/UC |
| AL-03, continuidade | Denominador desconhecido; DEC/FEC nulos e motivo explícito |

Os pagamentos são associados à competência da fatura, mesmo quando a data do pagamento ocorre em fevereiro ou março. BRL 1.710 não representa fluxo de caixa recebido dentro da janela janeiro–fevereiro. A fatura de fevereiro de UC-1002 cobra BRL 82, registra BRL 70 pagos em 05/03/2025 e situação de pagamento parcial.

O preço observado acumulado é valor faturado dividido por energia faturada: 1.727 / 1.585 = 1,0896 BRL/kWh. Não equivale à tarifa homologada. A decomposição `endpoint_price_volume` compara exclusivamente os meses inicial e final solicitados: com preço `p` e energia faturada `q`, volume = `p0 × (q1 − q0)`, preço = `q0 × (p1 − p0)` e interação = `(p1 − p0) × (q1 − q0)`. Janeiro contra fevereiro resulta em +136,99, −8,53 e −1,46 BRL, somando +127 BRL com ajuste zero; o método permanece demonstrativo. Extremos ausentes, iguais, cobertura financeira incompleta ou energia faturada não positiva tornam a decomposição indisponível. Dinheiro e componentes são quantizados a centavos, preço observado a quatro casas; o [contrato DEV-03](revenue-dev03.md) fixa arredondamento, deltas publicados, ajustes, mix e reconciliação dos grupos.

DEC/FEC usam eventos individuais por UC, duração em horas e denominador fixo por alimentador; ainda não implementam todas as regras de DE-05. A cobertura usa o cadastro do snapshot, sem reconstrução temporal. Desde DEV-05, prioridades e estimativas são calculadas por uma [regra sintética auditável](inspection-dev05.md), com insumos e limitações no detalhe; não são critérios validados com dados reais. A potência GD permanece em kW e não é tratada como energia gerada. Essas definições precisam de revisão com a Gold.

A fonte de interrupções declara separadamente sua cobertura temporal inclusiva: janeiro a fevereiro de 2025. `coverage_ratio`, `covered_uc_count` e `coverage_status` descrevem a cobertura cadastral/espacial, não comprovam observação em qualquer competência. Uma janela totalmente fora da cobertura temporal ou uma fonte com cobertura temporal desconhecida resulta em DEC/FEC nulos e estado `unavailable`, com motivo. Uma janela parcialmente coberta retorna `partial`, calcula somente os eventos da interseção e informa o trecho observado nas limitações; `metadata.period` mantém a janela solicitada. Zero dentro de uma janela conhecida continua disponível. Se alguns alimentadores estiverem disponíveis e outros indisponíveis, o estado agregado é `partial`; se todos estiverem indisponíveis, é `unavailable`. O adaptador Gold futuro precisará declarar sua cobertura real, sem inferi-la apenas das datas dos eventos encontrados.

## Reprodução da consulta integrada

Na pasta `backend`, com as dependências instaladas, iniciar uma sessão PowerShell:

```powershell
$env:ANALYTICS_SOURCE = "synthetic"
$env:DATABASE_URL = "sqlite:///:memory:"
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

As leituras sintéticas não precisam de migração nem de um banco populado. Essa configuração SQLite em memória serve apenas para esta demonstração, sem persistência de ordens. Em outra sessão, na pasta `frontend`, configurar `VITE_API_URL` se necessário conforme o README e executar:

```powershell
npm.cmd run dev -- --host 127.0.0.1 --port 5173 --strictPort
```

Abrir `http://127.0.0.1:5173/dev/contratos`, consultar janeiro–fevereiro de 2025 sem filtros e conferir BRL 1.727, BRL 1.710, 1.585 kWh e 407 kWh parcial, junto da origem sintética e versão. Filtrar Olinda e janeiro para observar zero disponível; Paulista para ausência no KPI; AL-03 em fevereiro pode ser conferido diretamente na API. A rota existe somente em desenvolvimento; no preview do build de produção, `/dev/contratos` redireciona ao Panorama.

A exploração de produto DEV-03 usa `/receita`: abrir Residencial, explorar Recife e um bairro, retornar ao total e conferir classe/período preservados na URL. No lote atual, Residencial total compara BRL 620 → BRL 725 (Δ BRL 105); Recife/Residencial compara BRL 620 → BRL 645 (Δ BRL 25). Totais acumulados e valores dos extremos são apresentados separadamente. Esses controles sintéticos não substituem diagnóstico ou reconciliação Gold.

O formulário mantém o rascunho local; ao consultar, o período e os filtros aplicados compõem a URL e a chave de cache. Abrir/recarregar um link com recorte válido restaura a consulta; voltar/avançar acompanha o histórico da URL. Uma URL inválida não dispara consulta e apresenta validação para correção. Durante atualização de dados já cacheados, o resultado válido permanece identificado com um aviso de atualização.

```powershell
Invoke-RestMethod 'http://127.0.0.1:8000/api/v1/kpis?competencia_inicio=2025-01&competencia_fim=2025-02'
Invoke-RestMethod 'http://127.0.0.1:8000/api/v1/kpis?alimentador=AL-03&competencia=2025-02'
```

## Substituição da fonte sintética pela Gold

Implementar um novo repositório que satisfaça `AnalyticsRepository`, convertendo as tabelas Gold para os registros de aplicação esperados pelos serviços. Adicionar a seleção explícita desse adaptador em `get_analytics_repository` e na configuração; hoje apenas `synthetic` e `unavailable` são aceitos. Reconciliar os controles com consultas independentes sobre o lote Gold e revisar as fórmulas antes de habilitar a fonte real.

O schema da API admite `is_demo: false`, e o repositório fornece a proveniência; isso permite conectar uma fonte real sem alterar o formato dos indicadores. Os consumidores das jornadas podem manter o contrato quando a semântica continuar adequada. A página interna `/dev/contratos` exige intencionalmente `synthetic` e `is_demo: true`: ela permanece uma verificação de demonstração, não é uma página de produto pronta para Gold. Uma alteração de significado, unidade ou formato exige revisão do contrato e dos consumidores. As fixtures permanecem para testes e demonstração explícita; falhas da Gold não devem acionar fallback sintético. O adaptador e os serviços devem comunicar origem, lote, atualização, cobertura e indisponibilidade reais.

## Revisão obrigatória quando a Gold chegar

Revisar chave de UC e vigência cadastral; granularidade e deduplicação de faturas/leituras; relógio de competência versus pagamento; receita faturada/paga e arredondamento; energia apurada versus faturada; GD como potência versus energia; universo de UCs; fórmula preço-volume e interação; regra/estimativa de inspeção; denominador e janela DEC/FEC; atualização/lote e qualidade. Conectar o adaptador não resolve essas decisões automaticamente.

A conclusão funcional continua condicionada ao dicionário Gold e à reconciliação entre Databricks, banco, API, portal, IA e diagnóstico. O [dicionário](../data-dictionary.md) permanece a fonte das definições aprovadas dos dados reais.
