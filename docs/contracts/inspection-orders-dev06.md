# DEV-06 — criação e consulta de ordens

23/10/2026. WEB-05, dependência DEV-01; integração com DEV-05/WEB-04. Backend verificado com fonte sintética. Interface básica por solicitação da pessoa usuária; acabamento e jornada completa de alterações ficam com a pessoa responsável pelo frontend.

## Criação pela fila

`POST /api/v1/inspections/queue/{uc_id}/orders`, com `Idempotency-Key` obrigatório: 16–128 caracteres alfanuméricos ASCII, `_` ou `-`. No modo local `demo`, não exige autenticação e só pode usar fonte sintética; nos modos `session`/`service`, exige identidade com permissão de escrita. Configuração e contrato para o frontend: [guia de entrega](inspection-auth-handoff.md).

```json
{
  "source_version": "dev03-v1",
  "rule_version": "dev05-v1",
  "priority": "MEDIA",
  "notes": "Verificar o contexto do medidor."
}
```

Use as versões retornadas pelo detalhe, sem fixá-las no cliente. As duas versões são obrigatórias. Prioridade operacional: BAIXA/MEDIA/ALTA, padrão MEDIA, independente da pontuação analítica de 0 a 1. Observações opcionais, até 4.000 caracteres. UC da rota tem até 50 caracteres. Motivo e evidências vêm exclusivamente do servidor; campos desconhecidos são recusados.

- 201: nova ordem PENDENTE, commit confirmado.
- 200: mesma chave/conteúdo normalizado retorna a mesma ordem, inclusive após encerramento.
- 409: chave reutilizada com outro conteúdo/UC, versão obsoleta ou ordem ativa para a mesma UC.
- 404: UC sem suspeita. 422: entrada/header inválidos. Nos modos autenticados, 401 indica credencial ausente/inválida e 403 indica permissão insuficiente; na demo, 403 também pode indicar origem de navegador não permitida ou requisição cross-site. 503 indica fonte/acesso indisponíveis.

`suspicion_reference` identifica UC + kind/version/is_demo da fonte + versão da regra por SHA-256. `updated_at` não cria nova identidade: a versão da fonte precisa identificar snapshot imutável. `suspicion_snapshot` preserva detalhe e metadados completos: motivo, sinais, pontuação, estimativa, janela, atualização e limites. Estimativa ausente continua nula. Gold e inspeções históricas XLSX não são alteradas.

O JSON persistido usa `snapshot_schema_version: "1"`, com modelo operacional independente de `SuspicionResponse`. Registros anteriores sem esse campo são lidos como versão 1, sem reescrever o banco. Campos adicionais da evidência e metadados JSON são preservados; acrescentar campos obrigatórios ao contrato analítico não invalida o histórico. Uma futura versão do snapshot deve ter adaptador explícito; não alterar silenciosamente o significado de v1. Não há nova migração SQL: o versionamento vive no JSON existente.

## Repetição e concorrência

Uma ordem PENDENTE/EM_ANDAMENTO por UC, conforme [ADR-0011](../decisions/0011-ordem-ativa-por-uc.md), alinhada à DEV-07. A regra cobre criações manuais e pela fila e independe da versão da fonte/regra. Cancelamento/conclusão libera nova intenção/chave, preservando o registro anterior; repetir a chave antiga continua retornando a ordem original.

Índice único global da chave e índice parcial único da UC nos estados ativos (nomes persistidos PENDING/IN_PROGRESS) protegem múltiplos processos. A consulta prévia não é a garantia de exclusividade. Falha executa rollback; colisão concorrente consulta a ordem vencedora ou retorna conflito. Chaves não expiram automaticamente. O provedor analítico é resolvido sob demanda, somente após a consulta da chave: reenvio confirmado retorna 200 mesmo com fonte indisponível; intenção nova recebe 503 sem gravar nada. Conteúdo divergente recebe 409 antes de consultar a fonte. Autorização e validação HTTP continuam obrigatórias.

Conflitos preservam `detail` como string, para clientes existentes, e acrescentam `error: {code, message, order_id}`. Códigos: `idempotency_key_reused`, `stale_suspicion`, `active_order_exists`; transições existentes usam `order_conflict`. `order_id` identifica a ordem relacionada ou é nulo (exemplo: versão obsoleta). O frontend pode usar o ID para consultar `/orders/{id}` sem interpretar texto. O schema 409 é publicado no OpenAPI; criação manual e atualização também usam esse envelope.

No cliente, uma chave por intenção, reutilizada após perda de resposta. Desabilitar envio em andamento e mostrar sucesso apenas depois de 200/201 com JSON validado. Navegar/recarregar gera nova intenção na UI básica; a restrição de ordem ativa continua impedindo duplicação.

## Consulta e compatibilidade

`GET /api/v1/inspections/orders/search`: filtros AND por `status` (PENDENTE/EM_ANDAMENTO/CONCLUIDA/CANCELADA), `uc_id` exato, `priority` e `has_result` opcional. `has_result=true` seleciona ordens com resultado preenchido; `false` seleciona resultado nulo, vazio ou composto apenas por whitespace ASCII; omissão inclui ambos. O filtro é aplicado antes da contagem e da paginação. `page >= 1`, `page_size` de 1 a 100 (padrão 20). Retorna `{items, pagination: {page, page_size, total, total_pages}}`. Ordenação `created_at DESC, id DESC`. Contagem do recorte completo; página além do total tem itens vazios. Paginação por offset pode mudar se houver gravações entre consultas.

`items` usa `OrderSummary`, com ID, UC, motivo, prioridade, estado, observações/resultado, timestamps e referência da suspeita; não inclui `suspicion_snapshot`. A consulta SQL seleciona somente essas colunas e conta por ID, sem carregar o JSON. Evidência completa permanece no GET por ID e nas respostas de criação/reenvio. Página além do total é devolvida antes de enviar offset ao banco, inclusive para inteiros maiores que BIGINT; mantém os totais e evita erro 500.

`GET /api/v1/inspections/orders/{id}` retorna registro ou 404 independentemente da fonte analítica. Nos modos autenticados, leitura exige token de leitura ou escrita; no modo local `demo`, não exige Bearer. Ordens antigas têm campos novos nulos. `GET /orders` mantém lista antiga por compatibilidade; clientes novos usam `/orders/search`. `POST /orders` mantém criação manual sem vínculo analítico, agora sujeita à mesma unicidade por UC, com 409 estruturado para repetição; o portal usa exclusivamente criação pela fila.

`PATCH /orders/{id}` preserva ADR-0007: PENDENTE inicia/cancela, EM_ANDAMENTO conclui/cancela, conclusão exige resultado, estados finais não reabrem. A UI básica só cria/consulta. Snapshot de criação não substitui auditoria durável das alterações nem identidade individual de operador, ainda pendentes em WEB-05/WEB-10.

Atualização frontend de 24/10/2026: a página de Ordens passa a consumir também o PATCH existente, com resultado obrigatório na conclusão, confirmação de cancelamento e bloqueio de estados finais. Os timestamps operacionais são gerados em UTC por `TimestampMixin`; a demo SQLite pode serializá-los sem offset, e o cliente os normaliza como UTC antes de mostrar o fuso de Recife. Competências do snapshot (`YYYY-MM`) são apresentadas como mês/ano, sem conversão de fuso. [Evidências](../plans/2026-10-24-dev06-orders-frontend-evidence.md).

## Execução e integração do frontend

Aplicar `alembic upgrade head` sobre banco existente, inclusive SQLite. Revisão `a6d060000001` acrescenta campos nulos e índices sem perder ordens antigas. Downgrade remove os novos campos/evidências: requer backup adequado fora do banco descartável.

A revisão seguinte, `a6d060000002`, verifica duplicidades ativas por UC antes de substituir o índice por referência. Se encontrar duplicidades, interrompe a migração para reconciliação manual, sem apagar/cancelar ordens. Após resolver a duplicidade de acordo com a operação, reaplicar o upgrade. O histórico, snapshots e chaves existentes são preservados.

API: use `DATABASE_URL` persistente e `ANALYTICS_SOURCE=synthetic`. A demo local sem autenticação exige `APP_ENV=development` e `ORDERS_AUTH_MODE=demo`. No modo `session`, permissões pertencem ao usuário autenticado; no modo `service`, `ORDERS_WRITE_TOKEN` privado habilita escrita e leitura, e `ORDERS_READ_TOKEN` é opcional para acesso somente de leitura. SQLite em memória não comprova reinício.

Vite: `API_PROXY_TARGET` com endereço da API e `VITE_API_URL=/`. O proxy não injeta credenciais; `ORDERS_DEV_PROXY_TOKEN` não tem mais efeito. No Compose local, `ORDERS_AUTH_MODE=session` habilita login individual após migração e provisão explícitas do banco. Para demonstração sem login, selecione `ORDERS_AUTH_MODE=demo` apenas em desenvolvimento com fonte sintética. Credenciais de serviço ficam exclusivas de CLI/Swagger em desenvolvimento; não entram em `VITE_*`, bundle ou armazenamento do navegador. Compose publica as três portas somente em localhost.

Referência consultada via Figma MCP: arquivo `oTjmpIBgbA7OOYb9ZmMG9K`, frame `16:640` (Ordens desktop claro), com ordem, UC, estado, resultado e ação. Conforme pedido, shell/tokens preservados e tela simplificada, sem reprodução integral ou redesenho da DEV-05.

## Evidência reproduzível

- Python 3.12, FastAPI 0.161.1, SQLAlchemy 2.1.6, Alembic 1.20.1; PostgreSQL 18 descartável, papel sem superusuário. Context7 consultado: [índices parciais PostgreSQL](https://docs.sqlalchemy.org/en/20/dialects/postgresql.html#partial-indexes), [SQLite](https://docs.sqlalchemy.org/en/20/dialects/sqlite.html#partial-indexes) e [transações](https://docs.sqlalchemy.org/en/20/orm/session_transaction.html).
- Em `backend`: `python -m pytest -q`, com `TEST_POSTGRES_URL` apontando para banco descartável `*_test`: **193 aprovados**, sem pulados. Inclui migração/modelos, ordens antigas, concorrência, versões obsoletas, campos forjados, filtros/paginação, autorização e reinício real de processo Uvicorn preservando ordem/reenvio.
- Em `frontend`: `npm.cmd run test -- --reporter=dot`: **121 aprovados em 14 arquivos**. Build/tipos, lint, check:boundaries (80 arquivos), format:check aprovados. Testes novos verificam ausência de falso sucesso, bloqueio durante envio, link de acompanhamento e mesma chave após perda de resposta. Vitest exigiu execução fora do sandbox por EPERM em temporários.
- Controle independente UC-1004: snapshot persiste pontuação 0,92 e estimativa 45 kWh, UC e motivo da fila; nova conexão/processo preserva registro. Banco PostgreSQL criado apenas em `work/dev06`, sem tocar em banco operacional existente.
- Pendências: Gold/homologação, acabamento visual, auditoria de alterações e revisão humana. Aceite automatizado DEV-06 não conclui WEB-05 inteiro.
- Navegador com API real: detalhe UC-1004 → criar → confirmação da ordem 1 → acompanhar → recarregar `/ordens?uc_id=UC-1004`; registro preservado, motivo e referência visíveis. Captura local `dev06-orders.png` fora do repositório. Sem reprodução visual integral do Figma; modo escuro desktop conferido.

### Revisão integrada com develop — 23/10/2026

- Integração de `origin/develop` em `e6c5423`: preservados contratos UC/Receita e fila; conflitos documentais resolvidos, decisão da fila renumerada para ADR-0010 e decisão de composição do frontend para ADR-0013. A develop não foi alterada.
- Corrigida também a janela concorrente entre a primeira consulta da chave e a consulta de ordem ativa: antes de emitir conflito, o serviço reconcilia novamente a chave e retorna 200 para conteúdo idêntico. O teste determinístico confirma criação pelo outro trabalhador nesse intervalo, sem transformar reenvio válido em 409.
- `python -m pytest -q` com PostgreSQL 18 descartável: **214 aprovados, sem pulados**. `python -m compileall -q app tests scripts`: aprovado. Novas regressões cobrem páginas extremas, projeção SQL sem JSON, snapshots legados após evolução do DTO analítico e interleaving concorrente.
- Frontend integrado: **130 testes em 17 arquivos**, lint, fronteiras (89 arquivos), build/tipos e format:check aprovados. A tela básica continua usando os mesmos campos do resumo. `git diff --check` aprovado.
- Context7: [seleção de colunas no SQLAlchemy](https://docs.sqlalchemy.org/en/20/orm/queryguide/select.html#selecting-individual-attributes). Revisões de padrões e requisitos não identificaram bloqueadores nos ajustes; reconciliação Gold e revisão humana permanecem pendentes.

### Recuperação e alinhamento operacional — 23/10/2026

- `python -m pytest -q`, PostgreSQL 18 descartável: **221 aprovados, sem pulados**; compileall aprovado. Novas regressões: fonte indisponível sem sequer resolver o provedor em replay; conflito estruturado; unicidade entre versões e criação manual; falha de inserção com rollback da chave; falha em `refresh` após commit com recuperação por reenvio; migração com duplicidades preservadas em SQLite e PostgreSQL.
- Concorrência PostgreSQL também cobre duas versões da fonte e disputa entre criação manual e pela fila. O índice arbitra uma única ordem ativa por UC. Downgrade/upgrade e drift entre migração/modelos aprovados.
- Frontend: **130 aprovados em 17 arquivos**, build/tipos, lint, fronteiras (89 arquivos) e format:check aprovados. `detail` textual preservado; nenhum ajuste visual necessário.
