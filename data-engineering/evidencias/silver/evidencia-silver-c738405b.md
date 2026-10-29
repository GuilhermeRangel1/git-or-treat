# Evidência da Silver — execução `20261026T225331Z_c738405b`

**Escopo:** camada Silver (DE-02 e DE-03). Este relatório registra o que foi conferido no Databricks sobre a execução
indicada, sem valores financeiros nem de energia. Não conclui requisito: DE-02 e DE-03 permanecem em validação até o
run limpo de ponta a ponta e a revisão humana (ver [PRD](../../../docs/PRD.md)).

## 1. Execução

| Item | Valor |
| --- | --- |
| Execução da Silver | `20261026T225331Z_c738405b` |
| Lote Bronze de entrada | `20261026T220920Z_9168e7ab` |
| Estado | `CONCLUIDO` (registrado em `silver.controle_silver`) |
| Ponteiro de publicação | `silver.controle_publicacao` com uma única linha, apontando para esta execução |
| Origem da execução | Job `v-energy-grid-360`, run de 26/10/2026 (ID `143094252373760`, 42 min 49 s, quatro das cinco tarefas, sem `Exportacao_Gold`), com retomada (repair run) das tarefas `Bronze_to_Silver` e `Silver_to_gold` |
| Gold oficial | `GOLD_20261027T014656Z_81c5530b`, gerada por run isolado da tarefa `Silver_to_gold` (ID `302306640423869`, 26/10/2026, `AMBIENTE=prod`) |
| Exportação dos CSVs | Tarefa `Exportacao_Gold` rodada isoladamente em 28/10/2026 (IDs `717942317963199` e `1029191300581647`; o segundo é o que está no Volume) |

## 2. Roteiro e autoria

- Roteiro: `validacao_silver_v1`, somente leitura, executado no Workspace sobre esta execução.
- Resultado: **32 verificações, 0 falhas.**
- O roteiro foi elaborado com assistência de IA e conferido contra o código do notebook. Execução e conferência no
  Databricks por Júlia Tenório Calado. Revisão humana por outra pessoa do time: pendente.

## 3. O que foi conferido

| Tema | Resultado |
| --- | --- |
| Identificação da execução | O roteiro imprime o ID da execução e do lote Bronze lidos de `silver.controle_publicacao`; coincidem com os da seção 1. |
| Texto com encoding quebrado | `bairro`, `municipio` e `logradouro` de `unidades_consumidoras` sem caso suspeito; varredura em todas as colunas de texto das 9 tabelas publicadas: nenhum caso suspeito. |
| Bairro (D61) | O reparo de encoding está ativo. Sobre a mesma entrada Bronze, a Silver sem reparo tinha 331 bairros distintos; com reparo, 272. As UCs com bairro reparado estão todas presentes na Silver, e nenhum par município-bairro tem mais de uma grafia depois de normalizar espaço e hífen. |
| Fatura × Silver × Gold | Faturas com leitura mais faturas sem leitura fecham com o total das faturas; a receita da Silver e a da Gold não têm divergência, ao centavo, por competência e por classe. |
| Cronologia de datas | Nenhuma violação em instalação ≤ retirada (medidores), abertura ≤ encerramento (ocorrências) e abertura ≤ fechamento (atendimentos); nenhum medidor com manutenção anterior à instalação; nenhuma fatura com pagamento ou vencimento anterior à emissão. |
| Valores impossíveis | Nenhuma fatura com valor negativo ou inconsistente, leitura com consumo negativo ou decrescente, nota fora de 0–10, ocorrência com duração negativa ou geração distribuída com potência menor ou igual a zero nas tabelas publicadas. |
| Coordenadas | Dentro dos limites matemáticos (latitude e longitude), sem nulo e sem o par (0, 0). O case não define limites geográficos, e nenhuma regra de faixa regional foi adotada. |
| Situação da fatura | O status só assume `PAGA` e `EM ABERTO`; não há divergência entre o status e a data de pagamento. |
| Classe das UCs | Todas as UCs reais pertencem às cinco classes esperadas. |
| UCs de teste | UCs com identificador `TESTE` existem na Silver e são excluídas da Gold. |
| Quarentena | Todo registro que não entra na Silver tem motivo registrado em `silver_hist.quarentena`; as contagens por motivo ficam na saída do roteiro e não são publicadas aqui. |

## 4. Decisões que valem para esta execução

- **Datas ambíguas de dia/mês:** permanecem em quarentena (D36, D53); a Silver não escolhe a ordem.
- **Sentinela `9999-12-31` e datas futuras:** preservadas e marcadas com flags; não se presume quitação (D15, D55).
- **`data_ligacao` anterior a 1950:** a Silver preserva o valor. **Proposta (D62), ainda não implementada:** transformar esses
  valores em nulo na Gold, na próxima execução da Gold. A Gold oficial `81c5530b` ainda contém o valor original.

## 5. Limites

- A evidência vale para esta execução. O run limpo final gera outra execução da Silver, e o roteiro deve ser repetido
  sobre ela.
- O roteiro mostra que não há violação nos dados publicados. Ele não prova que as regras cobririam um lote futuro com
  defeitos novos.
- Os roteiros `validacao_silver_v1` e `validacao_gold_v4` não estão versionados neste repositório (ver seção 6).
- Valores, contagens detalhadas, identificadores de UC e coordenadas por município ficam nas saídas do Databricks e não são publicados aqui.

## 6. Roteiros de verificação e como repetir

Os roteiros são notebooks Python somente leitura, na pasta `revisao_gold` do Workspace de Dados no Databricks. Ficam
fora do repositório porque as saídas trazem identificadores de UC, coordenadas e valores do case.

- `validacao_silver_v1`: lê `silver_publicada.*` e os controles da Silver; resultado nesta execução: 32 verificações, 0 falhas.
- `validacao_gold_v4`: lê `workspace.gold.*` e `gold.controle_gold`; resultado sobre a Gold `81c5530b`: 0 falhas. O total
  de verificações impresso não coincide com a contagem das linhas da saída; por isso só se cita "0 falhas" até a revisão
  do notebook.

Para repetir:

1. Abrir o notebook em `revisao_gold`, com compute Serverless.
2. Conferir, na primeira saída, que a execução da Silver (ou da Gold) lida é a que se quer verificar.
3. Executar todas as células. O esperado é nenhuma falha.
4. Registrar apenas o identificador da execução e o resultado ("N verificações, 0 falhas"). Não copiar saídas para o
   repositório, para PRs, para issues nem para ferramentas externas.