# DEV-06 — criação e consulta de ordens

23/10/2026. WEB-05, dependência DEV-01; integração com DEV-05/WEB-04. Backend verificado com fonte sintética. Interface básica por solicitação da pessoa usuária; acabamento e jornada completa de alterações ficam com a pessoa responsável pelo frontend.

## Criação pela fila

`POST /api/v1/inspections/queue/{uc_id}/orders`, Bearer de escrita e header obrigatório `Idempotency-Key`: 16–128 caracteres alfanuméricos ASCII, `_` ou `-`.

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
- 409: chave reutilizada com outro conteúdo/UC, versão obsoleta ou ordem ativa para a mesma suspeita.
- 404: UC sem suspeita. 422: entrada/header inválidos. 401/403: acesso negado. 503: fonte/acesso indisponíveis.

`suspicion_reference` identifica UC + kind/version/is_demo da fonte + versão da regra por SHA-256. `updated_at` não cria nova identidade: a versão da fonte precisa identificar snapshot imutável. `suspicion_snapshot` preserva detalhe e metadados completos: motivo, sinais, pontuação, estimativa, janela, atualização e limites. Estimativa ausente continua nula. Gold e inspeções históricas XLSX não são alteradas.

## Repetição e concorrência

Uma ordem PENDENTE/EM_ANDAMENTO por referência da suspeita. Cancelamento/conclusão libera uma nova intenção/chave, preservando o registro anterior; repetir a chave antiga continua retornando a ordem original. A mesma UC pode ter investigação em outra versão da fonte/regra.

Índice único global da chave e índice parcial único da referência nos estados ativos (nomes persistidos PENDING/IN_PROGRESS) protegem múltiplos processos. A consulta prévia não é a garantia de exclusividade. Falha executa rollback; colisão concorrente consulta a ordem vencedora ou retorna conflito. Chaves não expiram automaticamente. O provedor analítico configurado ainda pode precisar estar disponível para resolver a dependência HTTP em um reenvio.

No cliente, uma chave por intenção, reutilizada após perda de resposta. Desabilitar envio em andamento e mostrar sucesso apenas depois de 200/201 com JSON validado. Navegar/recarregar gera nova intenção na UI básica; a restrição de ordem ativa continua impedindo duplicação.

## Consulta e compatibilidade

`GET /api/v1/inspections/orders/search`: filtros AND por `status` (PENDENTE/EM_ANDAMENTO/CONCLUIDA/CANCELADA), `uc_id` exato e `priority`; `page >= 1`, `page_size` de 1 a 100 (padrão 20). Retorna `{items, pagination: {page, page_size, total, total_pages}}`. Ordenação `created_at DESC, id DESC`. Contagem do recorte completo; página além do total tem itens vazios. Paginação por offset pode mudar se houver gravações entre consultas.

`GET /api/v1/inspections/orders/{id}` retorna registro ou 404 independentemente da fonte analítica. Leitura exige token de leitura ou escrita. Ordens antigas têm campos novos nulos. `GET /orders` mantém lista antiga por compatibilidade; clientes novos usam `/orders/search`. `POST /orders` mantém criação manual anterior, sem vínculo analítico e fora da regra de identidade de suspeita; o portal usa exclusivamente criação pela fila.

`PATCH /orders/{id}` preserva ADR-0007: PENDENTE inicia/cancela, EM_ANDAMENTO conclui/cancela, conclusão exige resultado, estados finais não reabrem. A UI básica só cria/consulta. Snapshot de criação não substitui auditoria durável das alterações nem identidade individual de operador, ainda pendentes em WEB-05/WEB-10.

## Execução e integração do frontend

Aplicar `alembic upgrade head` sobre banco existente, inclusive SQLite. Revisão `a6d060000001` acrescenta campos nulos e índices sem perder ordens antigas. Downgrade remove os novos campos/evidências: requer backup adequado fora do banco descartável.

API: `DATABASE_URL` persistente, `ANALYTICS_SOURCE=synthetic`, `ORDERS_WRITE_TOKEN` privado. SQLite em memória não comprova reinício.

Vite: `ORDERS_DEV_PROXY_TOKEN` no ambiente do servidor com o mesmo valor do token da API; `API_PROXY_TARGET` com endereço da API; `VITE_API_URL=/`. Proxy injeta Bearer somente nas rotas operacionais e requisições de mesma origem. Token não entra em `VITE_*`, bundle ou armazenamento do navegador. Desenvolvimento interno apenas; produção precisa de sessão/BFF/identidade própria. No Compose, passe explicitamente `ORDERS_DEV_PROXY_TOKEN` ao serviço frontend; não carregue todas as credenciais do backend nele. Sem token, a UI recebe erro e a API permanece fechada.

Referência consultada via Figma MCP: arquivo `oTjmpIBgbA7OOYb9ZmMG9K`, frame `16:640` (Ordens desktop claro), com ordem, UC, estado, resultado e ação. Conforme pedido, shell/tokens preservados e tela simplificada, sem reprodução integral ou redesenho da DEV-05.

## Evidência reproduzível

- Python 3.12, FastAPI 0.161.1, SQLAlchemy 2.1.6, Alembic 1.20.1; PostgreSQL 18 descartável, papel sem superusuário. Context7 consultado: [índices parciais PostgreSQL](https://docs.sqlalchemy.org/en/20/dialects/postgresql.html#partial-indexes), [SQLite](https://docs.sqlalchemy.org/en/20/dialects/sqlite.html#partial-indexes) e [transações](https://docs.sqlalchemy.org/en/20/orm/session_transaction.html).
- Em `backend`: `python -m pytest -q`, com `TEST_POSTGRES_URL` apontando para banco descartável `*_test`: **193 aprovados**, sem pulados. Inclui migração/modelos, ordens antigas, concorrência, versões obsoletas, campos forjados, filtros/paginação, autorização e reinício real de processo Uvicorn preservando ordem/reenvio.
- Em `frontend`: `npm.cmd run test -- --reporter=dot`: **121 aprovados em 14 arquivos**. Build/tipos, lint, check:boundaries (80 arquivos), format:check aprovados. Testes novos verificam ausência de falso sucesso, bloqueio durante envio, link de acompanhamento e mesma chave após perda de resposta. Vitest exigiu execução fora do sandbox por EPERM em temporários.
- Controle independente UC-1004: snapshot persiste pontuação 0,92 e estimativa 45 kWh, UC e motivo da fila; nova conexão/processo preserva registro. Banco PostgreSQL criado apenas em `work/dev06`, sem tocar em banco operacional existente.
- Pendências: Gold/homologação, acabamento visual, auditoria de alterações e revisão humana. Aceite automatizado DEV-06 não conclui WEB-05 inteiro.
- Navegador com API real: detalhe UC-1004 → criar → confirmação da ordem 1 → acompanhar → recarregar `/ordens?uc_id=UC-1004`; registro preservado, motivo e referência visíveis. Captura local `dev06-orders.png` fora do repositório. Sem reprodução visual integral do Figma; modo escuro desktop conferido.
