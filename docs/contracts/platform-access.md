# Matriz de acesso da plataforma

WEB-10 etapa 2: a API deriva os escopos da sessão ativa em cada requisição. `admin` recebe a união das permissões públicas da matriz, sem isenção para rotas internas técnicas. Contas sem perfil ou com perfil desconhecido não recebem escopos de sessão.

| Recurso/rotas | Métodos e endpoints | Permissão | Justificativa |
| --- | --- | --- | --- |
| Indicadores legados | `GET /api/v1/kpis` | `panorama:read` | Alimenta os mesmos indicadores agregados e filtros da tela Panorama. |
| Panorama | `GET /api/v1/panorama` | `panorama:read` | Dados, comparação e recortes do Panorama. |
| Receita | `GET /api/v1/revenue` | `revenue:read` | Série financeira e decomposição preço-volume. |
| UC 360 | `GET /api/v1/ucs`; `GET /api/v1/ucs/{uc_id}`; `GET /api/v1/ucs/{uc_id}/overview`; `GET /api/v1/ucs/{uc_id}/history/{section}` | `ucs:read` | Busca, resumo, detalhe e históricos acessam dados cadastrais e individuais de UCs. |
| Fila analítica | `GET /api/v1/inspections/queue`; `GET /api/v1/inspections/queue/{uc_id}` | `inspections:read` | Fila, suspeita e fundamentos são recursos da jornada de perdas, além das ações operacionais de ordens. |
| Ordens | `GET /api/v1/inspections/orders`; `GET /api/v1/inspections/orders/search`; `GET /api/v1/inspections/orders/{order_id}`; `GET /api/v1/inspections/orders/{order_id}/history` | `orders:read` | Listagem, busca, detalhe e trilha da ordem operacional. |
| Identidade das ordens | `GET /api/v1/inspections/access` | Autenticação conforme `ORDERS_AUTH_MODE`; sem escopo funcional adicional | Retorna somente ator e permissões de ordens da própria identidade; pode retornar lista vazia, preservando o adaptador legado. |
| Ordens | `POST /api/v1/inspections/queue/{uc_id}/orders` | `inspections:read` e `orders:write` | A criação a partir de suspeita usa a fila e grava uma ordem. |
| Ordens | `POST /api/v1/inspections/orders`; `POST /api/v1/inspections/orders/{order_id}/result`; `POST /api/v1/inspections/orders/{order_id}/cancel`; `PATCH /api/v1/inspections/orders/{order_id}` | `orders:write` | Criação e mudanças de estado, resultado e cancelamento. O serviço valida transições e versão da ordem. |
| Operação | `GET /api/v1/operations/options`; `GET /api/v1/operations/continuity`; `GET /api/v1/operations/series`; `GET /api/v1/operations/summary`; `GET /api/v1/operations/ranking`; `GET /api/v1/operations/feeders/{feeder_id}` | `operations:read` | Opções, continuidade, séries, consolidados, rankings e detalhe de alimentador formam a jornada operacional. |
| Perguntas IA | `POST /api/v1/ai/questions` | `ai:ask` | Acesso ao assistente; `ai:ask` está disponível aos cinco perfis segundo a matriz. |
| Insight contextual | `POST /api/v1/ai/insights` | `ai:ask` e `panorama:read` | Além de chamar a IA, o servidor lê e recalcula indicadores do Panorama para fundamentar a resposta. |
| Legado indisponível | `POST /api/v1/ai/query` | `ai:ask`; retorna 503 | Mantém contrato legado indisponível; não executa consulta nem serve de alternativa a `/ai/questions`. |
| Sessão e saúde | `GET /api/v1/auth/session`; `POST /api/v1/auth/login`; `POST /api/v1/auth/logout`; `GET /api/v1/health` | Sem escopo de produto | Entrada, encerramento e estado do serviço não expõem recursos analíticos do usuário. Login/logout preservam suas validações próprias. |
| Auditoria técnica interna | `POST /api/v1/internal/genai-audit-events` | Token técnico `GENAI_AUDIT_WRITE_TOKEN` | Canal Backend → GenAI exclusivo para persistir eventos. Perfil `admin` não substitui a credencial técnica. |

## Modos de autenticação e Gold

- `session`: exige cookie individual válido e ativo; permissões e perfil são consultados novamente em cada requisição. Gold autoriza o recurso antes de abrir o snapshot `REPEATABLE READ READ ONLY`.
- `service`: somente em desenvolvimento; conserva tokens técnicos existentes para leitura analítica explícita e para o ciclo técnico de ordens. O escopo de leitura inclui Panorama, Receita, UC, Inspeções, Ordens e Operação; escrita continua limitada a ordens com token de escrita. Não recebe perfil `admin`, `ai:ask` nem acesso ao ingresso interno de auditoria.
- `demo`: somente desenvolvimento com `ANALYTICS_SOURCE=synthetic`; preserva a demonstração local. O modo recusa ambiente de produção ou fonte Gold, sem fallback sintético.

Rotas analíticas aplicam autorização antes de chamar providers. Dependências Gold repetem a checagem do recurso antes de conectar ao banco, inclusive nos fluxos opcionais usados com a fonte sintética.

## Perguntas GenAI por perfil — Gold v2

`ai:ask` autoriza abrir o assistente. O acesso a medidas Gold é uma decisão separada, derivada do perfil persistido e relida em cada fronteira de planejamento, execução, síntese e replay. O `profile_id` enviado ao catálogo continua sendo `v-energy-grid-360-gold`; ele identifica o domínio da GenAI e não o cargo da pessoa.

| Perfil | Métricas Gold v2 autorizadas | Dimensões autorizadas | Capacidades/tabelas usadas |
| --- | --- | --- | --- |
| Comercial | `billing.revenue`, `energy.consumption`, `billing.average_ticket`, `billing.effective_tariff`, `energy.average_consumption_per_uc` | `geography.municipality`, `geography.neighborhood`, `customer.consumption_class`, `tariff.subgroup`, `tariff.flag`, `generation.distributed` | `faturamento.receita` (`gold_v2.diagnostico_receita`), `faturamento.receita_bairro` (`gold_v2.consumo_receita_bairro`), `consumo.mensal_uc` (`gold_v2.consumo_mensal_uc`) |
| Operações | `network.equivalent_interruption_duration`, `network.equivalent_interruption_frequency` (DEC/FEC) | `network.feeder`, `geography.municipality` | `interrupcoes.dec_fec` (`gold_v2.indicadores_dec_fec`) |
| Atendimento | Nenhuma métrica aprovada | Nenhuma dimensão | Sem capacidade de atendimento habilitada neste leitor |
| Perdas | Nenhuma métrica aprovada | Nenhuma dimensão | Fila e ordens não são uma capacidade analítica deste leitor |
| Admin | União das métricas e dimensões atualmente implementadas para Comercial e Operações | União dos domínios acima | Capacidades atualmente implementadas para Comercial e Operações; admin não ignora validação, allowlist, leitor restrito ou prontidão |

IDs e nomes físicos vêm do catálogo `backend/app/catalogs/gold_v2.json`, do dicionário Gold v2 e da allowlist do leitor `backend/app/core/genai_gold_access.py`. Atendimento não é inferido de tabelas individuais/IDs de UC: embora existam capacidades no catálogo geral, elas não integram a lista de grants desse leitor. Nenhuma capacidade, grant ou permissão HTTP é ampliada por esta matriz.

Atendimento e Perdas continuam com `ai:ask`, mas o escopo de métricas fica vazio. Em `POST /api/v1/ai/questions`, o Backend retorna HTTP 200 com estado `needs_clarification`, sem resposta numérica e com a limitação “Ainda não há consultas disponíveis para esta área.” A mensagem é “Seu perfil tem acesso ao Assistente, mas as consultas da sua área ainda não estão disponíveis.” Essa resposta é produzida antes de criar o engine leitor, capturar publicação, consultar metadados Gold ou chamar planejamento/síntese da GenAI. O mesmo envelope preserva a correlação do pedido.

O Backend calcula `caller_ref` como hash do ator autenticado e inclui chamador, perfil, permissões, métricas, dimensões, plano e publicação no escopo de cache. Mudanças de perfil/permissões invalidam a admissão anterior; um downgrade de admin para Operações não reaproveita plano financeiro, e replay de outro chamador é negado. Prompt, contexto, headers, `session_id` conversacional, `ai:ask` e modo de serviço/demo nunca ampliam o escopo de medidas Gold.
