# Status report intermediário

**Requisito:** ENT-05. **Corte:** 03/11/2026, Lote Gold `GOLD_20261103T173853Z_76c37784` (Silver `20261103T171539Z_12682bfc`). O estado oficial dos requisitos continua no [PRD](PRD.md); este relatório resume o que existe, o que foi validado e o que falta. Nenhum valor em R$, contagem de registros ou identificador de UC consta aqui.

## Data e escopo do corte

Corte em 03/11/2026, um dia antes da entrega final (04/11). Cobre a camada de dados completa (Bronze, Silver, Gold e exportação), o diagnóstico da receita e o estado de integração com portal e agente de IA. A versão do dataset é a extração única do case.

## Entregas demonstráveis

| Entrega | Estado | Evidência |
| --- | --- | --- |
| Workflow de seis tarefas, run limpo de ponta a ponta | Executado | [registro do run](../data-engineering/evidencias/workflow/run-limpo-250327107715287.md) |
| Silver com validação automatizada (32 de 32 verificações) | Executado | [evidência Silver](../data-engineering/evidencias/silver/evidencia-silver-c738405b.md) e registro do run |
| Gold com quinze tabelas analíticas, conferida pela bateria de 03/11 (chaves, órfãos, DEC/FEC recalculados, decomposição fechando e reprodução dos percentuais do diagnóstico) | Executado | registro do run |
| Exportação CSV v2 concluída; o validador da exportação aceitou o lote (manifesto publicado) | Executado | registro do run |
| Cadastro restrito separado, sem CPF nem endereço | Gerado e entregue ao backend por canal privado | registro do run |
| Dicionário da Gold | Publicado | [dicionário](dicionario_gold.md) |
| Diagnóstico da receita com decomposição preço × volume | Escrito; revisão da equipe pendente | [diagnóstico](revenue-diagnosis.md) |
| Portal e agente de IA lendo o lote real | Em integração pelo backend e pela GenAI | [PRD](PRD.md) |

## Primeiras hipóteses sobre a receita

| Hipótese | Dado testado | Resultado | Limite |
| --- | --- | --- | --- |
| A receita subiu cerca de 8% | Decomposição na base comum (96,3% das UCs) | +7,97% reproduzido | É receita faturada, não recebida |
| O reajuste explica o ganho de preço | Preço efetivo observado | +10,81% de preço, compatível com o reajuste de 10,5% | Preço efetivo não é tarifa homologada; mix e bandeiras também entram |
| O volume caiu quase 4% | Consumo medido nos pares UC/mês | −4,02% reproduzido | É consumo medido, não energia faturada |
| A queda de volume se concentra em classes específicas | Abertura por classe | Comercial −8,87% e residencial −5,11% do próprio faturamento base; industrial estável (+0,14%) | Descreve o que mudou, não prova a causa |
| Faturas sem leitura inflam a receita | Parcela fora da base comum | +1,74% da variação total, cerca de 1/5 da alta | Ponto que mais merece auditoria |

## Riscos, bloqueios e decisões

- **Energia faturada:** a fonte não traz kWh faturado. O volume do diagnóstico é consumo medido. A forma de rotular isso no portal e na IA é decisão do grupo.
- **Energia recuperável por UC:** a Gold publica a estimativa por consumo, condicional à confirmação da irregularidade, com faixa de 90%, validada em teste temporal; sem estimativa para UCs com menos de 6 meses de consumo, que mostram a referência histórica. O `aceite_web04` segue pendente e o portal precisa exibir o campo.
- **Cobertura de atendimentos e ocorrências:** certificada (`FECHADO`) no total do domínio. Por alimentador continua `NAO_CERTIFICADA`, pois exigiria evidência externa de fechamento.
- **Troca de lote:** o lote novo exige que backend e GenAI recarreguem e refaçam as evidências.
- **Confidencialidade:** o case é confidencial e o repositório é público; o tratamento permitido deve ser confirmado com a organização antes de publicar.

## Próximos marcos

| Marco | Data | Responsável | Como se comprova |
| --- | --- | --- | --- |
| Decisão sobre cobertura e rótulos de energia | 03/11 | Grupo | Registro no PRD |
| Revisão e merge do diagnóstico | 04/11 | Revisão da equipe | Pull request mergeado |
| Entrega final no repositório | 04/11 | Grupo | `develop` revisada |
| Prévia | 05/11 | Grupo | Apresentação |
| Banca | 10/11 | Grupo | Demonstração ao vivo |
