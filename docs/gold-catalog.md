# Catálogo Gold v2 e mapeamento em adaptação

A referência atual é [Gold CSV v2](contracts/gold-csv-v2.md), com quinze tabelas analíticas no schema Backend `gold_v2`. O perfil lógico `GRID360_GOLD_PROFILE` preserva IDs de negócio e não contém tabelas físicas. O mapeamento `gold-catalog-v2` exige schema `gold-csv-v2` e prontidão `gold-readiness-v2`. A versão do envelope interno v1 é independente dessas versões de dados.

## Primeira fatia atualizada

- Receita representa o faturamento total, inclusive faturas sem leitura; não representa pagamento.
- Consumo representa as leituras observadas, inclusive sem fatura; não é energia faturada.
- Ticket médio usa receita dividida por UCs faturadas no mês, como razão de somas. Não é contagem de UCs únicas em todo o intervalo.
- Preço médio observado usa somente receita e consumo da mesma base comparável, com fatura e leituras integralmente válidas. Não é tarifa homologada.
- Consumo médio usa UCs com leitura no mês como denominador; não divide consumo independente por UCs faturadas.
- DEC/FEC preservam maiúsculas físicas, grão alimentador/competência e a exigência de alimentador; não são somados entre meses/alimentadores.
- Nulos continuam ausência; denominador nulo ou zero não gera razão válida. Cadastro é atual, sem vigência histórica inventada.

As fontes são únicas por consulta; dimensões incompatíveis não provocam join de fatos ou descarte silencioso de filtros. O mapeamento não executa SQL. Cada métrica declara suas dependências de prontidão, além da capacidade da fonte selecionada: uma tabela contendo receita e consumo não autoriza automaticamente ambos os domínios. Preço observado exige prontidão de faturamento e consumo. Dependências inexistentes ou não aprovadas são rejeitadas pelo validador.

Os sete indicadores desta fatia são comprovados pelo planejador público e pela seleção do mapeamento contra o schema Backend. DEC/FEC sem filtro de alimentador são reconhecidos no planejamento, mas a seleção recusa a fonte; reconhecer o indicador não autoriza a consulta. Nomes completos como “ticket médio” e “consumo médio por UC” não são confundidos com pedidos adicionais de média ou agrupamento; qualificadores externos continuam exigindo esclarecimento quando não suportados. Arredondamento de apresentação permanece uma proposta técnica, sem homologação implícita de negócio.

## Compatibilidade e fonte física

Os módulos `grid360_gold_v1.py` e `grid360_gold_mapping_v1.py` conservam explicitamente os contratos históricos e sua regressão. O arquivo `dictionary_gold.toml` do PR #46 continua legado; não deve ser carregado como se representasse quinze tabelas v2. O [documento histórico](gold-catalog-v1.md) conserva a fotografia anterior e suas pendências; ele não descreve o estado corrente.

Os testes atuais confrontam o validador público com as quinze tabelas reais de `backend/app/models/gold_v2.py`, em processo separado, sem importar Backend no runtime GenAI. Renomear coluna, trocar tipo, grão, período ou versão deve falhar. São metadados de schema, sem registros do lote.

O planejador público `core.question.plan` é exercitado com perfil Gold, envelope de publicação v2 e escopo controlado. Gera IDs, unidades e fonte lógica sem consultar banco ou chamar evidência. Isso comprova planejamento, não execução da Gold. O frontend não é dependência dessa prova.

## Pendências desta adaptação

Esta primeira fatia não conclui o catálogo: atendimento mensal/acumulado ainda precisa de métricas e mapeamentos próprios, sem inventar períodos; fontes atuais de faturas, medidores, decomposição e fila não podem ser descritas como ausentes. Capacidades com definição consumidora pendente continuam bloqueadas. O mapeamento físico ainda precisa ser disponibilizado ao executor Backend sem acoplar o núcleo ao SQL.

A composição implantada de perguntas/insights Gold e o executor pertencem às etapas de integração correspondentes; este catálogo não ativa o banco nem remove guardas existentes. Vocabulário e resolução de períodos serão conferidos no PR de linguagem. Não presumir aprovação de controles ou metodologia por atualizar o número da versão.
