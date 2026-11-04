# Contrato geográfico do Mapa da RMR

## Referência territorial

O universo do mapa é a Região Metropolitana do Recife definida por legislação estadual, não uma Região Geográfica Imediata do IBGE. A LC pernambucana nº 426, de 3 de abril de 2020, retirou Goiana; o IBGE publicou então a composição de 14 municípios. A página de composição territorial do IBGE foi atualizada em 29/07/2026, mas a planilha corrigida de 2025 não foi inspecionada nesta tarefa e não é usada para afirmar que não houve alteração posterior. A malha é publicada pelo serviço oficial de Malhas do IBGE v3, por município, em GeoJSON de qualidade mínima, período 2022. Nenhuma geometria de consumidor é usada.

O asset estático em `frontend/public/geography/rmr.geojson` contém uma feição por município, com `properties.code` (geocódigo IBGE como string) e `properties.name` (nome oficial do IBGE). As geometrias originais da API simplificada são preservadas sem simplificação adicional. `rmr-metadata.json` registra fonte, período, lista de códigos, atribuição e SHA-256 dos bytes GeoJSON. O navegador lê o arquivo local e não depende do serviço do IBGE na visita.

| Código IBGE | Município |
| --- | --- |
| 2600054 | Abreu e Lima |
| 2601052 | Araçoiaba |
| 2602902 | Cabo de Santo Agostinho |
| 2603454 | Camaragibe |
| 2606804 | Igarassu |
| 2607604 | Ilha de Itamaracá |
| 2607208 | Ipojuca |
| 2607752 | Itapissuma |
| 2607901 | Jaboatão dos Guararapes |
| 2609402 | Moreno |
| 2609600 | Olinda |
| 2610707 | Paulista |
| 2611606 | Recife |
| 2613701 | São Lourenço da Mata |

## Correspondência analítica

`municipalities.ts` mantém código, nome oficial e `goldNames`. A publicação Gold v2 local aprovada para esta validação foi conferida sem copiar seus dados brutos: os 14 municípios tiveram uma correspondência literal única e nenhum nome municipal ficou sem mapeamento. Grafias Gold distintas do nome oficial estão registradas como aliases literais, sem normalização em runtime. O relatório privado ignorado `work/mapa-rmr/gold-municipality-map.md` registra a conferência; nomes/linhas/valores Gold não são publicados neste contrato. Nomes oficiais continuam sendo aceitos por igualdade exata. Nenhum nome foi inferido por proximidade ou geografia.

Todos os 14 municípios permanecem na malha mesmo quando não há nome Gold conhecido ou observação na publicação. O consumidor marca a falta de correspondência/dado como indisponível; não remove o território e não converte ausência em zero. A malha não contém valores analíticos.

## Semântica da visão

- Faturamento é faturamento observado, não arrecadação nem valor recebido.
- Consumo é consumo medido, não energia faturada.
- As camadas absolutas usam a competência final. As camadas de variação usam apenas os dois meses extremos, de acordo com o contrato vigente de Receita.
- Valor zero observado, ausência de linha, cobertura insuficiente, falha de consulta e município sem mapeamento Gold são estados distintos.
- Município selecionado pela geometria é o mesmo código territorial usado pela lista. Consulta analítica sempre usa um nome Gold permitido validado pelo consumidor; não existe associação aproximada.
- Acesso ao conteúdo financeiro continua sob `revenue:read`; a disponibilização de geometria pública não amplia permissões.
- Percentual de faturamento permanece indisponível enquanto o contrato Gold v2 da Receita não o declarar elegível. A camada de variação é delta absoluto.

## Preparação e verificações

`node scripts/prepare-rmr-geography.mjs --download` baixa uma feição por código municipal no endpoint oficial e valida tipo, coordenadas, anéis fechados, ausência de duplicatas e cobertura integral antes de gravar os assets. Sem argumento, o mesmo script valida os arquivos existentes e seu checksum. A suíte determinística roda com `node --test scripts/prepare-rmr-geography.test.mjs` a partir de `frontend/`; seus testes usam geometrias artificiais pequenas e não alegam validar os dados analíticos.

## Fontes oficiais

- IBGE, [Composição das Regiões Metropolitanas, RIDEs e Aglomerações Urbanas](https://www.ibge.gov.br/geociencias/organizacao-do-territorio/analises-do-territorio/18354-regioes-metropolitanas-aglomeracoes-urbanas-e-regioes-integradas-de-desenvolvimento.html), página de produto atualizada em 29/07/2026; a planilha 2025 não foi inspecionada nesta fatia.
- IBGE, [notícia sobre a atualização da composição em 2020](https://agenciadenoticias.ibge.gov.br/agencia-sala-de-imprensa/2013-agencia-de-noticias/releases/29465-ibge-atualiza-a-lista-dos-municipios-que-integram-os-recortes-territoriais-brasileiros2), incluindo a saída de Goiana e a lista de 14 municípios.
- IBGE, [API de malhas geográficas v3.0.0](https://servicodados.ibge.gov.br/api/docs/malhas?versao=3), que documenta malhas municipais simplificadas e formato GeoJSON.
- IBGE, [API de localidades](https://servicodados.ibge.gov.br/api/v1/localidades/estados/26/municipios), usada para conferir os geocódigos e nomes oficiais.
