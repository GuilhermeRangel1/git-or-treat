# DEV-13.1 — plano de integração da Gold na API

> **Para execução por agentes:** usar `superpowers:subagent-driven-development` quando a delegação estiver autorizada, ou `superpowers:executing-plans` para execução direta. As caixas abaixo representam trabalho futuro, não verificações já realizadas.

**Objetivo:** disponibilizar Panorama, triagem que origina Ordens e Operação pela API sobre o mesmo lote real, antes de adaptar as telas.

**Arquitetura:** evoluir os providers e contratos existentes com consultas específicas à Gold no PostgreSQL. Routers validam HTTP; serviços mantêm regras; repositórios filtram/agregam/paginam no banco. Ordens e eventos permanecem operacionais, com evidências históricas imutáveis.

**Stack:** FastAPI, Pydantic, SQLAlchemy/psycopg, PostgreSQL; posteriormente React/TypeScript, Vite e TanStack Query existentes. Sem nova dependência prevista.

**Especificação:** [mapeamento e evidências](2026-10-28-dev13-1-gold-api-mapeamento.md), [dicionário](../dicionario_gold.md), [PRD](../PRD.md) e contratos DEV-05/06/07/08. Propostas de alteração semântica deste plano ainda não são decisões aprovadas.

**Execução em 28/10/2026:** etapas 1–4 implementadas na API; etapa 5 com reconciliação e medições locais, sem SLA ou CI remota observados. As caixas abaixo conservam a especificação granular do plano; a comprovação e os limites do trabalho executado estão na [evidência da API](2026-10-28-dev13-1-gold-api-evidencias.md). A etapa 6 não foi executada, conforme a prioridade API primeiro. A [ADR-0021](../decisions/0021-api-gold-dev13-1.md) registra as escolhas técnicas adotadas, sem homologar os aceites de negócio.

## Restrições globais

- API primeiro; não implementar telas durante as etapas 1–5. A etapa 6 depende de contratos e consultas reconciliados.
- Gold é analítica; carga não apaga nem recria ordens/histórico. Dataset, identificadores individuais e segredos não entram em commits/evidências públicas.
- Nenhum fallback sintético no modo Gold. Não preencher receita paga, energia faturada, recuperação ou ocorrências com valores de outra grandeza.
- Mesmo lote na resposta, snapshot consistente durante consultas e detecção de mudança entre chamadas.
- Ausência, zero, vazio, parcial e falha são distintos. Comparação requer base e cobertura explícitas.
- Revisões que mudem decisões ou critérios do produto exigem PRD e ADR coerentes; o mapeamento não altera silenciosamente o aceite.
- Fonte sintética continua explicitamente demonstrativa; modo `demo` de ordens não é habilitado para dados reais.

## Pontos prioritários de revisão

1. Recarga durante resumo/detalhe/criação: nunca misturar metadado novo com fatos antigos nem perder ordem confirmada.
2. Duas tabelas de fatos e múltiplos meses: impedir multiplicação por join e repetição de denominadores/UCs.
3. Campo ausente: contrato aceita indisponibilidade sem usar zero, score ou evento fictício.
4. Página/filtro diferente: itens, contagem e resumo representam o mesmo universo, com desempate determinístico.
5. Ordem histórica: snapshot antigo e replay confirmado continuam legíveis mesmo com UC ausente da Gold nova.

## Etapa 1 — contexto de lote, capacidades e contratos Gold

**Arquivos existentes:** `backend/app/core/config.py`, `core/database.py`, `repositories/{analytics,panorama}.py`, `models/gold_load.py`, `schemas/{common,analytics,panorama,inspection_queue,operations,order_snapshot}.py`, `api/v1/endpoints/*`; contratos em `docs/contracts/`.

**Novos arquivos propostos:** `repositories/gold_context.py` para leitura da publicação e ciclo consistente; contratos específicos dos domínios, conforme necessário, sem criar um framework genérico.

- [x] Definir contratos Gold versionados para disponibilidade de métricas, temporalidade de snapshot, categorias de prioridade e detalhe agregado sem ocorrências. Proposta de versão `2.0.0` onde a mudança é incompatível; preservar a identificação das versões sintéticas existentes. Documentar negociação/seleção pelo modo da fonte antes de mudar respostas consumidas.
- [x] Documentar quais rotas estão disponíveis em Gold, incluindo comportamento explícito das ainda não adaptadas de Receita/UC/KPIs. Não permitir mistura silenciosa de fontes.
- [x] Acrescentar `ANALYTICS_SOURCE=gold` e providers por capacidade. Validar lote/esquema suportado pela `gold_carga_atual`; tentativa falha não invalida publicação anterior preservada.
- [x] Implementar contexto de leitura por requisição com transação `REPEATABLE READ READ ONLY`; metadados e agregados vêm desse contexto. Injeção de `Session`/conexão explícita e fechamento garantido.
- [x] Definir `expected_lote` opcional para chamadas analíticas e conflito 409 para lote substituído. No contrato de criação, manter `source_version`/`rule_version` esperadas.
- [x] Definir acesso local às leituras reais: sessão individual no portal e credenciais privadas de serviço em CLI/Swagger; não contornar a trava de `demo`. Não injetar credenciais por proxy ou publicar segredos no cliente.
- [x] Verificar pelo HTTP configuração inválida, Gold ausente, esquema incompatível, falha de dependência e reload entre consultas/chamadas, sem fallback.

**Saída verificável:** contrato e provider executáveis retornam lote real; concorrência não mistura fatos/metadados. Ainda não significa que todas as jornadas estejam adaptadas.

## Etapa 2 — Panorama real na API

**Arquivos:** criar `backend/app/repositories/gold_panorama.py`; evoluir `services/panorama.py`, `schemas/panorama.py`, `api/v1/endpoints/panorama.py` e contrato correspondente. Evitar materializar tabelas para imitar `records`.

**Interface proposta do repositório:** consultar totais e série por competência/município/classe no contexto Gold da etapa 1 e retornar resultados tipados agregados; opções de filtro e competências observadas vêm do mesmo lote. Assinaturas finais devem constar no contrato antes da implementação, preservando nomes públicos onde sua semântica continuar válida.

- [x] Consultar diagnóstico por competência, município e classe, com somas no SQL e Decimal para dinheiro. Série e comparação compartilham os mesmos predicados.
- [x] Entregar receita faturada e consumo medido com a definição restrita à interseção fatura/leitura. Preço observado usa razão das somas; UC faturada no mês não vira UC ativa histórica.
- [x] Entregar ausências de receita paga/energia faturada como `null` e motivo; revisar schema atual que exige números. Distinguir snapshot cadastral de série financeira.
- [x] Preservar comparação anterior/ano anterior/nenhuma, sem percentual sobre referência zero/ausente; explicitar falta de declaração de fechamento mensal. Derivar opções e padrão temporal da fonte.
- [x] Para continuidade nos KPIs do Panorama, usar o serviço da etapa 4; até ele existir, responder indisponibilidade explícita. Filtro classe incompatível não altera só uma parte da fórmula.
- [x] Fazer o insight falhar explicitamente no modo Gold até rever o cálculo de energia faturada e a validação de lote. Não enviar números reais à composição sintética atual.
- [x] Reconciliar HTTP com consultas SQL independentes no total, município, classe, mês e referência; conferir receita/energia, preço/base zero, vazio e indisponibilidade. Não usar o cálculo do próprio serviço como controle independente.

**Saída verificável:** `/api/v1/panorama` em perfil Gold lê banco real e publica métricas sustentadas, ausências e lote, sem adaptação visual ainda.

## Etapa 3 — fila Gold e criação/preservação de Ordens

**Arquivos:** criar `backend/app/repositories/gold_inspections.py`; evoluir `services/inspection_analytics.py`, `services/inspections.py`, `schemas/{inspection_queue,order_snapshot,inspections}.py`, `repositories/analytics.py`, endpoints e contratos de inspeção. Manter `models/operational.py` salvo necessidade demonstrada de migração nova.

- [x] Expor fila/detalhe sobre `fila_inspecao`, com evidências do dicionário e categoria original. Definir prioridade de despacho e tratamento de `REVISAR` explicitamente, sem converter categoria em probabilidade ou pesos sintéticos.
- [x] Paginar e contar no banco depois dos filtros. Propor ordenação padrão por categoria conforme política documentada, com desempate por `id_uc`; até a política ser definida, ordenação por UC é alternativa determinística sem inferência de severidade.
- [x] Expor estimativa recuperável indisponível. Variação é contexto 1:1 com janelas fixas e meses observados, sem transformar diferença em energia recuperável.
- [x] Substituir o acoplamento de `create_from_queue` a `build_suspicion_response` sintético por uma capacidade de detalhe/evidência selecionada pelo provider. Preservar replay operacional anterior à resolução da fonte.
- [x] Acrescentar snapshot operacional v2 para categoria/evidências/lote e continuar aceitando v1/legado; `priority` operacional continua BAIXA/MEDIA/ALTA e não recebe o texto longo da Gold.
- [x] Tratar corrida recarga/criação com o contexto transacional definido na etapa 1; avaliar lock compartilhado na chave de publicação antes de ler lote/evidências na transação que grava ordem+evento. Manter recuperação de idempotência e conflitos existentes.
- [x] Em banco isolado, criar ordens controladas, registrar resultados/transições e capturar IDs/versões/snapshots/eventos; executar recarga nova, repetição e carga que falha. Conferir preservação integral, replay, uma ativa por UC, UC removida e lote obsoleto. Não usar o banco vazio atual como prova.

**Saída verificável:** criação de ordem por HTTP usa evidência real congelada; consulta e ciclo operacional permanecem independentes da Gold corrente.

## Etapa 4 — Operação real na API e continuidade do Panorama

**Arquivos:** criar `backend/app/repositories/gold_operations.py`; evoluir `services/operations.py`, fronteira compartilhada de continuidade em `services/analytics.py`, `schemas/{operations,analytics}.py`, `api/v1/endpoints/operations.py`; atualizar contrato DEV-08 e registrar extensão aprovada da ADR-0015.

- [x] Consultar `indicadores_dec_fec` para série/ranking/resumo/detalhe agregado, mantendo numeradores originais. Opções de alimentadores e município vêm do lote/cadastro, sem usar interrupções sintéticas.
- [x] Implementar revisão de denominador cadastral atual e cobertura observada; `ucs_interrompidas` não mede cobertura da fonte. Não somar UCs distintas mensais para afirmar unicidade na janela.
- [x] Acumular numeradores por janela e usar uma base por alimentador somente quando constante e válida. Tratar denominação variável, zero, ausência de mês e janela fora da fonte explicitamente.
- [x] Implementar consolidado e elegibilidade conforme definição Gold documentada; bases excluídas ficam visíveis. Não declarar homologação regulatória ou completude de origem sem evidência.
- [x] Aceitar município/alimentador; rejeitar classe/bairro incompatíveis. Compartilhar essa capacidade com Panorama, sem duplicar fórmula.
- [x] Publicar detalhe agregado e indisponibilidade de eventos individuais. Não inventar paginação de ocorrências: eventual paginação de série tem entidade e total próprios, documentados.
- [x] Reconciliar via HTTP um mês, vários meses, alimentador e município com SQL independente; verificar razão dos numeradores, desempates no ranking, exclusões e consistência com Panorama no mesmo lote.

**Saída verificável:** endpoints de Operação sustentam série/ranking/consolidado com dados reais e limites explícitos; investigação individual permanece dependente de nova exportação.

## Etapa 5 — volume real e revisão da integração da API

**Arquivos:** repositórios das etapas anteriores, eventuais novas revisões em `backend/alembic/versions/`, contratos/runbook e evidência em `docs/plans/`. Nunca editar migração histórica `goldv1000001` para instalar índice novo.

- [ ] Medir consultas reais de total, filtros seletivos/amplos, contagem, ordenação, páginas inicial/final e janela máxima; registrar `EXPLAIN (ANALYZE, BUFFERS)`, latência e tamanho de resposta. Acordar orçamento de latência antes de afirmar aprovação de desempenho.
- [ ] Avaliar índices de continuidade por competência, fila por filtro/ordem e ordens por ordenação temporal a partir dos planos, não automaticamente. Validar custo de carga, locks e regressões se houver índice novo.
- [ ] Reconciliar recortes município/classe/bairro entre tabelas onde o grão permitir; comparar com respostas reais. Separar arredondamento de divergência semântica e documentar tolerância de energia quando necessária.
- [ ] Exercitar leituras durante recarga e rejeição de `expected_lote` antigo, junto com o cenário operacional da etapa 3. Fonte real não pode regressar para fixture.
- [ ] Executar gates de backend pertinentes à mudança conforme `backend/AGENTS.md`, revisão de contrato e evidência reproduzível; registrar comandos e limitações, sem reutilizar contagens antigas como execução nova.
- [ ] Publicar guia de consumo HTTP com campos disponíveis/indisponíveis e lote, sem amostras identificáveis, e revisar critérios de aceite da API. Não concluir WEB por haver apenas HTTP.

**Saída verificável:** API pronta para integração do frontend, com consultas reconciliadas, comportamento de volume medido e preservação operacional demonstrada.

## Etapa 6 — adaptação posterior das telas e aceite integrado

**Arquivos:** pontos frontend listados no mapeamento; `docs/services/{backend,frontend}.md`, contratos, PRD e decisões afetadas.

- [ ] Adaptar decoders/tipos/hooks antes de ativar o perfil Gold integrado; tratar `null`, categoria, snapshot v2 e detalhe sem eventos. Preservar leitura histórica v1/legado.
- [ ] Propagar lote esperado entre consultas relacionadas, invalidar dados após troca e distinguir lote histórico de uma ordem do atual.
- [ ] Ajustar rótulos, fundamentos, opções de filtros, estados e séries às definições da API, com ausência/zero/erro distintos. Não mover fórmulas para React.
- [ ] Adaptar insight apenas com fronteira IA própria e contexto recalculado no servidor sobre a mesma métrica/lote; pode continuar indisponível até sua integração específica.
- [ ] Executar jornadas reais de Panorama, fila→criação→ordens e Operação; validar filtros, recarga, vazio/erro e amostras reconciliadas com a Gold. Conferir ambos os temas, teclado e comportamento responsivo nas áreas alteradas.
- [ ] Atualizar evidências do PRD e Trello conforme disponibilidade; marcar conclusão somente dos critérios efetivamente atendidos. Registrar lacunas de WEB-02/03/04/06 e dependências de exportação/escopo.

**Aceite DEV-13.1:** jornadas previstas consultam o mesmo lote real, com amostras Gold → banco → API → portal reconciliadas e ordens preservadas após novas cargas. A carga local e o mapeamento atual, isoladamente, não atendem esse aceite.

## Ponto de partida recomendado

A próxima mudança de código é a **etapa 1**, seguida do Panorama financeiro da etapa 2. Ela torna a conexão com a Gold verificável por HTTP e estabelece o contrato que as telas consumirão depois. Operação e fila avançam sobre essa base; a troca visual fica para a etapa 6.
