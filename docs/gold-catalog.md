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

## Atendimento mensal e histórico acumulado

| ID lógico | Medida e fonte única | Tempo e prontidão |
| --- | --- | --- |
| `service.attendance` | Contagem de `protocolo` em `atendimentos_uc`; não conta tratativas | Abertura em UTC, projetada por mês; `atendimento.mensal`, C14/C15 e cobertura fechada do recorte |
| `service.satisfaction` | Média das notas não nulas dos protocolos; não média de médias | Mesmo recorte por abertura UTC e mesma prontidão mensal |
| `service.accumulated_attendance` | Soma de `total_chamados_callcenter` em `visao_360_uc` | Histórico publicado sem intervalo conhecido; `atendimento.uc_acumulado` e C14 |
| `service.accumulated_satisfaction` | Média das notas individuais em `atendimentos_uc` | Histórico publicado sem intervalo conhecido; `atendimento.uc_acumulado` e C14 |

Notas zero são válidas. Ausência de nota não vira zero; sem notas válidas não há média. Nenhuma escala máxima é presumida. A carga e C14 verificam as flags e a sanitização das notas; C15 verifica abertura/ausência de data e cobertura. Zero mensal só pode ser publicado quando a prontidão comprovar cobertura fechada/zero confirmado; ausência de linhas sozinha não o autoriza.

Os indicadores acumulados aceitam somente a frase explícita “histórico acumulado”, sem início, fim ou granularidade inventados. A restrição vale na construção e revalidação do plano e na seleção Backend. Indicadores de calendário não aceitam essa frase. A frase do plano identifica ausência de período, não uma certificação de completude histórica. O envelope interno continua v1, sem novo tipo de janela ou datas sentinelas.

Nesta adaptação, atendimento admite apenas filtro por UC; outros recortes não provocam joins nem descarte de filtros. Nenhuma tabela de titular, nome, CPF, endereço ou texto livre é autorizada por esse catálogo.

## Disponibilização ao Backend

O artefato interno `backend/app/catalogs/gold_v2.json` contém as onze métricas e suas regras físicas versionadas. `app.services.gold_catalog.load_gold_catalog()` o carrega no Backend e recusa versão, tabela, coluna, tipo, grão, projeção temporal, fórmula malformada, nulidade ou dependência incompatíveis com os modelos instalados. Soma/média de texto são recusadas mesmo quando o tipo declarado coincide com a coluna; DEC/FEC só permitem granularidade mensal.

`select_catalog_source()` escolhe uma única fonte pelos filtros e capacidades fornecidos e confere o modo temporal. Não executa SQL, não comprova autorização dos valores, não resolve períodos relativos e não certifica controles: o coordenador/executor futuro ainda precisa revalidar plano completo, escopo, publicação e prontidão do recorte. O consumidor deve usar apenas um catálogo validado pelo carregador. Não há novo endpoint nem exposição desse artefato ao portal/modelo.

A declaração de autoria nesta etapa continua em `grid360_gold_mapping.py`; um teste compara exatamente seu resultado com o artefato Backend e carrega este em outro processo, impedindo versões divergentes entre serviços. Regeneração a partir de `ai-agent/`:

```powershell
python -c "from pathlib import Path; from app.profiles.grid360_gold_mapping import GRID360_GOLD_MAPPING as m; Path('../backend/app/catalogs/gold_v2.json').write_text(m.model_dump_json(indent=2)+'\n', encoding='utf-8')"
```

O núcleo de planejamento não importa o mapeamento físico nem o Backend. Nenhum relacionamento entre fatos está autorizado; as chaves declaradas são as chaves primárias das fontes. Não há conversão de unidade implícita. Fórmulas/nomes físicos não são instruções de prompt.

## Limites e próximas integrações

Atendimento e disponibilização do catálogo físico deixaram de ser pendências desta fatia. As onze métricas e a compatibilidade entre serviços são preparação testada, sem consulta Gold implantada. Capacidades candidatas ainda não liberadas permanecem explicitamente fora do perfil; a presença de faturas, medidores, decomposição ou fila no schema não aprova suas medidas automaticamente.

A composição de perguntas/insights Gold e o executor pertencem às etapas de integração correspondentes. Vocabulário amplo, valores dinâmicos e resolução de períodos serão conferidos no PR de linguagem. Não presumir aprovação de controles/metodologia ou conclusão integral do cartão por existirem metadados e testes; os critérios transversais e o estado do consumidor continuam necessários.
