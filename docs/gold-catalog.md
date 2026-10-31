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

Os onze indicadores desta fatia são comprovados pelo planejador público e pela seleção do mapeamento contra o schema Backend. DEC/FEC sem filtro de alimentador são reconhecidos no planejamento, mas a seleção recusa a fonte; reconhecer o indicador não autoriza a consulta. Nomes completos como “ticket médio” e “consumo médio por UC” não são confundidos com pedidos adicionais de média ou agrupamento; qualificadores externos continuam exigindo esclarecimento quando não suportados. Arredondamento half-even ocorre apenas na apresentação, com precisão declarada por métrica, sem mudar os controles. Dados registrou ausência de objeção ao arredondamento de apresentação no [PR #73](https://github.com/GuilhermeRangel1/git-or-treat/pull/73#issuecomment-6508822736).

## Compatibilidade e fonte física

Os módulos `grid360_gold_v1.py` e `grid360_gold_mapping_v1.py` conservam explicitamente os contratos históricos e sua regressão. O arquivo `dictionary_gold.toml` do PR #46 continua legado; não deve ser carregado como se representasse quinze tabelas v2. O [documento histórico](gold-catalog-v1.md) conserva a fotografia anterior e suas pendências; ele não descreve o estado corrente.

Os testes atuais confrontam o validador público com as quinze tabelas reais de `backend/app/models/gold_v2.py`, em processo separado, sem importar Backend no runtime GenAI. Renomear coluna, trocar tipo, grão, período ou versão deve falhar. Dimensões e competências precisam continuar texto; a abertura usada para mês deve continuar timestamp com fuso; as colunas monetárias mapeadas preservam precisão e escala decimais declaradas. São metadados de schema, sem registros do lote.

Os limites de calendário também são declarados em cada métrica: consultas delimitadas aceitam até 1.830 dias, teto que já era aplicado pelo planejador; DEC/FEC continuam mensais e os acumulados não aceitam datas. A política global do planejador pode reduzir esse teto, nunca ampliá-lo. Cobertura do lote continua decidindo quais períodos estão de fato disponíveis.

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

O artefato interno `backend/app/catalogs/gold_v2.json` contém as onze métricas e suas regras físicas versionadas. `app.services.gold_catalog.load_gold_catalog()` o carrega no Backend e recusa versão, tabela, coluna, família ou precisão/escala física, tipo de dimensão e competência, fuso da projeção temporal, grão, limite temporal, fórmula malformada, nulidade ou dependência incompatíveis com os modelos instalados. Soma/média de texto são recusadas mesmo quando o tipo declarado coincide com a coluna; DEC/FEC só permitem granularidade mensal.

Cada métrica também publica `label`, `definition` e `dimension_operators`. Os rótulos e as definições vêm do perfil lógico, em português e sem nomes de tabela. Os operadores são igualdade e pertinência (`eq`/`in`) apenas nas dimensões declaradas; isso não autoriza valores nem pessoas. API, evidência e portal poderão consumir os mesmos metadados nos respectivos adaptadores, sem reconstruir rótulos a partir de identificadores físicos. O teste entre serviços confronta esses campos com o perfil. A versão `gold-catalog-v2` cobre os metadados físicos e de negócio; não há endpoint novo nesta preparação.

Compatibilidade de schema não homologa outra semântica. O validador GenAI confronta os candidatos com a definição versionada do perfil/mapeamento; o carregador Backend confronta o payload candidato com o artefato distribuído. As seleções do Backend revalidam o catálogo recebido, pois mapas internos do Pydantic continuam mutáveis mesmo com modelos `frozen`; a checagem semântica GenAI usa assinaturas capturadas da definição aprovada, não os mesmos mapas mutáveis usados por consumidores. Uma coluna numérica existente não pode substituir o denominador da base comparável, nem uma soma substituir a média de notas. Alteração do catálogo exige editar e revisar sua definição versionada, regenerar o artefato e conferir ambos os consumidores e as provas independentes de fórmula. Estes controles não verificam integridade de arquivos modificados no servidor nem executam reconciliação dos dados.

`select_catalog_source()` escolhe uma única fonte pelos filtros e capacidades fornecidos, confere o modo temporal e rejeita janelas delimitadas acima do teto da métrica; revalida o objeto recebido contra o artefato versionado antes de selecionar. Não executa SQL, não comprova autorização dos valores, não resolve períodos relativos e não certifica controles: o coordenador/executor futuro ainda precisa revalidar plano completo, escopo, publicação e prontidão do recorte. Não há novo endpoint nem exposição desse artefato ao portal/modelo.

A declaração física nesta etapa continua em `grid360_gold_mapping.py`; os rótulos/definições/operadores são derivados de `grid360_gold.py`. Um teste compara exatamente o resultado com o artefato Backend e carrega este em outro processo, impedindo versões divergentes entre serviços. Regeneração a partir de `ai-agent/`:

```powershell
python -c "from pathlib import Path; from app.profiles.grid360_gold_mapping import GRID360_GOLD_MAPPING as m; Path('../backend/app/catalogs/gold_v2.json').write_text(m.model_dump_json(indent=2)+'\n', encoding='utf-8')"
```

O núcleo de planejamento não importa o mapeamento físico nem o Backend. Nenhum relacionamento entre fatos está autorizado; as chaves declaradas são as chaves primárias das fontes. Não há conversão de unidade implícita. Fórmulas/nomes físicos não são instruções de prompt.

## Cobertura do contrato de catálogo

As definições atuais são sustentadas por [dicionário Gold](dicionario_gold.md) e [contrato CSV v2](contracts/gold-csv-v2.md), que substituem as populações da preparação v1. As provas de coerência exercitam `core.question.plan`, `validate_mapping()` e `load_gold_catalog()`, nas fronteiras aprovadas.

| Critério | Evidência nesta entrega |
| --- | --- |
| Fórmula, fonte, unidade e população | Soma, contagem, média de notas, razão de somas e leitura DEC/FEC declaradas por métrica; exemplos independentes para os três denominadores de razões. |
| Grão, tempo e cobertura | Chaves reais confrontadas com modelos v2; abertura UTC, teto de 1.830 dias para datas, DEC/FEC mensais e ausência explícita de calendário no acumulado; dependências C14/C15 e prontidão por domínio. Resolução de frases e janelas concretas pertence ao GENAI-04. |
| Dimensões, operadores e nulidade | `dimension_operators` segue o perfil; fonte única cobre todos os filtros; zero certificado e nulos não são confundidos. |
| Relações, sensibilidade e conversão | Sem joins autorizados, sem conversão implícita e sem tabelas pessoais ou texto livre; catálogo fechado de medidas e dimensões. |
| Rótulos e compatibilidade entre serviços | Onze nomes/definições de negócio derivados do perfil e distribuídos com o artefato; teste entre processos e rejeição de drift físico/semântico. |
| Precisão e agregação | Half-even só na apresentação; razões preservam população, DEC/FEC não agregam e satisfação usa protocolos individuais. |

As capacidades fora das onze métricas conservam motivos específicos. A decomposição de preço observado já tem fonte/método na Gold; sua indisponibilidade na IA significa que ainda falta mapear duas janelas, estados e controles consumidores, não que seja necessária uma tarifa homologada. Faturas distinguem valor nominal declarado de saldo indicativo, variação usa janelas fixas, medidor/fila ainda exigem seleção e controles consumidores, e a média histórica de recuperação não equivale à estimativa individual de uma UC. Nenhuma dessas fontes é anunciada como ausente do schema v2.

## Limites e próximas integrações

Atendimento e disponibilização do catálogo físico deixaram de ser pendências desta fatia. As onze métricas e a compatibilidade entre serviços são preparação testada, sem consulta Gold implantada. Capacidades candidatas ainda não liberadas permanecem explicitamente fora do perfil; a presença de faturas, medidores, decomposição ou fila no schema não aprova suas medidas automaticamente.

A composição de perguntas/insights Gold e o executor pertencem às etapas de integração correspondentes. Vocabulário amplo, valores dinâmicos e resolução de períodos serão conferidos no PR de linguagem. Não presumir aprovação de controles/metodologia ou conclusão integral do cartão por existirem metadados e testes; os critérios transversais e o estado do consumidor continuam necessários.


## Progresso por critério — GENAI-03 (31/10/2026)

Conferência das dez caixas do cartão técnico: **sete critérios comprovados e três
parciais**. Essa contagem mede a checklist do catálogo; não é percentual de entrega
da IA integrada nem altera os estados IA-01 a IA-06 do PRD.

| Checklist / item | Situação | Evidência ou trabalho restante |
| --- | --- | --- |
| Implementação 1 — definição, fórmula, unidade, grão, filtros e limitações aprovadas | Parcial | Onze métricas mapeadas e confrontadas com dicionário/modelos v2. Falta revisão explícita da semântica v2 e atendimento com Dados; o comentário de 29/10 no PR #73 ainda descreve a interseção v1. |
| Implementação 2 — tempo próprio e ausência de competência | Comprovado | Coluna mensal UTC e acumulado sem datas; planejador e seleção Backend rejeitam calendário incompatível. |
| Implementação 3 — agregações e denominadores | Comprovado | Razões de somas, satisfação por nota de protocolo e DEC/FEC sem consolidação; regressões de fórmula/unidade e denominadores. |
| Implementação 4 — sensibilidade e catálogo fechado | Comprovado | Sem joins ou conversões implícitas, sem cadastro pessoal; rejeição de colunas sensíveis e de métrica desconhecida na seleção direta. |
| Implementação 5 — rótulos e descrições na API/portal | Parcial | Rótulos versionados e iguais no perfil e artefato Backend; uso pela evidência/API/portal depende dos adaptadores de GENAI-07/11/12. |
| Implementação 6 — drift e capacidade incompleta | Comprovado | Rejeição de divergências de unidade, fórmula, grão, schema, tipo, precisão, fuso e dependências. |
| Robustez 1 — contrato completo por métrica | Comprovado | Operações, dimensões, operadores, agregação, grão, unidades, precisão, nulidade, tempo e dependências de cobertura versionados nas onze métricas. |
| Robustez 2 — relacionamentos e cardinalidade | Comprovado | Uma fonte por consulta, chave primária conferida, sem relacionamentos ou conversões autorizados; fórmulas do dicionário preservadas sem consolidar DEC/FEC. A revisão de definições permanece explicitamente no item 1. |
| Robustez 3 — metadados até evidência/portal | Parcial | Contrato entre núcleo e Backend testado; consistência na evidência e na interface ainda requer os consumidores de GENAI-07/11/12. |
| Robustez 4 — núcleo composto e contrato de schema | Comprovado | `core.question.plan`, `validate_mapping`, `select_source` e carregador Backend exercitados; descoberta de coluna não libera capacidade. |

A correção da seleção direta recusa IDs ausentes da definição versionada antes de
considerar fontes existentes. Uma cópia de receita com ID novo reproduzia aceitação
indevida; o teste público passa após a correção. Essa proteção não substitui a
revalidação de identidade, plano, publicação e cobertura no futuro executor.

Próximo passo: conferir as definições atuais com Dados no PR #73 e consumir estes
metadados ao integrar o fluxo existente. O cartão continua aberto; execução SQL e
reconciliação de dados são entregas GENAI-06/07/10, sem criar um segundo núcleo.
