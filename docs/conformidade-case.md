# Conformidade com o case Visagio

Mapa entre o enunciado do case (seções 4 a 6) e o que o repositório entrega, separando **obrigatório**, **diferencial** (marcado como tal no case) e **extra** (iniciativa do time além do pedido). O estado oficial de cada ID continua no [PRD](PRD.md); esta página aponta a evidência e o que falta. Sem valores em R$, contagens de registros ou identificadores de UC.

**Como ler a coluna Situação:** `Evidência` = verificado no repositório ou em execução registrada. `Dono confirma` = o estado vem do PRD e a evidência precisa ser conferida pelo responsável antes de afirmar conclusão. Esta página não promove nenhum requisito a concluído.

## 1. Engenharia de Dados (case 5.1 e 4)

| ID | Tipo | Requisito do case | Situação | Evidência ou pendência |
| --- | --- | --- | --- | --- |
| DE-01 | Obrigatório | Ingerir os 8 arquivos na Bronze, preservando o conteúdo | Evidência | Run limpo do Workflow; reconciliação por origem com delta zero. [Registro do run](../data-engineering/evidencias/workflow/run-limpo-250327107715287.md) |
| DE-02 | Obrigatório | Silver confiável, problemas de qualidade tratados | Evidência | Roteiro de validação da Silver, 32 de 32 verificações no run limpo. [Evidência Silver](../data-engineering/evidencias/silver/evidencia-silver-c738405b.md) |
| DE-03 | Obrigatório | Integridade referencial entre medição, faturamento e cadastro | Evidência | Registros órfãos segregados na quarentena da Silver; conferências Gold × Silver no registro do run |
| DE-04 | Obrigatório | Gold modelada a partir das perguntas de negócio | Evidência | Quinze tabelas analíticas; bateria de conferência da Gold de 03/11 sem falhas. [Dicionário](dicionario_gold.md) |
| DE-05 | Obrigatório | DEC e FEC por alimentador | Evidência, com limite | Tabela `indicadores_dec_fec`. Indicador simplificado conforme o case, sem selo de cobertura por alimentador (exigiria evidência externa de fechamento). Não é conformidade regulatória |
| DE-06 | Obrigatório | Exportar a Gold em CSV para banco local | Evidência na exportação; carga no banco: dono confirma | Exportação concluída com manifesto no run de 03/11. Aceite da carga pelo backend pendente |
| DE-07 | Obrigatório | Orquestrar em Workflow reexecutável e justificar o agendamento | Evidência | Job de 6 tarefas, [YAML versionado](../data-engineering/configuracao/databricks/v-energy-grid-360.yaml) e print do run. Agendamento mensal **proposto e não ativado**, com justificativa no [guia de dados](../data-engineering/README.md) |
| DE-08 | Obrigatório | Dicionário de dados da Gold | Evidência | [dicionario_gold.md](dicionario_gold.md) |
| DE-09 | **Diferencial** | Testes de qualidade automatizados no pipeline | Parcial | Portão de qualidade na Silver e validações na Gold derrubam a tarefa quando falham. Roteiros de validação pós-run ainda não versionados |

## 2. Portal Web (case 5.2)

| ID | Tipo | Requisito do case | Situação | Evidência ou pendência |
| --- | --- | --- | --- | --- |
| WEB-01 | Obrigatório | Indicadores gerais com comparação entre períodos | Dono confirma | Integração com a Gold real (issue 75) |
| WEB-02 | Obrigatório | Variação de receita, preço × volume, por município, bairro e classe | Dono confirma | Dados prontos na tabela `decomposicao_receita`; falta conferir a tela contra o [diagnóstico](revenue-diagnosis.md) |
| WEB-03 | Obrigatório | Visão 360 da UC, inclusive conta alta | Dono confirma | Depende do carregador do cadastro restrito (nome do titular) |
| WEB-04 | Obrigatório | Fila de inspeção ordenada, com motivo e energia estimada a recuperar | Dados: validado na Gold de teste; portal: dono confirma | A Gold publica a estimativa por consumo (se confirmada) com faixa para as UCs com histórico de consumo suficiente; as demais mostram a referência histórica. O Backend ainda fixa o campo da fila em nulo (ajuste do Backend pendente). Ver seção 5 |
| WEB-05 | Obrigatório | Ordens de inspeção: gerar, atualizar status, registrar resultado, cancelar | Dono confirma | Backend e frontend |
| WEB-06 | Obrigatório | DEC e FEC por alimentador ao longo do tempo | Dono confirma | Usa `indicadores_dec_fec` |
| WEB-07 | Obrigatório | Filtros e recortes | Dono confirma | Frontend |
| WEB-08 a WEB-11 | **Diferencial** | Exportar fila; importar planilha de campo; perfis por cargo; testes do backend | Dono confirma | Branches `feat/inspecoes-campo` e `feat/web10-perfis` abertas |

## 3. Inteligência Artificial (case 5.3)

| ID | Tipo | Requisito do case | Situação | Evidência ou pendência |
| --- | --- | --- | --- | --- |
| IA-01 | Obrigatório | Perguntas em português, sem SQL | Dono confirma | Agente Text-to-SQL em `ai-agent/` |
| IA-02 | Obrigatório | Vocabulário do dia a dia ("conta de luz", "falta de luz") | Dono confirma | Plano de entendimento de perguntas em `docs/plans/` |
| IA-03 | Obrigatório | Auditar como a IA chegou à resposta | Dono confirma | [Contrato de auditoria](contracts/genai-audit.md) |
| IA-04 | Obrigatório | Insights de IA dentro das telas | Dono confirma | |
| IA-05 | Obrigatório | Agente dentro do portal | Dono confirma | |
| IA-06 | Obrigatório | Somente leitura; não pode ser manipulada | Dono confirma | Exigir testes de bloqueio de escrita e de perguntas fora do escopo |
| IA-07 | **Diferencial** | Follow-up sem repetir contexto | Dono confirma | Marcado como concluído no PRD |
| IA-08 | **Diferencial** | Avaliação automática de qualidade | Dono confirma | Regressão sintética roda no CI |

## 4. Diagnóstico, documentação e entrega (case 5.4 e 6)

| ID | Tipo | Requisito do case | Situação | Evidência ou pendência |
| --- | --- | --- | --- | --- |
| ENT-01 | Obrigatório | Diagnóstico da receita em `docs/`, com recomendações e ordem de grandeza | Escrito, revisão pendente | Branch `docs/diagnostico-receita`, sem merge na `develop` |
| ENT-02 | Obrigatório | Apresentação final (15 min + 15 min de perguntas) | **Não existe no repositório** | Banca em 10/11, prévia em 05/11 |
| ENT-03 | Obrigatório | Repositório GitHub público e organizado | Evidência, com ressalva | Estrutura dos módulos e YAML do Workflow presentes. Confirmar com a organização o tratamento de confidencialidade |
| ENT-04 | Obrigatório | README com descrição, execução, print do Workflow, links e suposições | Atualizado nesta revisão | [README](../README.md) |
| ENT-05 | Obrigatório | Status report intermediário | Preenchido nesta revisão | [Status report](status-report.md) |

## 5. Pontos que podem impedir um obrigatório

1. **Energia estimada a recuperar (WEB-04).** O case pede "quanta energia dá para recuperar em cada uma". A estimativa pela referência histórica não se sustentou por UC, mas o consumo da UC sustentou: a estimativa condicional à confirmação passou na validação temporal. Falta o portal exibi-la: o Backend ainda fixa o campo da fila em nulo e recusa a ordenação por ele. Sem esse ajuste, vale a referência histórica rotulada. Não se exibe previsão individual sem validação.
2. **Energia faturada.** A tabela de faturas não traz kWh. Nenhum processamento cria esse dado. O que fecha o assunto é uma regra formal e rotulada: energia faturada aproximada pelo consumo medido nas UC/mês com fatura elegível, aplicada igual no diagnóstico, no dicionário, no portal e na IA. A regra reproduz a queda de volume citada no case. Depende da aceitação do grupo.
3. **Integração Gold → API → portal (issue 75)** e carregador do cadastro restrito: sem isso WEB-01, WEB-03 e IA-01 não demonstram o lote real.
4. **Apresentação à diretoria (ENT-02):** sem arquivo.
5. **Confidencialidade (ENT-03):** confirmar o tratamento antes de publicar.
6. **Tabela de status do PRD:** defasada; atualizar só com evidência.

## 6. Extras, além do que o case pede

- Cadastro restrito em pacote separado, sem CPF nem endereço, nunca no repositório.
- Declaração de cobertura por domínio, com reconciliação de extração, e estados `NAO_CERTIFICADA` visíveis em vez de lacunas escondidas.
- Decomposição preço × volume com base comum, interação, faturas sem leitura, entradas e saídas, fechando sem resíduo.
- Estimativa de energia recuperável por UC pelo consumo (condicional à confirmação), validada em teste temporal e publicada na Gold com faixa de 90%; sem validação, os campos ficam nulos e vale a referência histórica.
- Lote versionado (`run_id` Silver e Gold) rastreável da exportação ao portal e à IA.
