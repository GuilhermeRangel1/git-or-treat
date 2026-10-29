# Prontidão da Gold por capacidade

**Cartão:** GENAI-02. **Versão:** `gold-readiness-v1`. **Código:** `ai-agent/app/readiness/`. **Testes:** `ai-agent/tests/test_gold_readiness.py`.

**Natureza:** preparação. A matriz e os estados são verificáveis com fatos sintéticos, mas nada aqui prova a Gold real nem substitui GENAI-06, GENAI-07 ou GENAI-10. Este documento não traz nenhum valor, contagem, período ou identificador de lote.

## O que é

Uma função pura, `evaluate_readiness(facts) -> ReadinessReport`, sem I/O, banco ou rede. O Backend observa a publicação carregada no banco local e informa os fatos; a função devolve o estado do lote e, para cada capacidade, se ela pode ser usada e por quê. O catálogo (GENAI-03), o executor e o portal consomem o relatório.

**Entrada (`PublicationFacts`):** `readiness_version`, `batch_ref` atual, `expected_batch_ref`, `tables` (por tabela Gold: `present`, `has_rows`, `batch_ref` e `periods` no formato `AAAA-MM`, sem repetição), `approved_controls` e `backend_reachable`. Campo desconhecido, versão diferente, tabela fora das sete oficiais, `batch_ref` fora do formato, competência inválida ou repetida e fatos contraditórios (tabela ausente com linhas, por exemplo) são recusados com erro de validação; nada é corrigido.

**Saída (`ReadinessReport`):** `readiness_version`, `lot_state`, `batch_ref` e, por capacidade, `status` (`available` ou `unavailable`) e `reasons`. A saída tem só códigos e estados.

## Estados do lote e precedência

A primeira regra que se aplica define o estado:

| Ordem | Condição | Estado | Efeito nas capacidades |
| ---: | --- | --- | --- |
| 1 | Backend não alcançou o banco | `unavailable` | Todas indisponíveis com `backend_unavailable`. Indisponibilidade nunca vira vazio nem ausência legítima. |
| 2 | Lote atual sem `batch_ref`, ou alguma tabela presente sem `batch_ref` | `invalid` | Todas com `publication_unidentified`. |
| 3 | `expected_batch_ref` definido e diferente do atual | `stale` | Todas com `publication_stale`. |
| 4 | Tabelas presentes com `batch_ref` diferentes entre si ou do atual | `mixed` | Todas com `publication_mixed`. |
| 5 | Nenhuma tabela com linhas | `empty` | Avaliação por capacidade: `table_empty` ou `table_missing`. |
| 6 | Alguma tabela exigida ausente ou sem linhas | `partial` | Só as capacidades que dependem dela ficam indisponíveis. |
| 7 | Demais casos | `ready` | Avaliação por capacidade. |

Nos estados 1 a 4, as capacidades fora da Gold também levam `source_not_in_gold`. Uma capacidade bloqueada nunca derruba as outras.

`invalid` e `mixed` são casos distintos: `mixed` exige que todos os `batch_ref` estejam presentes e que haja divergência entre eles; a falta de identificação é sempre `invalid`, nunca `mixed` nem `ready`. Uma publicação legada, sem origem validada, cai em `invalid`, como prevê o [contrato de consulta](contracts/genai-query-execution.md#lote-da-gold-batch_ref) para lote sem manifesto carregado e validado.

## Avaliação por capacidade

Uma capacidade fica `available` só quando não acumula nenhum motivo:

- tabela exigida ausente → `table_missing`; presente sem linhas → `table_empty` (zero é diferente de ausência: tabela vazia nunca é lida como zero);
- com coluna temporal `competencia`: sem competências → `period_missing`; competências com lacuna ou em número menor que `min_consecutive_months` → `period_insufficient`;
- controle exigido fora de `approved_controls` → `control_pending`;
- definição ainda dependente de Dados → `definition_pending`;
- fonte que não existe na Gold → `source_not_in_gold`, sempre indisponível.

Os motivos saem sem repetição, na ordem da enumeração `ReasonCode`, e a mesma entrada produz sempre a mesma saída.

## Códigos

`table_missing`, `table_empty`, `period_missing`, `period_insufficient`, `definition_pending`, `control_pending`, `source_not_in_gold`, `publication_stale`, `publication_mixed`, `publication_unidentified`, `backend_unavailable`.

## Capacidades, tabelas e controles

Perguntas (P) e controles (C) são os de [gold-coverage-v0.md](gold-coverage-v0.md); tabelas, as do [dicionário Gold](dicionario_gold.md).

| Capacidade | Domínio | Tabelas | Período | Controles | Definição |
| --- | --- | --- | --- | --- | --- |
| `faturamento.receita` (P1, P4, P5) | faturamento | `diagnostico_receita` | `competencia` | C01, C02, C04 | aprovada |
| `faturamento.receita_bairro` (P3) | faturamento | `consumo_receita_bairro` | `competencia` | C12, C13 | aprovada |
| `faturamento.preco_volume` (P2) | faturamento | `diagnostico_receita` | `competencia` | C01, C02 | pendente |
| `faturamento.faturas_em_aberto` (P8) | faturamento | fora da Gold | — | — | — |
| `consumo.mensal_uc` (P7, P20) | consumo | `consumo_mensal_uc` | `competencia` | C03, C10 | aprovada |
| `consumo.variacao_uc` (P6) | consumo | `variacao_consumo_uc` | janelas fixas | C08, C09 | pendente |
| `interrupcoes.dec_fec` (P16, P17, P21) | interrupções | `indicadores_dec_fec` | `competencia` | C11 | aprovada |
| `interrupcoes.uc_acumulado` (P10) | interrupções | `visao_360_uc` | sem competência | nenhum | pendente |
| `atendimento.uc_acumulado` (P11) | atendimento | `visao_360_uc` | sem competência | nenhum | pendente |
| `apoio.fila_inspecao` (P14) | apoio | `fila_inspecao` | sem competência | C06, C07 | pendente |
| `apoio.medidor_uc` (P9) | apoio | fora da Gold | — | — | — |
| `apoio.energia_recuperavel` (P15) | apoio | fora da Gold | — | — | — |

Nenhuma capacidade declara `min_consecutive_months`: não há janela mínima aprovada por Dados. Toda capacidade com `competencia` exige, ainda assim, competências sem lacuna.

## Pendências

**Definições de Dados** (`definition_pending`):

- `faturamento.preco_volume`: faltam a tarifa homologada e o método aprovado de decomposição preço × volume.
- `consumo.variacao_uc`: janela e mínimo de meses da pergunta de GD ainda abertos; P1 e P2 são fixos na Gold.
- `interrupcoes.uc_acumulado` e `atendimento.uc_acumulado`: só há totais acumulados por UC, sem mês (e, no atendimento, sem motivo), e nenhum controle independente do domínio.
- `apoio.fila_inspecao`: mapeamento dos rótulos de resultado de inspeção pendente (issue #39).

**Controles:** a seção (g) de `gold-coverage-v0.md` define C01 a C13. Os controles aprovados vêm na entrada, não no código; C13 só libera `faturamento.receita_bairro` quando o Backend o informar como aprovado. Controles posteriores (como C15) não estão documentados e não são exigidos por nenhuma capacidade; quando forem, entram em `requirements.py` com a capacidade correspondente.

**Fora da Gold** (`source_not_in_gold`): faturas em aberto, medidor e energia a recuperar. Dependem de complemento da Gold por Dados.

**Lote:** o `batch_ref` segue o formato proposto em [genai-query-execution.md](contracts/genai-query-execution.md#lote-da-gold-batch_ref). Enquanto ele não estiver nos schemas de evidência da `develop`, o módulo declara o mesmo formato localmente.

## Limites

- Preparação: os testes usam somente fatos sintéticos e não provam a Gold real.
- Não substitui GENAI-06, GENAI-07 nem GENAI-10, nem a carga e reconciliação do Backend (DE-06).
- Não decide se uma resposta está correta: indica apenas se a capacidade pode ser consultada com aquele lote.
- Uma mudança incompatível na entrada ou na saída exige nova `readiness_version`.
