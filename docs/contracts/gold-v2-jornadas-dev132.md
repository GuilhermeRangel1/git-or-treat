# DEV-13.2 — Mapeamento e proveniência do lote local v2

Conferência em 29/10/2026, limitada a Receita, UC 360 e Inspeções. Requisitos WEB-02/03/04/07; dependências DE-06/DE-08. Referência semântica: [dicionário Gold](../dicionario_gold.md). Esta conferência valida o lote recebido contra o contrato físico e o consumo da aplicação; não substitui a reconciliação do Delta na origem nem conclui esses requisitos.

## Pastas e identidade

Manter `backend/data/gold/v1/` e `backend/data/gold/v2/` separados. Cada diretório contém as sete pastas de tabelas e o manifesto do respectivo lote; na v2 recebida, ele fica em `manifesto/manifest.json`. Não copiar o manifesto de outro lote nem misturar partes de exportações. Ambos permanecem ignorados pelo Git.

`v2` é o nome local da segunda entrega. Seus sete cabeçalhos continuam compatíveis com o esquema físico **`gold-csv-v1`**; a pasta não define a versão do esquema nem a identidade do lote. O lote é derivado do `run_id` validado do manifesto. Como esta exportação não declara `schema_version`, a opção explícita abaixo fornece a versão suportada, conforme a compatibilidade já documentada pelo carregador.

Em `backend/`, com `DATABASE_URL` apontando para o banco de destino escolhido:

```powershell
venv/Scripts/python.exe -m alembic upgrade head
venv/Scripts/python.exe scripts/load_gold.py --directory data/gold/v2 --schema-version gold-csv-v1
```

A API consulta o banco, sem receber caminhos de CSV do frontend. Portanto, não é necessário apagar a v1 ou manter o mesmo caminho para trocar a exportação importada. A publicação continua atômica e preserva operações conforme [DEV-12](gold-load-dev12.md). Nesta conferência foi usado um banco isolado `gold_v2_mapping_test`, sem substituir o banco anterior, sem alterar `.env` e sem enviar CSVs ao Git.

## Receita — tabelas, grão e campos

- `gold.gold_consumo_receita_bairro`: uma linha por (`competencia`, `municipio`, `bairro`, `classe_consumo`). Esses quatro campos compõem a chave. A API projeta `receita_total_reais` → `billed_amount`/totais em R$; `consumo_total_kwh` → `measured_energy_kwh`/totais em kWh; contagem de UCs do grupo → `billed_uc_count` nos snapshots mensais. Município/bairro/classe formam os recortes; competência delimita a série e os extremos comparados.
- Com filtro por alimentador, a consulta usa `gold.gold_consumo_mensal_uc`, chave (`id_uc`, `competencia`), com `receita_reais`/`consumo_kwh`; relaciona `id_uc` a `gold.gold_visao_360_uc`, cuja chave é `id_uc`. O cadastro fornece município, bairro, classe e alimentador **atuais**, não suas vigências históricas.
- `gold.gold_diagnostico_receita` é carregada e participa dos controles financeiros, mas não alimenta diretamente esta projeção da tela. `tarifa_media_efetiva` existe na exportação; não é tarifa homologada nem está exposta automaticamente como preço no contrato atual. Implementar outra interpretação exige revisar o contrato da métrica.
- Receita paga, energia faturada separada e faturas individuais não constam dos CSVs. A API mantém as medidas ausentes nulas e a decomposição preço-volume indisponível; não preenche com fixtures ou zero.

## UC 360 — tabelas, grão e campos

- Busca/perfil: `gold.gold_visao_360_uc`, uma linha por `id_uc`; mapeia `id_uc` → `uc_id`, além de município, bairro, classe, alimentador e status do cadastro atual. Nome/referência do cliente permanecem nulos, pois esses identificadores pessoais não são exportados.
- Comparação e histórico: `gold.gold_consumo_mensal_uc`, uma linha por (`id_uc`, `competencia`); `consumo_kwh` → `measured_energy_kwh` e `receita_reais` → `billed_amount`. O histórico é mensal agregado, não uma lista de faturas. A seleção de período vale para esse histórico/comparação.
- `possui_gd` informa presença cadastral de GD; não fornece potência, geração ou compensação mensal. Não equivale a um histórico de instalações.
- Totais de chamados/interrupções, duração em horas, satisfação e média histórica existem na visão consolidada, mas não viram eventos mensais individuais nem são todos expostos como indicadores nesta tela. Sua janela histórica não está declarada na tabela. Exibi-los como novos resumos continua sendo trabalho próprio, com escopo temporal explícito.
- Faturas detalhadas, pagamentos, medidores e registros individuais de chamados/interrupções permanecem indisponíveis. A busca agora preserva os metadados recebidos da API, que antes eram reduzidos ao estado da consulta no decoder do frontend.

## Inspeções — tabelas, grão e campos

- `gold.gold_fila_inspecao`: uma linha por `id_uc`; projeções de município/bairro/classe/alimentador, `prioridade_inspecao` → `priority_label`, contagens de inspeções realizadas/irregulares e indicador cadastral de GD. O detalhe confere a existência da UC no cadastro e na fila pela chave `id_uc`.
- Prioridade é uma categoria textual descrita no dicionário; `priority` numérico, pesos/sinais calculados e energia recuperável não são fornecidos por esta projeção. Permanecem ausentes, sem transformar histórico em confirmação de nova irregularidade.
- A fila não tem `competencia` nem janela dos históricos acumulados. O período do envelope corresponde à cobertura do consumo mensal no lote. Tela, detalhe e fundamentos agora usam esse rótulo e explicam que ele **não é a janela da suspeita**. Não se deduz essa janela da data de ligação, do instante de importação ou da cobertura mensal de outra tabela.
- A unidade da listagem é UC; contagens históricas são inspeções. kWh aparece com estimativa de recuperação explicitamente indisponível. A criação de ordens a partir da fila Gold continua condicionada à regra/autorização previstas no escopo próprio.

## Colunas ausentes versus valores nulos

Os sete CSVs v2 possuem todos os cabeçalhos do contrato físico atual, sem colunas extras. Na leitura integral local:

- Mensal: 1.928.920 linhas; territorial: 51.862; diagnóstico: 4.694; continuidade: 5.856; fila/variação/visão UC: 45.000 em cada tabela.
- As tabelas mensais cobrem 48 competências, de julho/2022 a junho/2026. Isso não atribui período às três tabelas cadastrais/por UC sem competência.
- `media_consumo_historico` está nula em 1.046 linhas da fila e da visão UC; `media_satisfacao_atendimento`, em 66 linhas da visão UC.
- Na variação por UC, `consumo_medio_inicial`, `variacao_kwh` e `variacao_pct` estão nulos em 1.461 linhas; `consumo_medio_final`, em 1.046. Essa tabela não é a fonte da comparação atual das três telas; suas janelas fixas não são intercambiáveis com o período selecionado na UI.
- Nenhum vazio foi observado nas outras colunas durante esta leitura CSV. Valores nulos dos agregados e detalhes não exportados são situações diferentes; ambos preservam indisponibilidade, sem completar números por hipótese.

## Evidência e metadados na interface

O carregador real validou tipos, chaves obrigatórias/únicas, inventário, contagens e controles financeiros das sete tabelas, publicando o lote no PostgreSQL 18.4 isolado. A relação mensal → cadastro preservou exatamente 1.928.920 linhas, com zero órfãos; fila → cadastro também sem órfãos. Isso comprova a cardinalidade do lote local, não a formação dos fatos na Silver/Delta.

Conferência local `work/verify_gold_v2_mapping.py` (ignorada): seis rotas reais de Receita, busca/overview/histórico UC e fila/detalhe retornaram período, lote/hash e limitações consistentes. Totais de Receita dos últimos 12 meses conferiram com o agregado no banco; pagamentos, energia faturada separada, cliente, medidor e estimativa ausentes permaneceram nulos. Perfil agregado dos arquivos e resultados ficam em `work/gold-v2-profile.json` e `work/gold-v2-mapping-result.json`, sem registros individuais na saída.

O componente compartilhado `DataProvenance` é usado somente nestas jornadas. Mostra período com seu significado, unidades, identidade completa do lote/versão, importação local UTC e limitações. Identidades e textos longos quebram linha. Não apresenta importação como data de processamento da origem.

Verificações: 551 testes backend aprovados, 63 ignorados (PostgreSQL de testes não configurado/limite de precisão SQLite); 292 testes frontend aprovados; build, lint, formatação e fronteiras passaram. A conferência real acima usou PostgreSQL 18.4 separadamente das suítes artificiais. Navegador local Vite → API → banco v2: painel visível em Receita, busca/detalhe UC e Inspeções; painel sem overflow próprio em 390 px, além da inspeção em 1440 px. Isso não constitui auditoria visual integral de gráficos, tabelas ou todos os estados das páginas.

Documentação React 19 sobre componentes/acessibilidade consultada via Context7 em 29/10/2026; mantidos os componentes e tokens existentes. Sem nova migração, fórmula de negócio ou exposição pública de dados. Pendências de desempenho, filtros completos, campos ainda não projetados e homologação permanecem no checklist DEV-13.2.
