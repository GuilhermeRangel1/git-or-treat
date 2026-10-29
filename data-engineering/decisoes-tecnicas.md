# Decisões técnicas do pipeline V-Energy Grid 360

Este documento **centraliza as decisões técnicas** das camadas de engenharia de dados (Bronze, perfilamento,
Silver e Gold), explica **de onde vem cada número** e diz **o que ainda é pendência**. Ele existe para facilitar a
correção: em vez de garimpar decisão espalhada por notebook, PRD e ADR, o leitor acha aqui o "porquê" de cada
escolha e um registro de decisões com evidência.

Regras deste documento:

- **Fonte de requisitos:** o [PRD](../docs/PRD.md) (IDs, estados e critérios). Este arquivo é o registro
  consolidado das decisões técnicas de Engenharia de Dados, incluindo o contexto e as alternativas da Bronze.
  Decisões de outros módulos continuam registradas em [`docs/decisions/`](../docs/decisions/README.md).
- **Só entra afirmação com número ou prova.** Todo número citado vem do perfil da Bronze
  (`quality.perfil_bronze`, execução de 17/10/2026, 113 linhas), da reconciliação da ingestão
  (`bronze.reconciliacao`), da execução do Workflow, ou de verificação local reprodutível — e a origem está dita.
- **Sem prova, é pendência declarada**, não afirmação. O que só se prova no Databricks está marcado como
  "só no runtime".
- **Camada Gold ainda não existe.** A seção da Gold é **proposta de modelagem** (decisão a tomar), não código.

Nomes de arquivo: `Landing_to_Bronze.ipynb` e `Bronze_perfilamento.ipynb` em `data-engineering/notebook/`;
`v-energy-grid-360.yaml` em `data-engineering/configuracao/databricks/`. O contêiner é `workspace`; as tabelas são
`workspace.bronze.*`, `workspace.quality.perfil_bronze` e `workspace.silver.*`.

---

## 0. Como as camadas se encaixam

```text
8 fontes brutas (Volume)
      │  Landing_to_Bronze.ipynb      → schema de preparo por execução → bronze_hist.*
      │                                 → vistas workspace.bronze.* selecionadas por controle_publicacao
      │                                 + bronze.arquivos_lote e bronze.controle_lote
      ▼
   Bronze (Delta, conteúdo original preservado)
      │  Bronze_perfilamento.ipynb    → workspace.quality.perfil_bronze   (mede, não altera)
      ▼
   Plano de limpeza (números por problema)
      │  Bronze_to_Silver.ipynb       → workspace.silver.* + silver.quarentena
      ▼
   Silver (limpa, tipada, relacionada)
      │  (a construir)                → Gold
      ▼
   Gold (métricas de negócio)  →  CSV  →  banco local  →  API / portal / IA
```

Cada seta só existe se a anterior fechou a conta. As duas contas que governam o pipeline:

- **Ingestão:** `registros lógicos de origem = gravadas + rejeitadas` (com `delta = 0`), **por origem** (arquivo e aba);
  a posição em linhas físicas é registrada separadamente; o total da tabela é a soma das origens (D39).
- **Silver:** `bronze = aceitos + quarentenados` (com `delta = 0`), por tabela, no grão certo.

---

## 1. Registro de decisões (resumo)

| # | Camada | Decisão | Por quê (motivo) | Evidência / número | Estado |
|---|---|---|---|---|---|
| D1 | Bronze | Campos CSV/XLSX em texto; JSON aninhado preserva a estrutura e guarda o bruto | evitar inferência em campos tabulares sem achatar a estrutura original do JSON | `Landing_to_Bronze.ipynb` §§2–6; `_registro_bruto` | implementação local; falta validar no Databricks |
| D2 | Bronze | Scanner CSV/JSON antes do Spark; rejeições preservam bruto, motivo e posição | `PERMISSIVE` pode completar campos ausentes e descartar excedentes sem marcá-los | §2.11; autoteste sintético: CSV 2 larguras inválidas e JSON 1 objeto inválido | implementação local 20/10; falta executar no Databricks |
| D3 | Bronze | Auditoria inclui origem, ordinal, linhas físicas, registro bruto e metadados do lote | rastrear o conteúdo aceito/rejeitado até o arquivo ou aba | `_id_registro` identifica a linha na Bronze; arquivo + ordinal + intervalo físico identificam a origem (D40) | implementação local; falta validar no Databricks |
| D4 | Bronze | `unionByName(..., allowMissingColumns=True)` nos 5 arquivos de leitura | coluna ausente num ano vira `null` em vez de derrubar a leitura | 5 arquivos 2022–2026 | implementado |
| D5 | Bronze | Carga por **`overwrite`** no schema de preparo da execução (não `append` na tabela publicada) | a extração vem completa; sem isso, rodar 2× dobraria a base; preparo separado protege o lote ativo durante a ingestão | 2.184.623 faturas virariam 4.369.246 | implementado, **revisado (D42)** |
| D6 | Bronze | Reconciliação **por origem** (arquivo e aba) + `bronze.rejeitados` | "diferenças de parse e rejeições contadas e explicadas" (DE-01), **para cada fonte e lote** (§4.3) | 5 linhas em `leituras` + 3 em `inspecoes`; `delta = 0` nas origens | implementado, **revisado (D39)** |
| D7 | Perfil | Notebook **separado** da ingestão | medir ≠ alterar; o perfil só investiga e grava o plano de limpeza | `quality.perfil_bronze`, 113 linhas | implementado |
| D8 | Perfil | Deduplicação e nulos contados **só nas colunas de negócio** | `_id_registro` é único por linha e daria 0 duplicatas sempre (falso negativo) | `Bronze_perfilamento.ipynb` §2 | implementado |
| D9 | Perfil | Normalizar **moeda/vírgula** antes de chamar valor de "não numérico" | senão formato vira "podridão" | `valor_total` não numérico: 196.624 → 2 | implementado |
| D10 | Perfil | Data fora do ISO conta como **ambígua**, não inválida | ordem dia/mês é decisão de negócio, não defeito do dado | 102.878 (leituras) + 61.226 (faturas) | implementado |
| D11 | Silver | **Rastreio na Silver:** `_arquivo_origem`, `_ordem_na_origem`, `_lote_id`, `_id_registro` (+`_aba_origem` em `inspecoes`) entram como metadados técnicos | localizam o registro aceito na Bronze sem serem atributo de negócio; o rastro inteiro segue no `_registro` da quarentena | comportamento implementado no notebook; a issue #18 registra posições diferentes sobre a linhagem | implementado na branch; sem alegar consenso da discussão |
| D12 | Silver | Fim da **releitura** de tabela depois de `saveAsTable` | evitar custo e ponto de inconsistência; usa o DataFrame em memória | seção 5.1 | implementado |
| D13 | Silver | Data ambígua de dia/mês → **quarentena** | a Silver não chuta ordem dia/mês | seção 5.3 / 8 | implementado, mas **regra pendente** |
| D14 | Silver | Deduplicação por **chave de negócio**, mantendo o registro mais completo | uma verdade por registro; empate por `_data_carga` | duplicata exata 21.523/900/513/1 | implementado |
| D15 | Silver | **Sentinela `9999-12-31` preservada (revisado):** o valor **fica** na coluna tipada e é marcado com `_*_sentinela`; `_tem_pagamento` a exclui | decisão do time: só virar nulo depois que a origem confirmar o significado; até lá não é lida como data real | faturas.data_pagamento 61.333 de 61.335 | implementado, **confirmar com a origem** |
| D16 | Silver | Conversões **à prova de ANSI** (`try_to_*`, `try_cast`) | valor ruim vira nulo em vez de estourar a execução | seção 5.3 | implementado |
| D17 | Silver | Contrato de tipos conferido **antes** de transformar | não gravar tabela errada em silêncio | `historico: array<struct>`, `nota_satisfacao: double` | implementado, só no runtime |
| D18 | Silver | Reconciliação Bronze→Silver com `delta` por tabela | invariante da camada | seção 7 | implementado, só no runtime |
| D21 | Silver | Data no futuro → **flag**, não quarentena | perfil §6: futuro é "investigar", não defeito (competência corrente pode cair à frente) | flags `_*_futura` | revisão 18/10 |
| D22 | Silver | A verificação final **lê** `quality.perfil_bronze`, `bronze.reconciliacao`, `bronze.arquivos_lote` e `bronze.controle_lote` | antes os números eram digitados e `PERFIL`/`RECON` eram código morto | seção 13 do notebook | revisão 18/10, ampliada |
| D23 | Silver | Negativos impossíveis de GD/inspeções → quarentena; fatura/nota → flag | perfil §7 classifica negativo por coluna | `gd_negativo`, `kwh_recuperado_negativo`; `_valor_negativo`, `_nota_negativa` | revisão 18/10 |
| D24 | Silver | `atendimentos_historico` com `explode` (não `explode_outer`) | grão de saída = `sum(size(historico))` da entrada | reconciliação de grão fecha | revisão 18/10 |
| D25 | Silver | Desempate de dedup por `_id_registro` (terceiro critério) | `_data_carga` é constante por lote; sem isso o empate é arbitrário entre execuções | janela determinística | revisão 2, 18/10 |
| D26 | Silver | Flag `_*_futura` em **toda** tabela com data | o sinal de "futuro" não pode ser calculado e descartado | contrato de saída confere as flags | revisão 2, 18/10 |
| D27 | Silver | `vazio`/`texto` colapsam espaço antes do placeholder | `SEM  INFORMACAO` (espaço duplo) passava como valor | `numero`/`data` provados iguais ao perfil (14.5) | revisão 2, 18/10 |
| D28 | Silver | `DROP TABLE IF EXISTS quarentena` quando não há rejeição | não herdar a quarentena de execução anterior | idempotência | revisão 2, 18/10 |
| D29 | Silver | Seção 13 mede data inválida, chave duplicada (GD/inspeções/ocorrências/atendimentos) e cascata de órfão | tornar visível o que antes só existia no perfil | verificação final | revisão 2, 18/10 |
| D30 | Silver | Órfão de UC também em `medidores` e `geracao_distribuida` (quarentena `uc_inexistente`) | o perfil mede órfão nas cinco fontes com `id_uc` | invariante de órfãos nas seis tabelas | revisão 3, 18/10 |
| D31 | Silver | Deduplica `ocorrencias_rede` (`id_ocorrencia`) e `atendimentos` (`protocolo`) | o `CHAVES` do perfil mede `chave duplicada` das duas; a saída tinha chave repetida | chaves únicas de fato nas 8 tabelas | revisão 3, 18/10 |
| D32 | Silver | Bloco de cobertura na seção 13 (lê o perfil e lista achados com ocorrências > 0) | garantir que nenhum achado fique sem tratamento/justificativa | cobertura do plano de limpeza | revisão 3, 18/10 |
| D33 | Silver | `mes_referencia_invalido` também em `leituras` | o perfil checa o formato nas duas fontes; antes só `faturas` | quarentena no grão certo | revisão 3, 18/10 |
| D34 | Silver | Flag `_pagamento_antes_emissao` em `faturas` | regra ALTA do perfil sem tratamento | flag na saída | revisão 3, 18/10 |
| D35 | Silver | Seções `14.5 Divergências` / `14.6 Próximos passos` reordenadas | eu havia inserido a 14.6 antes da 14.5 | numeração corrente | revisão 3, 18/10 |
| D36 | Silver | Data ambígua de dia/mês: **manter quarentena (opção B)** e rodar a evidência por arquivo (opção C) | decisão do time: não chutar a ordem dia/mês; recuperar só com prova | 102.878 leituras / 61.226 faturas | **decidido** 18/10 |
| D37 | Silver | Achados que não rejeitam + `inspetor`: **manter as regras atuais**, quantificar no próximo perfil e **confirmar se `inspetor` é exibido ao usuário** antes de padronizar | decisão do time: não criar regra sem justificativa; padronizar nome de pessoa pode afetar a exibição | §14.4 do notebook | **decidido** 18/10 |
| D38 | Silver | **Cascata de órfão — decidido:** validar a FK contra a **Silver** (A) e dar **motivo próprio** ao bloqueio (`uc_em_quarentena`/`medidor_em_quarentena`) quando a chave existe na Bronze e o cadastro pai caiu na quarentena | decisão do time: a linha bloqueada não é registro malformado; mantê-la na Bronze e no `_registro` permite reprocessar depois de 14.1 | `medidor_inexistente` volta a 8.609 e as 58.214 leituras ficam identificadas | **decidido** 19/10 (R41) |
| D39 | Bronze | Reconciliação **por origem** (uma linha por arquivo e por aba), com `_aba_origem` | o §4.3 pede a conta "para cada fonte e lote"; por tabela, um ano das leituras ou uma aba do Excel que encolhesse ficava invisível | `leituras` 5 linhas, `inspecoes` 3; a Silver soma por `_tabela` (§13.1b) | **implementado** 19/10 (revê D6) |
| D40 | Bronze | `_ordem_na_origem` e intervalo de linhas físicas por arquivo/aba | `_id_registro` localiza na tabela; o scanner localiza o registro lógico no arquivo sem depender do particionamento do Spark | CSV/JSON: ordinal e linhas inicial/final do scanner; Excel: linha da planilha | implementação local 20/10; falta conferir no Databricks |
| D41 | Bronze | `bronze.arquivos_lote`: nome, caminho, tamanho, modificação e **SHA-256** por lote | provar **qual versão** do arquivo entrou e comparar reexecuções; fecha a pendência de hash do §4.3 / DE-01 | arquivos publicados com `status_hash = OK`; hash indisponível bloqueia a carga | implementação local; validar o acesso aos arquivos no Databricks |
| D42 | Bronze | **Publicação por lote:** ingestão grava em schema de preparo e `bronze_hist`; vistas `bronze.*` filtram o lote de `bronze.controle_publicacao` | uma falha antes da troca do ponteiro deve manter o conjunto anterior visível | a troca do ponteiro é uma operação Delta; migração inicial de tabelas legadas exige janela controlada | implementação local 20/10; falta validar falhas, reexecução e migração no Databricks |
| D43 | Silver | `_ordem_na_origem` entra no rastreio publicado, no contrato de tipos e nas `AUDITORIA` do perfilador e da Silver | preserva a ordem auxiliar até a Silver; no perfilador, incluí-la como dado zeraria a duplicata exata | §13 compara as 4 colunas e confere `bigint`; o intervalo físico fica registrado na Bronze conforme D40 | **implementado** 19/10 (revê D11) |
| D44 | Silver | **UF/CEP/endereço:** `uf` publicada no **código de 2 letras** (mapa das 27 UFs); `cep` só com **8 dígitos**; `logradouro`/`numero` aparados; `nome_titular` preserva a caixa | a seção 5.2 já dizia "UF padronizada", mas a carga só fazia maiúscula — o arquivo tem **5 grafias** cruas para PE (`PE` 39.470, `pe` 1.826, `pernambuco` 1.729, `P.E.` 1.726, `Pernambuco` 1.709); `cep = "-1"` (162 linhas) virava `"1"`; 2.797 logradouros tinham espaço nas pontas e 1.551, espaço duplo | 45.200 UCs, todas `PE`; CEP nulo onde não há 8 dígitos; 1.557 grafias de logradouro → 217 | **implementado** 19/10 (R42–R44) |
| D45 | Silver | **Tipo de medidor:** mapa canônico `ELETRO-MECANICO` → `ELETROMECANICO` e `SMART METER` → `SMART` | o arquivo tem **5 valores (10 grafias cruas) para 3 tipos**; o perfil mediu 3 grupos cosméticos, mas o hífen e o nome em inglês ficavam fora do colapso — o mesmo tipo apareceria duas vezes na saída e a Gold agruparia errado | 51.812 medidores, 3 tipos na saída (§13.6) | **implementado** 19/10 (R48) |
| D46 | Silver | **Lote fixado:** a Silver lê `bronze_hist.<tabela>` filtrada por `_lote_id`, com o lote lido de `bronze.controle_publicacao` no início e exigido `PUBLICADO` em `bronze.controle_lote`; não lê as vistas `bronze.*` | o ponteiro da Bronze pode mudar no meio da execução; a vista misturaria lotes entre tabelas. É o mesmo padrão do `Bronze_perfilamento` | execução local: ponteiro verificado no início e no fim; aviso se andar | implementado; executado no Databricks em 21/10 (§11.3) |
| D47 | Silver | **Portão de qualidade e controle de execução:** `silver.controle_silver` (`EM_ANDAMENTO` → `CONCLUIDO`/`FALHOU`) e `FALHAS`: qualquer invariante violado (reconciliação, chave, órfão, negativo, tipo, rastreio, lote) falha a tarefa | a seção 13 precisa impedir a publicação de dados reprovados; a Gold só consome execução `CONCLUIDO` do lote desejado | controle de estado e invariantes descritos na seção 13 do notebook | implementado no notebook; a execução registrada em 21/10 antecede a revisão atual |
| D48 | Silver | **Auditoria da Bronze:** `_linha_fisica_inicial/_final`, `_registro_bruto`, `_lote_origem`, `_versao_origem` entram em `AUDITORIA` (fora da completude e duplicata exata); `_registro_bruto` também integra o JSON completo da quarentena; os localizadores ficam como colunas consultáveis | registros rejeitados precisam ser autocontidos e reprocessáveis; localizadores consultáveis evitam parsear o JSON para achar a origem | `_arquivo_origem`, `_ordem_na_origem`, `_lote_id`, `_id_registro`, `_valor_controle` e payload íntegro | implementado no notebook; conferir no lote autorizado |
| D49 | Silver | **Conta em valor e detecção de multiplicação:** soma de `faturas.valor_total` (R$) e `leituras.consumo_kwh` (kWh) na entrada = aceitos + quarentena; a entrada medida depois dos joins deve igualar a contagem independente da Bronze | PRD §4.3 pede reconciliar somas; DE-03 pede detectar multiplicação de fatos | reconciliação em R$/kWh e contagem independente após joins, seção 13 | implementado no notebook; conferir no lote autorizado |
| D50 | Silver | **`try_element_at` para `primeira_acao`/`ultima_acao`** (em vez de `historico[0]` e `historico[size-1]`) | com ANSI ligado, índice fora do limite **estoura** (`INVALID_ARRAY_INDEX`); histórico vazio não deve interromper a execução | `try_element_at` aplicado às posições inicial e final | implementado no notebook; a execução registrada em 21/10 antecede a revisão atual |
| D51 | Silver | **Conta ponta a ponta inclui `bronze_hist.rejeitados`:** origem lógica = rejeitados no parse + aceitos na Bronze; aceitos na Bronze = quarentena + Silver. Rejeitados do parse **não** entram na quarentena da Silver | a quarentena mede a Silver; misturar os dois quebraria o invariante D18 | §13.2 imprime a conta por origem e por tabela | implementado; executado no Databricks em 21/10 (§11.3) |
| D52 | Silver | **Diagnóstico de competência, não decisão de formato:** o run anterior encontrou uma interpretação compatível com a competência em todas as datas ambíguas medidas; os arquivos misturam dia/mês e mês/dia | compatibilidade com competência é evidência, mas não prova que todas as datas de um mesmo arquivo seguem a mesma ordem; D36 mantém B + C | consultas do run `20261021T101818Z_223235ca`; novo perfil por arquivo mede evidências direcionais, mistura e consistência | dado exploratório; não autoriza inferência nem altera a quarentena |
| D53 | Silver | **Opção B + diagnóstico C (mantém D36):** datas ambíguas de leitura e emissão permanecem em quarentena. O diagnóstico mede por arquivo ordem evidente, compatibilidade das datas inequívocas com a competência, competência ausente/inválida e impacto por competência/classe; não publica uma interpretação | componente acima de 12 e consistência com competência ajudam a avaliar o arquivo, mas não provam que ele todo use a mesma ordem; revisar o contexto antes de qualquer regra | seções 13.6 e 14.1 | implementado no notebook; analisar os resultados do próximo perfil/lote antes de reavaliar |
| D54 | Silver | **Instalação ambígua e cascata:** mantém a opção A de D38. Medidor com `data_instalacao` ambígua fica em quarentena; leitura que referencia esse medidor recebe `medidor_em_quarentena`. Só reavaliar identidade com data pendente se o negócio confirmar que ela é válida sem a data | não inventar vigência nem publicar FK cujo pai não entrou na Silver; cascata é bloqueio, não defeito individual | 1.369 medidores e 58.214 leituras na execução anterior; reprocessáveis pela origem e payload completos | **implementado localmente; não recupera medidor/leitura por padrão** |
| D55 | Silver | **Data registrada não equivale a quitação:** preservar `9999-12-31` e datas futuras, manter status e flags de sentinela/futuro; `_data_pagamento_inconclusiva` e `_paga_sem_data_valida` impedem que data isolada prove pagamento | a pessoa usuária não conhece o significado na origem; 61.335 faturas `EM ABERTO` têm data registrada no perfil anterior | política conservadora: `EM ABERTO` não é pago, `PAGA` sem data válida não é pagamento comprovado; Gold deve distinguir status de comprovação | **política Silver implementada; sem atribuir significado à data futura** |
| D56 | Silver | **Titular conflitante não é resolvido por completude:** em duplicatas da mesma UC, publicar `cpf_cnpj`/`nome_titular` como nulo quando houver mais de um valor normalizado; flags sinalizam conflito e candidatos ficam na Bronze/quarentena | 360 grupos com cópias não exatas; linha mais preenchida não prova titularidade nem vigência | a UC segue vinculável por `id_uc` sem publicar titular concorrente como verdade | **política Silver implementada; origem pode corrigir identidade depois** |
| D57 | Silver | **Publicação isolada por execução:** preparar as tabelas em schema próprio, reconciliar cada fonte, copiar o run para `silver_hist` e só então trocar `silver.controle_publicacao`; a Gold lê `silver_publicada.*` | sobrescrever `silver.*` durante a execução poderia expor tabelas de versões diferentes | notebook Silver, seção 15; o ponteiro só avança após preparar e reconciliar a execução | implementação no notebook; a transação Delta ainda requer validação no Databricks |
| D58 | Silver | **Qualidade por achado e recorte:** todo achado relevante do perfil recebe destino explícito; aceitos, quarentena e rejeitados de parse são confrontados por origem, e os fatos de R$/kWh também por competência e classe | uma listagem de achados ou o fechamento agregado por tabela não revelam lacunas em arquivos ou segmentos | notebook Silver, seções 13.2 e 13.7; DE-02/DE-03 permanecem em validação até o lote autorizado | implementado no notebook; validar no lote autorizado |
| D59 | Silver | **Nulo tipado exige destino explícito:** timestamp inválido de ocorrência/atendimento vai à quarentena; nota de satisfação inválida fica nula com `_nota_invalida`; coordenadas inválidas ficam nulas com `_geo_invalida`. Medidas necessárias malformadas vão à quarentena | conversão silenciosa para nulo esconderia perda de significado; o histórico de R24/R25 descreve versões anteriores, não a regra atual | notebook Silver, transformações e relatório por arquivo/aba na seção 13 | **implementado localmente; conferir volumes no lote autorizado** |
| D60 | Silver | **Tratativa localizável:** `atendimentos_historico` usa `(protocolo, posicao_historico)` como chave, com posição de 1 em diante no array original | `sequencia` vem do JSON e pode ser ausente, inválida ou repetida; sem ordinal não é possível localizar uma tratativa específica na Bronze | `posexplode` e verificação de unicidade no notebook; amostra de linhagem sem exposição de identificadores | **implementado localmente; validar no lote autorizado** |
| D19 | Gold | Modelo de métricas (receita, DEC/FEC, GD, UC 360) | responder às perguntas do portal/IA | PRD §5, dicionário | **proposta** |
| D20 | Gold | **Mascaramento/hash** de dado pessoal | LGPD: não expor CPF/nome a portal, IA e CSV local | seção 9 | **pendente** |
| D61 | Silver | **Reparo de encoding em `bairro`:** a Silver repara texto em UTF-8 lido como Latin-1 antes da padronização (função `reparar_encoding`). A Bronze guarda o texto cru de propósito. Nenhum mapeamento de grafias é aplicado, porque não há fonte de referência | sem o reparo, o mesmo bairro aparece com grafias diferentes e duplica linhas em `consumo_receita_bairro` | mesma entrada Bronze (`f875fb45`): Silver `b8bccba8`, sem reparo, 331 bairros distintos e 338 linhas com texto quebrado (padrão de busca desta conferência); Silver `c5ba30e0`, com reparo, 272 e 0 suspeitos; mantido na `c738405b`. A contagem de linhas reparadas na Bronze está no PRD (entrada de 24/10). O commit `5679271` (24/10, 01:58, Recife) é posterior à execução `c5ba30e0` (24/10, 00:54): o reparo já estava no notebook do Workspace quando ela rodou. Varredura de todas as colunas de texto das 9 tabelas: 0 suspeitos | **implementado e verificado nas execuções `c5ba30e0` e `c738405b`** |
| D62 | Silver / Gold | **Data de ligação anterior a 1950:** a Silver preserva o valor; o tratamento fica na Gold (nulo, sem coluna nova, contrato `gold-csv-v1`), na próxima execução da Gold | as 90 UCs afetadas (de 45.000) têm todas data 01-01, entre 1900 e 1948, e nenhuma UC tem ligação entre 1949 e 1997; 89 têm série mensal normal: são UCs reais com data de cadastro inválida na origem. Alterar a Silver invalidaria a evidência e exigiria nova Silver e nova Gold | medido em 28/10 na Gold `81c5530b`; a Silver continua preservando o valor (`validacao_silver_v1`: 0 falhas) | **proposto por Dados; implementação na Gold pendente (Bia)** |

---

## 2. Camada Bronze

### 2.1 Papel

A Bronze é uma **cópia fiel da Landing**, sem tratar nada: limpar é trabalho da Silver. Isso é o que permite
reprocessar a partir do bruto a qualquer momento e comparar "o que veio" com "o que a Silver publicou".

### 2.2 Tipos armazenados por formato (D1)

Os campos CSV usam schema explícito string; as células do XLSX também são convertidas para texto. Isso evita que
códigos como CEP `"05001-000"` virem números ou percam zero à esquerda. O JSON de atendimentos permanece aninhado e
o Spark determina os tipos físicos de armazenamento a partir dos objetos; `_registro_bruto` guarda o texto exato de
cada objeto para preservar sua representação original. A Bronze não aplica tipagem semântica nem regras de negócio;
a interpretação dos valores continua sendo trabalho da Silver. As colunas de auditoria mantêm tipos próprios.

### 2.3 Captura de registro malformado (D2)

O contexto, as alternativas e a decisão estão consolidados na §2.11. Antes do Spark, o scanner percorre registros
lógicos com `csv.reader(strict=True)` ou separa objetos do array JSON. Campos CSV com largura
incorreta e objetos JSON inválidos ficam em `bronze.rejeitados`, com conteúdo bruto, motivo, ordinal e intervalo
físico. Erros estruturais sem ponto seguro de retomada interrompem o lote. O autoteste sintético roda em cada
execução: confere três registros CSV (um aceito e dois rejeitados por largura) e três objetos JSON (dois aceitos e
um rejeitado). Assim, `rejeitadas = 0` pode ser interpretado junto da prova de que os scanners continuam ativos.
O Spark recebe JSONL preparado para persistência; não é o modo permissivo do Spark que decide a largura CSV.

### 2.4 Colunas de auditoria (D3)

| Coluna | O que é | Por que existe |
|---|---|---|
| `_arquivo_origem` | arquivo/ano de onde a linha veio | localiza a origem (ex.: `leituras_2023.csv`) |
| `_aba_origem` | aba do Excel (só em inspeções: `ago-set`, `dez`, `out-nov`) | o Excel tem 3 abas com grãos possivelmente distintos |
| `_ordem_na_origem` | ordinal lógico no arquivo ou aba (1-based) | localiza o registro em conjunto com o arquivo; não substitui o intervalo físico |
| `_linha_fisica_inicial` / `_linha_fisica_final` | linhas que contêm o registro original em CSV/JSON/XLSX | aponta a posição física; em CSV/JSON multilinha, o registro pode cobrir mais de uma linha |
| `_lote_id` | identificador da execução de ingestão | série de volumes por lote; uma queda fica visível |
| `_id_registro` | id técnico **único dentro do lote** | chave técnica de linha; **não** é o número da linha física |
| `_data_carga` | carimbo da ingestão | ordena a deduplicação na Silver (qual cópia é a mais recente) |

Ponto sutil que já causou erro uma vez: `_id_registro` é único por linha, então **não pode** entrar na contagem de
duplicatas nem no grão de negócio (D8). Ele é chave técnica de lote, não atributo do dado. Pelo mesmo motivo,
`_ordem_na_origem` também está nas colunas de auditoria do perfilador (D43) — como ela é única por arquivo, deixá-la
fora faria a checagem de duplicata exata dar **0 sempre**.

Como ler o rastro (D40): `_ordem_na_origem` vem do scanner em CSV/JSON e da iteração da planilha em XLSX;
`_linha_fisica_inicial`/`_linha_fisica_final` preservam o intervalo físico antes do Spark. Para CSV e JSON, um
registro multilinha pode ocupar mais de uma linha; no XLSX, a linha original é armazenada diretamente. A conferência
no Databricks ainda precisa comprovar que o caminho no Volume e o leitor do runtime preservam esse contrato.

Na Silver, `_arquivo_origem`, `_ordem_na_origem`, `_lote_id` e `_id_registro` (e `_aba_origem` em inspeções) são
**publicados** como **metadados de rastreio** dos registros aceitos (D11 revisado 2, §5.4); `_data_carga` fica de fora.

### 2.5 Carga por `overwrite` (D5, revisado em D42)

A extração do case é completa, não incremental — não existe a chave de "só o que chegou de novo" que o `append`
exigiria. Sem `overwrite`, reexecutar dobraria a base **sem erro visível** (2.184.623 faturas → 4.369.246) e o
estrago só apareceria na Silver como número dobrado. O histórico de cargas não se perde: cada execução carimba
`_lote_id`, registra `lidas × rejeitadas × gravadas` em `bronze.reconciliacao` e atualiza `bronze.controle_lote`.
Se a Landing estiver incompleta mas ainda for um arquivo válido, a contagem pode fechar sobre a entrada incompleta;
a reconciliação não prova que o fornecedor entregou o conteúdo completo. A identidade/hash detecta alterações de
versão, mas a completude exige comparação com contagem ou manifesto externo autorizado.

O `overwrite` é usado somente no schema de preparo isolado da execução. A publicação acrescenta esse lote ao
histórico e atualiza a vista ativa por ponteiro (§2.9).

### 2.6 Reconciliação e rejeitados (D6, revisado em D39)

`bronze.reconciliacao` fecha, **por origem**, `registros lógicos de origem × gravadas × rejeitadas`, com
`delta = registros lógicos − gravadas − rejeitadas` que **precisa ser 0** (delta ≠ 0 é falha declarada, não ruído).
Para CSV/JSON, o scanner conta registros/objetos de forma independente do Spark e também registra linhas físicas;
para XLSX, `linhas_dados` é a contagem de linhas lidas por aba e `linhas_arquivo` fica nulo.
`bronze.rejeitados` guarda o bruto do que não parseou.

Cada linha da reconciliação é uma **origem**: um arquivo ou uma aba. As 5 leituras anuais, por exemplo, não entram
como uma linha só — cada ano tem a sua, com `_arquivo_origem = leituras/leituras_20XX.csv`; as inspeções entram em
3 linhas, uma por aba, com `_aba_origem` preenchido. O total da tabela é a **soma** das origens, e é assim que a
Silver compara (§13.1b): somar as origens sem somar a tabela daria `DIVERGE` em toda leitura. A motivação vem do §4.3 ("para cada fonte e lote"): com uma linha por tabela, um ano que encolhesse ou uma aba que
sumisse do Excel ficava invisível dentro do agregado.

O JSON `atendimentos` já não sai `SEM_BASE`: `objetos_interpretados` e `linhas_dados` vêm do scanner independente.
Em `inspecoes`, `linhas_arquivo = null` porque XLSX não tem contagem de linhas físicas comparável; `linhas_dados`
conta registros por aba. A linha `_autoteste_scanners` registra fixtures sintéticas e é excluída dos totais reais.
As contagens de 17/10 abaixo são evidência histórica da versão anterior, baseada em contagem física de `leituras`;
na versão atual, a unidade principal de reconciliação é o registro lógico, que continua fechando em aceitos + rejeitados.

**Lacuna do §4.3 fechada em D41:** a reconciliação guardava o **nome** do arquivo, mas não a **versão/hash** do
arquivo ingerido. Agora `bronze.arquivos_lote` traz o SHA-256 por lote (§2.9).

### 2.7 Encoding e separador (documentado, conferência manual)

| Arquivo | Formato | Encoding | Separador | Tratamento |
|---|---|---|---|---|
| `unidades_consumidoras.csv` | CSV | UTF-8 | `,` | leitura padrão |
| `medidores.csv` | CSV | UTF-8 | `,` | leitura padrão |
| `ocorrencias_rede.csv` | CSV | UTF-8 | `,` | leitura padrão |
| `geracao_distribuida.csv` | CSV | UTF-8 | `,` | leitura padrão |
| `faturas.csv` | CSV | UTF-8 | `;` | separador explícito |
| `leituras/leituras_2022..2026.csv` | CSV | UTF-8 | `,` | 5 arquivos unidos por `unionByName` |
| `atendimentos.json` | JSON array (`multiLine`) | UTF-8 | — | mantém **aninhado** |
| `inspecoes.xlsx` | XLSX (3 abas) | — | — | pandas + openpyxl |

A Bronze **não** detecta sozinha mudança de encoding/separador — por isso a tabela é documentada e a conferência é
manual (PRD §4.1).

### 2.8 Volumes da ingestão (execução de 17/10/2026)

`unidades_consumidoras` 46.461 · `medidores` 51.812 · `ocorrencias_rede` 180.000 · `geracao_distribuida` 3.510 ·
`faturas` 2.184.623 · `leituras` 2.182.468 · `atendimentos` 318.871 · `inspecoes` 1.389 (abas 511 + 383 + 495).
`delta = 0` em todas; `bronze.rejeitados` vazia.

### 2.9 Publicação por lote (D42)

O contexto, as alternativas e a decisão estão consolidados na §2.11. O problema tratado é a exposição de fontes de lotes diferentes durante a publicação. A versão atual grava em schema
de preparo e depois acrescenta cada fonte a `bronze_hist.*`, conferindo as contagens. As tabelas legadas são
migradas para o histórico na primeira execução, em janela controlada. As vistas `bronze.*` leem o mesmo
`lote_ativo` em `bronze.controle_publicacao`; após preparar as vistas, uma única atualização Delta do ponteiro
publica o lote inteiro:

| Etapa | O que acontece |
|---|---|
| 1 | cria/atualiza `bronze.controle_lote` com o novo lote em `EM_ANDAMENTO` |
| 2 | lê fontes, prepara tabelas e reconciliação no schema isolado da execução |
| 3 | valida scanners, quarentena, reconciliação e identidade/hash dos arquivos |
| 4 | copia legado, se necessário, e acrescenta as dez tabelas publicadas ao histórico Delta |
| 5 | cria/atualiza as vistas `bronze.*` para filtrar `bronze.controle_publicacao.lote_ativo` |
| 6 | marca o lote como `PUBLICADO` e atualiza o ponteiro numa operação Delta |

**Limites ainda abertos:** a migração inicial substitui tabelas legadas por vistas uma a uma, por isso exige janela
controlada e conferência antes de liberar leitores. Depois de as vistas estarem estabelecidas, falha antes da troca
do ponteiro conserva o lote anterior visível. A implementação, a recuperação após falha induzida e a reexecução ainda
precisam ser verificadas no Databricks; essa mudança local não comprova o comportamento do runtime.

Custo assumido: o lote é escrito **duas vezes** (preparo + histórico), e o histórico cresce a cada execução. Uma
falha antes da atualização do ponteiro preserva o lote anterior. Consumidores que executam várias consultas e
precisam da mesma versão devem capturar o `lote_ativo` no início e manter essa versão durante a análise.

### 2.10 Identidade do arquivo ingerido (D41)

`bronze.arquivos_lote` guarda uma linha por arquivo e lote: nome, caminho relativo, **tamanho em bytes**, data de
modificação e **SHA-256**. É o que permite provar *qual versão* do arquivo entrou e comparar duas execuções do mesmo
nome de arquivo (retificação na Landing). O hash é calculado no driver, por streaming em blocos de 1 MB, sem
carregar o arquivo inteiro na memória. Se o driver não conseguir ler o arquivo para calcular o hash, a carga é
bloqueada antes da publicação: um lote sem identidade comprovada não deve aparecer como válido. Nos lotes publicados,
`status_hash` deve ser `OK`. A tabela é `append` por lote, e reexecutar o mesmo `_lote_id` não duplica (o notebook
apaga as linhas do lote antes de gravar). A Silver mostra o lote no §13.1c (caminho, tamanho, 16 primeiros dígitos
do hash).

### 2.11 Registro consolidado da decisão técnica (DE-01)

- **Data:** 20/10/2026
- **Estado:** implementação local; validação no Databricks pendente
- **Requisito afetado:** DE-01

#### Contexto

O PRD pede preservação rastreável da origem e reconciliação de aceitos e rejeitados por arquivo ou aba. A leitura
permissiva de CSV pelo Spark pode preencher campos ausentes com `null` e descartar campos excedentes sem marcar o
registro como corrompido. A contagem do JSON feita pelo próprio parser também não confere, de forma independente,
quantos objetos havia na origem. Além disso, substituir tabelas publicadas uma a uma pode deixar fontes de execuções
diferentes visíveis se uma publicação falhar no meio.

#### Alternativas consideradas

1. **Ler diretamente CSV e JSON com o parser permissivo do Spark e substituir as tabelas publicadas.** É simples,
   mas não garante a detecção de toda divergência de largura CSV, deixa a contagem JSON dependente do mesmo parser e
   pode expor uma publicação parcial entre tabelas.
2. **Fazer todo o processamento em Python fora do Delta.** Permite controlar a leitura e as contagens, mas não
   cumpre o contrato de persistência da Bronze em tabelas Delta no Databricks.
3. **Usar transação multi-tabela do Databricks.** Pode agrupar a publicação, mas depende de recursos e versão do
   runtime cuja disponibilidade no ambiente do projeto não foi confirmada.
4. **Separar registros lógicos com scanner Python, persistir em Delta e publicar por um ponteiro único.** Escolhida:
   o scanner controla a contagem e a posição dos registros; as vistas expõem um lote selecionado por uma única
   atualização do controle de publicação.

#### Decisão

O `Landing_to_Bronze.ipynb` percorre CSV e arrays JSON antes da leitura Spark, preserva o texto bruto e registra
arquivo, ordinal e posição física. Registros com largura CSV incorreta ou objeto JSON inválido vão para a
quarentena com motivo. Erros estruturais sem ponto seguro de retomada bloqueiam a publicação. JSONL temporário no
Volume autorizado serve de entrada para a persistência Delta; após publicação bem-sucedida, os temporários são
removidos, e em falha ficam disponíveis para diagnóstico.

Cada execução prepara seus dados em schema próprio e acrescenta os resultados validados a `bronze_hist.*`. As
vistas estáveis `bronze.*` filtram o lote indicado por `bronze.controle_publicacao`. A troca desse ponteiro publica
o conjunto de fontes; uma falha antes dela mantém visível o lote anterior. O perfilador fixa o lote ativo que lê.
O autoteste sintético verifica largura CSV, preservação do bruto, posição e contagem independente dos objetos JSON.

#### Consequências, limites e validação

- `bronze.reconciliacao` fecha registros lógicos de origem = aceitos + rejeitados por arquivo ou aba; `delta` fora
  de zero impede a publicação.
- O histórico aumenta o armazenamento e cada execução grava dados no preparo e no histórico. A migração inicial
  das tabelas legadas para histórico/vistas requer janela controlada e conferência antes de liberar leitores.
- Arrays JSON estruturalmente inválidos, CSV sem ponto seguro de retomada, hash indisponível ou divergência de
  reconciliação exigem investigação; a execução não deve anunciar o lote como publicado.
- A validação local cobre sintaxe, scanner sintético e documentação. Ainda faltam execução no Databricks Free
  Edition, conferência das 14 origens autorizadas, verificação de hash e posição física, migração inicial, falha
  induzida e reexecução. DE-01 permanece `Em validação` até essas evidências serem registradas no PRD.

---

## 3. Por que existe um notebook de perfilamento separado (D7)

A pergunta "por que não medir a qualidade dentro da ingestão?" tem três respostas, e todas são de engenharia:

1. **Medir não é alterar.** A ingestão **grava** (e por isso assume `overwrite`, `_falha_scanner`, etc.). O
   perfilamento **só lê e conta** — não grava nem corrige nada. Separar mantém a ingestão com uma
   responsabilidade só e permite rodar o perfil quantas vezes for preciso sem risco.
2. **O perfil é insumo, não efeito colateral.** O produto dele é a tabela `quality.perfil_bronze`, que vira o
   **plano de limpeza da Silver** e a **seção de limpeza do dicionário de dados**. A Silver não "descobre" o que
   limpar: ela executa o que o perfil mediu, com número.
3. **Ordem e dependência explícitas.** No Workflow, o perfilador lê as tabelas que a ingestão acabou de gravar —
   o elo é `depends_on` + `run_if: ALL_SUCCESS`. Arquivos separados deixam essa dependência escrita, não implícita.

### 3.1 O que o perfil mede

Cinco famílias: **completude** (nulos/vazios), **unicidade** (duplicata exata e duplicata na chave),
**integridade referencial** (órfãos), **validade** (formato inválido e valor impossível) e **consistência**
(grafia divergente). Mais regras de negócio pontuais (ex.: fatura paga sem data de pagamento).

### 3.2 Duas correções de medição que mudaram números (D8, D9, D10)

- **Deduplicação só nas colunas de negócio (D8).** Se `_id_registro` entrasse na comparação, toda linha seria
  "única" e a duplicata exata seria sempre 0 — um falso negativo. Medindo só as colunas de dado, ela aparece:
  `leituras` 21.523, `unidades_consumidoras` 900, `medidores` 513, `faturas` 1.
- **Moeda/vírgula antes de julgar o número (D9).** `valor_total` "R$ 1.234,56" é formato, não erro. Depois de
  normalizar, o não numérico caiu de **196.624 para 2**.
- **Data não-ISO é ambígua, não inválida (D10).** `11-05-2022` casa nos dois sentidos (dia/mês e mês/dia) e dá
  datas diferentes. O perfil passou a contar isso como **ambígua** — decisão de negócio — em vez de "inválida".

### 3.3 Ajustes estruturais

`inspecoes._aba_origem` é **coluna nossa** (auditoria), não do arquivo: saiu do perfil de **dado** e entrou em
`AUDITORIA`, junto de `_arquivo_origem`, `_lote_id`, `_id_registro` e `_data_carga`. Sem isso, ela contaria como
"categoria com duas grafias" e geraria achado falso.

### 3.4 Achados do perfil que a Silver trata (números de 17/10)

| Achado | Onde | Número |
|---|---|---|
| Duplicata exata | leituras / UC / medidores / faturas | 21.523 / 900 / 513 / 1 |
| Órfão | faturas / leituras | 32.285 linhas (31.705 UCs) / 8.609 |
| Negativo impossível | leitura_anterior / consumo_kwh | 8.068 / 8.150 |
| Valor não numérico | faturas.valor_total | 2 (era 196.624) |
| Grafia divergente | inspetor / modelo / classe / tipo / resultado | 32 / 9 / 5 / 3 / 2 |
| Data ambígua dia/mês | leituras.data_leitura / faturas.data_emissao | 102.878 (≈4,71%) / 61.226 (≈2,80%) |
| Data no futuro | faturas.data_pagamento | 61.333 de 61.335 |
| Nulos | medidores.data_ultima_manutencao / data_retirada | 51.812 (100%) / 31.796 (61,37%) |

`latitude`/`longitude` são **isentas** da regra de negativo: 46.460 valores negativos cada, e negativo é coordenada
legítima (hemisfério sul/oeste). O laço de órfãos do perfil cobre **cinco** fontes por `id_uc` (`leituras`,
`faturas`, `medidores`, `ocorrencias_rede`, `geracao_distribuida`) mais `leituras` por `id_medidor` — a Silver
aplica a regra nas cinco e valida o medidor em `leituras`; só `leituras` e `faturas` trouxeram número não-zero em
17/10 (8.609 e 32.285 linhas).

---

## 4. Camada Silver — princípios

1. **A Bronze nunca é alterada.** É a fonte da verdade bruta.
2. **Nada é apagado sem rastro.** Toda linha que não entra vai para `silver.quarentena` com o **motivo** e a
   **linha bruta inteira** em JSON (`_registro`, com as colunas de auditoria dentro).
3. **Uma verdade por registro.** As chaves são únicas nas tabelas Silver; as cópias vão para a quarentena.
4. **A coluna de auditoria não é atributo de negócio**, mas **as de localização entram na Silver** como metadados
   técnicos: `_arquivo_origem`/`_lote_id`/`_id_registro` (e `_aba_origem` em inspeções). `_data_carga` fica de fora,
   só ordenando a deduplicação (D11 revisado).
5. **Toda regra que tira/troca/agrega linha tem antes e depois.** `bronze = aceitos + quarentenados` com `delta = 0`.

---

## 5. Camada Silver — tratamento atributo a atributo

Ordem de leitura: cada tabela recebe o mesmo tratamento de forma (trim, placeholders → nulo, colapso de espaços),
depois as regras específicas de negócio. `_data_processamento` carimba toda saída.

### 5.1 Sem releitura de tabela (D12)

Uma versão anterior relia a tabela logo depois do `saveAsTable` apenas para montar as chaves de integridade. Isso
adicionava custo e um ponto de inconsistência. Agora a Silver usa o **DataFrame em memória**
(`silver_uc`, `silver_med`) para as chaves de UC e medidor. A releitura continua **só onde é proposital**: na
verificação final e na conferência de chaves, que devem olhar a **tabela gravada**, e não o DataFrame.

### 5.2 Padronização de texto e número

- **Vazios:** lista de placeholders (`""`, `NULL`, `N/A`, `NA`, `NAN`, `NONE`, `-`, `--`, `S/I`, `SEM INFORMACAO`)
  vira **nulo**. Nulo **não** vira zero (regra PRD §4.1.6).
- **Texto:** trim + colapso de espaços; categorias viram MAIÚSCULO **sem acento** (`sem_acento(maiusculo(...))`).
  Só se aplica a categoria — nunca a texto livre que o usuário vê.
- **Número BR:** remove `R$` e letras, `1.234,56 → 1234.56`, aceita sufixo (`217 min → 217`). Só converte o que
  casa o padrão; o resto vira **nulo** (e, onde o campo é obrigatório, quarentena — ver faturas).

### 5.3 Datas: leitura igual à do perfil; sentinela e futuro são decisão da Silver (D13, D15, D16)

O rascunho tratava `/` e `.` como convenção brasileira (dia primeiro) e só quarentenava o hífen ambíguo — o que
**contradizia o perfil**, que mede 102.878 datas ambíguas em `leituras`. Regra atual — os passos **1–3 são idênticos**
aos do `Bronze_perfilamento.ipynb`; os passos **4–5 são decisão da Silver** (o perfil não os tem):

1. troca separadores (`/`, `.`) por hífen;
2. tenta ISO, depois `dd-MM-yyyy` e `MM-dd-yyyy`;
3. **se as duas ordens parseiam e dão datas diferentes → ambígua → quarentena** (a Silver não chuta);
4. `9999-12-31` é **sentinela** de "não se aplica": o valor é **preservado** na coluna tipada e marcado com
   `_*_sentinela`; ela **não** é lida como data real (`_tem_pagamento` a exclui). A Silver trata; o perfil **não** —
   por isso ele conta 9999-12-31 como data futura, e a flag de futuro diverge nessa coluna. Só virará nulo se a
   origem confirmar o significado (D15);
5. valor no futuro vira **flag** (`_*_futura`), **não** quarentena — o perfil §6 classifica futuro como sinal a
   investigar (a competência corrente pode cair à frente da execução); rejeitar poderia apagar dado válido.

Tudo com `try_to_date`/`try_to_timestamp`/`try_cast` (ANSI não estoura com valor ruim).

Todas as **flags `_*` de saída são booleanas não nulas** (`true`/`false`): quando a coluna de origem é nula, a flag é
`false` (via `coalesce`), de modo que o **mesmo nome de coluna significa a mesma coisa em qualquer tabela** (R28).

### 5.4 Rastreio na Silver (D11, revisado 2)

Os registros **aceitos** preservam a linhagem com **metadados técnicos**: `_arquivo_origem`, `_ordem_na_origem`,
`_lote_id` e `_id_registro` entram no `select` de **todas** as tabelas, e `_aba_origem` **só** em `inspecoes` (as 3
abas do Excel). `_data_carga` fica de fora — serve só para ordenar a deduplicação. Não são atributo de negócio (ficam
fora da completude) e o rastro inteiro segue no `_registro` da quarentena. Em `atendimentos_historico` o rastreio é
**herdado do protocolo** (a tratativa localiza-se pela linha do protocolo na Bronze). `_ordem_na_origem` é o único
deles que auxilia a busca no arquivo; a Bronze também guarda `_linha_fisica_inicial`/`_linha_fisica_final` para
CSV/JSON/XLSX (D40), enquanto o contrato Silver descrito aqui carrega apenas o ordinal. `_id_registro`
aponta para a linha na tabela Bronze. Um hash pode entrar como **complemento de integridade** (seção 9), mas não
substitui esses identificadores. A reconciliação **por arquivo/aba** continua disponível na Bronze, e a verificação
final imprime `bronze.leituras` por arquivo, `bronze.inspecoes` por aba, a identidade dos arquivos do lote
(`bronze.arquivos_lote`, §13.1c) e o status da publicação (`bronze.controle_lote`, §13.1d).

### 5.5 Tratamento por tabela

**`unidades_consumidoras`** — remove linha de cabeçalho repetida; deduplica por `id_uc` (cobre as **1.256** chaves
repetidas: **1.260** linhas excedentes, das quais **900** são duplicata exata e **360** grupos têm a cópia diferindo
em `nome_titular`/`cpf_cnpj`); `cpf_cnpj` e `cep` guardam **só os dígitos** (sem dígito → **nulo**; `cep` exige os
**8 dígitos**, então o sentinela `-1` vira nulo; `cpf_cnpj` não é hasheado na Silver — ver seção 9);
`bairro`/`municipio`/`uf`/`classe`/`status` padronizados — **`uf` sai sempre no código de 2 letras** ("Pernambuco",
"P.E." e "pe" → "PE"), `logradouro`/`numero` só aparam espaço e `nome_titular` preserva a caixa; `latitude`/`longitude`
viram número ou nulo com flag **`_geo_invalida`** (negativo legítimo, não é erro); `data_ligacao` ambígua de dia/mês →
**quarentena**, e no futuro vira flag **`_ligacao_futura`** (a sentinela, **`_ligacao_sentinela`** — sinais, não
rejeição).

**`medidores`** — deduplica por `id_medidor` (cobre 513); `data_instalacao`/`data_retirada`/
`data_ultima_manutencao` normalizadas; `modelo`/`tipo`/`status` padronizados, com mapa canônico do `tipo`
(`ELETRO-MECANICO` → `ELETROMECANICO`, `SMART METER` → `SMART`); `9999-12-31` em `data_retirada` (medidor ativo) é
**preservado** e marcado com `_retirada_sentinela` (não é lido como data real);
`data_ultima_manutencao` é 100% nula (51.812): campo opcional, **não** vira zero; `id_uc` inexistente no cadastro →
quarentena (`uc_inexistente`) — o laço de órfãos do perfil cobre esta fonte; as três datas expõem flag de futuro
(`_instalacao_futura`/`_retirada_futura`/`_manutencao_futura`) e de sentinela (`_*_sentinela`), sinal e não rejeição.

**`leituras`** — deduplica por `id_leitura` (cobre 21.523); `data_leitura` ambígua → quarentena (no futuro vira flag
`_leitura_futura`; a sentinela, `_leitura_sentinela`); `consumo_kwh` negativo → quarentena (8.150); `leitura_anterior`/`leitura_atual` negativo →
quarentena (`leitura_negativa`, cobre 8.068); `leitura_atual < leitura_anterior` **não** rejeita, marca flag
`_leitura_decrescente` (pode ser troca de medidor); `mes_referencia` fora de `AAAA-MM` → quarentena
(`mes_referencia_invalido`, o perfil checa o formato nas duas fontes); medidor/UC inexistente → quarentena (cobre
8.609 órfãos).

**`faturas`** — deduplica por `id_fatura` (cobre 1); `9999-12-31` em `data_pagamento` é **preservado** e marcado com
`_pagamento_sentinela` (responde pelas duas linhas do relatório antigo — "data inválida" e "não paga com data" eram o
mesmo registro); moeda → número;
`valor_total` não numérico → quarentena (cobre 2); UC inexistente → quarentena (cobre 32.285 linhas / 31.705 UCs);
`mes_referencia` fora de `AAAA-MM` → quarentena; flags `_valor_inconsistente` (|total − (energia+tributos)| > 0,01),
`_paga`, `_tem_pagamento`, `_pagamento_antes_emissao` (regra ALTA do perfil), `_emissao_futura`/`_vencimento_futura`/
`_pagamento_futura`, `_*_sentinela` e `_valor_negativo` **documentam** sem rejeitar — data no futuro e valor negativo
de fatura são sinal a investigar (estorno/ajuste, competência corrente), não defeito provado.

**`geracao_distribuida`** — deduplica por `id_uc`; `potencia_kwp` e `energia_injetada_kwh_media_mensal` → número, com
**negativo → quarentena** (`gd_negativo`), como o perfil (§7) classifica; `id_uc` inexistente no cadastro →
quarentena (`uc_inexistente`, o laço de órfãos do perfil cobre esta fonte); `data_conexao` normalizada, com flag
`_conexao_futura` se cair no futuro (e `_conexao_sentinela` para a sentinela). Limite: potência instalada **não**
prova energia gerada/abatida (ver Gold).

**`ocorrencias_rede`** — deduplica por `id_ocorrencia` (o dict `CHAVES` do perfil mede `chave duplicada` aqui,
`id_ocorrencia_duplicado`); `data_abertura`/`data_encerramento` são **timestamp** (com hora); `duracao_min` vinha com
sufixo (`217 min`) → número; negativo → quarentena; UC inexistente → quarentena (o laço de órfãos do perfil cobre
esta fonte também); carimbo no futuro vira **flag** (`_abertura_futura`/`_encerramento_futura`), não quarentena.
Ressalva de medição: as contagens de data de `ocorrencias_rede` e `atendimentos` saíram infladas
em 17/10 (o leitor aceitava só data pura); a leitura foi corrigida e **essas contagens serão refeitas** — por isso
não há número novo derivado delas.

**`atendimentos`** — o JSON veio **aninhado** (`historico` é lista de tratativas). `atendimentos` é deduplicado por
`protocolo` (o dict `CHAVES` do perfil mede `chave duplicada` aqui, `protocolo_duplicado`), e o histórico exploda só
os protocolos aceitos. Duas saídas com grãos distintos:
`silver.atendimentos` (uma linha por **protocolo**, com `qtd_tratativas`) e `silver.atendimentos_historico` (uma
linha por **tratativa**, via **`explode`** — protocolo sem tratativa não gera linha de histórico, então o grão de
saída bate exatamente com `sum(size(historico))`). Por isso `atendimentos_historico` **não** entra no quadro de
reconciliação: sua entrada é a soma de `size(historico)`, não a contagem de protocolos (PRD: não somar grãos
diferentes). Data no futuro (`_abertura_futura`/`_fechamento_futura`) e nota negativa (`_nota_negativa`) são flags.

**`inspecoes`** — consolida as 3 abas e **publica `_aba_origem`** como metadado de rastreio (as demais tabelas publicam
só `_arquivo_origem`/`_lote_id`/`_id_registro`, seção 5.4); deduplica por `id_inspecao`
(`id_inspecao_duplicado`); `resultado` normaliza as grafias divergentes (2 grupos) para dois valores; `inspetor`
passa a ser padronizado como as demais categorias — decisão a revisar, incluindo se o nome é exibido ao usuário
(seções 8 e 14.4); `tipo_irregularidade` e `data`
tipados (no futuro, flag `_data_futura`; a sentinela, `_data_sentinela`); `kwh_recuperado` negativo → quarentena
(`kwh_recuperado_negativo`), como o perfil (§7) classifica.

### 5.6 Contrato de tipos (D17)

Antes de transformar, a Silver **verifica o que assume da Bronze** e **falha à vista** se não bater: `historico`
tem de ser `array<struct>` com `sequencia`/`data`/`acao`/`canal`, e `nota_satisfacao` tem de converter para
`double`. Na saída, um segundo contrato confere os tipos publicados por tabela. Isso evita gravar tabela errada em
silêncio.

---

## 6. Motivos de quarentena (vocabulário único)

`_motivo` é um array (pode haver mais de um por linha) serializado com `; `. Vocabulário atual:
`linha_cabecalho_repetida`, `data_<col>_ambigua`, `data_<col>_invalida`, `id_uc_duplicado`,
`id_medidor_duplicado`, `id_leitura_duplicado`, `id_fatura_duplicado`, `id_ocorrencia_duplicado`,
`id_inspecao_duplicado`, `protocolo_duplicado`, `consumo_kwh_negativo`, `leitura_negativa`, `medidor_inexistente`,
`uc_inexistente`, `medidor_em_quarentena`, `uc_em_quarentena`, `duracao_negativa`, `valor_total_nao_numerico`,
`mes_referencia_invalido`, `gd_negativo`, `kwh_recuperado_negativo`.

> **Órfão × cascata.** `*_inexistente` é a chave que **não existe** na Bronze (defeito do registro);
> `*_em_quarentena` é a chave que **existe** e cujo cadastro pai caiu na quarentena — a linha está **bloqueada**,
> não malformada (D38/R41). As duas aparecem separadas no confronto e a segunda é reprocessável.

> **Futuro não é motivo.** `data no futuro` **não** aparece aqui: desde a revisão de 18/10 ela é **flag**
> (`_*_futura`), não quarentena (o perfil classifica futuro como "investigar"). O status interno da coluna ainda
> registra `futura`, mas ele não vira motivo de rejeição. A **sentinela `9999-12-31`** também **não** é motivo:
> desde a revisão do time (D15) ela é **preservada** e marcada com `_*_sentinela` (§5.3).

Padronizar o motivo é o que permite **confrontar a quarentena com o número do perfil** (seção 7) e transformar
"rejeitado" em frase auditável.

---

## 7. Reconciliação e confronto com o perfil (D18)

- **Reconciliação Bronze → Silver:** por tabela, `bronze = aceitos + quarentenados`, com `delta` explícito. Uma
  linha com mais de um motivo conta **uma vez** no total (os motivos são um array), então a soma fecha.
- **Confronto com o perfil (lido, não digitado):** a verificação final **lê `quality.perfil_bronze`** e compara,
  motivo a motivo, o número do perfil com o medido na quarentena — não há número de perfil escrito no código. Ponto
  que confunde: o perfil mede **chave repetida** (nº de chaves que se repetem) enquanto o motivo da quarentena conta
  **linhas excedentes** (chave repetida 3× = 1 no perfil, 2 na quarentena) — então `id_*_duplicado` pode vir
  diferente do número do perfil de forma legítima. A linha de **duplicata exata** e a de **grafia divergente** são
  medidas na **saída**, onde o esperado é **zero**.
- **Reconciliação de ingestão (lida, não digitada):** a verificação final também lê **`bronze.reconciliacao`** e
  confere que a entrada da Silver (`count` de cada tabela Bronze) bate com as `gravadas` da ingestão — costura a
  Silver à Landing em vez de assumir. Como a Bronze reconcilia **por origem** (D39), a Silver **soma `gravadas` por
  `_tabela`** antes de comparar; comparar linha a linha daria `DIVERGE` nas leituras (5 origens) e nas inspeções (3).
  A mesma seção imprime a **identidade dos arquivos** do lote (`bronze.arquivos_lote`, §13.1c) e o **status da
  publicação** (`bronze.controle_lote`, §13.1d).
- **Invariantes da Silver:** chaves únicas (as 8 tabelas são deduplicadas), zero órfãos (nas seis tabelas com FK),
  zero negativos (leituras, ocorrências, GD, inspeções), zero grafia divergente, contrato de tipos.
- **Cobertura do plano de limpeza:** no fim da seção 13, a verificação **lê** `quality.perfil_bronze` e lista
  **todos** os achados com ocorrências > 0 — o que não tem linha no confronto está tratado por padronização/flag
  (não por rejeição) ou é regra de negócio exposta como coluna (D32).

**Só no runtime:** `delta`, contagens por motivo e invariantes só se confirmam executando o notebook na Free
Edition. O histórico de revisão não substitui a execução do notebook no lote autorizado nem comprova os resultados
de negócio da versão atual.

---

## 8. Pendências da Silver (o que a camada não resolve sozinha)

1. **Data ambígua de dia/mês (bloqueia receita/consumo por competência).** O arquivo não diz a ordem.
   `leituras.data_leitura` 102.878 (≈4,71% de 2.182.468) e `faturas.data_emissao` 61.226 (≈2,80% de 2.184.623).

   | Opção | O que faz | Ganho | Custo / risco |
   |---|---|---|---|
   | **A. Convenção brasileira** | trata `/`/`.` como `dd/MM/yyyy`; só o hífen com dia e mês ≤ 12 fica ambíguo | recupera ~102,9 mil leituras e ~61,2 mil faturas | se a origem escreveu `MM/dd`, troca dia/mês **em silêncio** e erra a competência de receita |
   | **B. Quarentena (atual)** | nenhuma data ambígua entra | zero risco; reversível (a linha bruta fica na quarentena) | perde ~4,71% das leituras e ~2,80% das faturas até a decisão |
   | **C. Evidência por arquivo** | mede, por arquivo/ano, quantas datas têm componente > 12 e aceita a convenção só onde houver prova | decide com dado, não com suposição | exige um passo de análise; pode dar resposta diferente por arquivo |

   **Decidido pelo time (18/10): manter **B** e rodar **C** para produzir a evidência por arquivo** — as ambíguas
   seguem em quarentena e fora dos cálculos por competência até haver prova. (D36)
2. **Sentinela `9999-12-31` — decidido pelo time (18/10).** Confirmar com a origem; **até a confirmação, preservar o
   valor original** e não usá-lo como data real (flag `_*_sentinela`; `_tem_pagamento` a exclui). Se a origem
   confirmar, virar nulo na Silver e documentar o efeito em `data_retirada` e `_tem_pagamento` (Gold). (D15)
3. **`inspetor` — decidido pelo time (18/10): manter a padronização atual.** Medir no próximo perfilamento e
   **confirmar se o nome do inspetor é exibido ao usuário** antes de qualquer mudança. (D37)
4. **Rastro linha a linha do que foi aceito — comportamento atual da branch:**
   `_arquivo_origem`/`_lote_id`/`_id_registro` (e `_aba_origem` em inspeções) entram na Silver como metadados
   técnicos; `_data_carga` fica de fora; um hash pode complementar a integridade (D11 revisado, §5.4). A issue #18
   registra posições diferentes sobre a linhagem; este registro descreve a implementação, sem atribuir consenso.
5. **`mes_referencia` de `leituras` e chave duplicada de `ocorrencias_rede`/`atendimentos`.** **Resolvido na 3ª
   revisão:** o perfil mede os três (o dict `CHAVES` dele inclui as duas fontes e o laço dele checa `mes_referencia`
   nas duas); a Silver passou a aplicar `mes_referencia_invalido` em `leituras` e a deduplicar `ocorrencias_rede` e
   `atendimentos`. Não era "sem número" — era número não capturado na nota.
6. **Quarentena dos rejeitados da Bronze.** Ainda falta decidir se a Silver reprocessará ou apenas auditará
   `bronze.rejeitados` (ver a decisão consolidada na §2.11; a última execução registrada não tinha rejeições).
7. **Divergências conscientes Silver × perfil.** A verificação final pode divergir do perfil por (a) `vazio` mais
   estrito na Silver (placeholder), (b) cascata de órfão (FK validada na Silver, não na Bronze) e (c) chave repetida
   × linha excedente. Não são bug — estão explicadas na seção 14.5 do notebook, e `vazio` e cascata são **medidos**
   pela seção 13. Dois pontos de julgamento também são declarados: (d) o perfil mede "valor não numérico" em
   **todas** as colunas numéricas. Medidas necessárias malformadas vão à quarentena; coordenadas e nota de
   satisfação inválidas ficam nulas com flag explícita; e (e) valores negativos em `nota_satisfacao` são mantidos
   com `_nota_negativa`. Não está confirmado que signifiquem "sem avaliação"; a interpretação de negócio deve ser
   confirmada antes de lhes atribuir esse significado.
8. **Datas inválidas em `atendimentos` e `ocorrencias_rede`.** A versão atual envia timestamps inválidos à
   quarentena nas duas tabelas. As contagens do perfil de 17/10 são históricas; conferir os volumes após atualizar
   o perfil e executar a Silver no mesmo lote.
9. **Cascata de órfão — decidido em 19/10: A (validar contra a Silver) + rótulo do bloqueio (§14.7).** A validação
   continua contra a **Silver** (garante integridade referencial interna), mas a linha que aponta para cadastro que
   **existe na Bronze** e caiu na quarentena deixa de ser contada como órfã: recebe o motivo
   `uc_em_quarentena`/`medidor_em_quarentena`. O motivo `*_inexistente` fica só para a chave ausente da Bronze — é o
   que faz `medidor_inexistente` voltar a bater com o perfil (**8.609**) e separa as **58.214** leituras bloqueadas
   (1.369 medidores removidos por `data_instalacao` ambígua/duplicação; `faturas.uc_inexistente` 32.285 → 32.287 =
   2 por cascata). A linha continua na Bronze e no `_registro` da quarentena, com origem e ordem, para reprocessar
   quando 14.1 sair. Se o negócio confirmar que a identidade do medidor vale mesmo com `data_instalacao` ambígua,
   avaliar a **B parcial** (medidor entra com a data nula + flag) — não agora. (D38, R41)

---

## 9. Camada Gold — proposta e decisões a tomar

> A Gold **não existe ainda**. Esta seção é a **proposta de modelagem** para não repetir a modelagem quando o
> notebook for escrito; cada item é decisão a registrar em `docs/dicionario_gold.md` (DE-08) e, se alterar
> arquitetura/métrica, em ADR (workflow §4).

### 9.1 Tabelas propostas (grão e chave)

| Tabela Gold | Uma linha representa | Chave | Perguntas que atende |
|---|---|---|---|
| `receita_uc_competencia` | 1 UC × 1 competência | `id_uc + mes_referencia` | receita, faturado × pago, preço médio |
| `consumo_uc_competencia` | 1 UC × 1 competência | `id_uc + mes_referencia` | consumo, queda de consumo |
| `uc_360` | 1 UC | `id_uc` | visão 360 (cadastro + últimos indicadores) |
| `continuidade_alimentador` | 1 alimentador × 1 período | `alimentador + período` | DEC/FEC simplificado |
| `gd_uc` | 1 UC com GD | `id_uc` | geração distribuída |
| `inspecao_prioridade` | 1 UC (ou 1 ordem) | `id_uc` / `id_inspecao` | fila de inspeção, energia recuperável |
| `atendimento_indicadores` | 1 período (ou 1 canal) | `período` | satisfação, volume de atendimento |

### 9.2 Regras de negócio a declarar antes de publicar a métrica

- **Faturado × pago** e **competência × vencimento** são eixos diferentes (PRD §5.4); receita não é "valor_total"
  somado às cegas.
- **Preço-volume:** a decomposição tem de **fechar com o total**, com termo de interação e regra de
  arredondamento explícitos (PRD §4.3).
- **Joins não podem multiplicar receita/energia:** agregar cada fato no grão pretendido **antes** de unir
  (PRD §4.1.4 e invariante de Gold).
- **DEC/FEC:** DESCREVER numerador, denominador, janela e UC afetada; **não** apresentar como apuração regulatória
  oficial (DE-05).
- **GD:** potência instalada **não** prova energia gerada/abatida por competência (PRD §4.2, GD).
- **Inspeção:** separar suspeita, ordem operacional e resultado; `inspecoes.xlsx` é histórico (PRD §5.4).

### 9.3 Exclusão de dados pessoais na projeção Gold (D20, decidido)

**Decisão — 28/10/2026:** publicar a Visão 360 e a fila de inspeção com as colunas analíticas necessárias, excluindo CPF/CNPJ, nome do titular, endereço, CEP, coordenadas e metadados técnicos iniciados por `_`. Esses campos não são substituídos por hash nem por versões mascaradas. A projeção é definida em `notebook/Silver_to_gold.ipynb` e descrita no [dicionário Gold](../docs/dicionario_gold.md).

**Motivo:** os consumidores identificam a unidade por `id_uc` e usam classe e território como contexto. O escopo analítico combinado não exige agrupar por titular; manter identificadores pessoais transformados acrescentaria dados sem necessidade demonstrada. A exclusão reduz a exposição na Gold e nos CSVs. `id_uc` continua sendo um identificador da unidade; esta projeção não constitui garantia de anonimização do conjunto.

**Limite:** a decisão não apaga os registros de origem. Bronze e Silver permanecem no ambiente autorizado, com acesso restrito e rastreabilidade. A recomendação anterior de hash com salt mais mascaramento fica substituída por esta decisão.

**Verificação:** a projeção da Gold foi reportada como conferida nas tabelas Delta oficiais, com 15 colunas na Visão 360 e 14 na fila. Os cabeçalhos dos sete CSVs recebidos foram conferidos localmente contra o contrato do Backend; Visão 360 e fila mantêm as 15 e 14 colunas esperadas, sem campos pessoais adicionais. No portal, confirmar que número da UC, classe e município/bairro atendem à identificação na tela do atendente antes de registrar essa suposição como validada.

### 9.4 Exportação (DE-06)

Gold → CSV → banco local (`SQLite` ou `PostgreSQL`, a definir) precisa ser **reimportável sem duplicar** (segunda
carga do mesmo lote não duplica linhas/valores). Conferir esquema, chaves, contagens e agregados nos dois lados.
Decisão de banco ainda aberta (PRD §5).

---

## 10. Decisões transversais e de processo

- **Workflow (DE-07):** a definição continua com `Landing_to_Bronze → Bronze_perfilamento`
  (elo `depends_on` + `run_if: ALL_SUCCESS`); o Workflow permanece inalterado conforme `43c2e590`. A Silver ainda
  não está encadeada ao Job; a integração depende de execução e revisão próprias.
- **Agenda proposta:** mensal, dia 5, 03:00 (America/Recife) — o insumo é mensal (competência) e a reexecução é
  segura porque a Bronze é `overwrite` com `delta = 0`. É proposta para operação futura, **não** integração de
  produção existente (o case entrega extração única).
- **Ambiente:** Free Edition sobre Spark Connect, compute **serverless** — por isso **não** se usa `.cache()` e as
  conversões são à prova de ANSI.
- **Idempotência:** reexecutar Bronze/Silver não acumula versões (Bronze `overwrite`; Silver `overwrite` com
  `overwriteSchema`).
- **Processo:** a Silver está versionada na branch `feat/silver`, derivada de `feat/bronze-rastreabilidade`; o PR #29
  reúne a implementação desta branch.

## 11. Histórico de revisão e execução da Silver

As revisões abaixo registram decisões e resultados de versões anteriores. A execução real disponível está em §11.3;
ela não comprova a revisão atual, cujo estado está descrito em §11.4 e no PRD.

### 11.1 Revisão pós-execução (18/10/2026)

Feita **depois** de a primeira versão rodar na Free Edition (todas as células passaram, `delta = 0` em todas as
tabelas). O que a revisão encontrou e o que foi corrigido **na fonte**, com base no próprio repositório:

| # | Achado | Gravidade | Correção |
|---|---|---|---|
| R1 | `PERFIL` e `RECON` eram **declarados e nunca lidos**; o confronto usava números digitados (podiam ficar obsoletos em silêncio) | alta | Seção 13 passa a **ler** `quality.perfil_bronze` e `bronze.reconciliacao`; nenhum número de perfil é digitado (D22) |
| R2 | `data no futuro` ia para **quarentena** em `faturas.data_emissao`/`data_vencimento` e em `ocorrencias_rede`/`atendimentos` — podia **apagar fatura/leitura válida** da competência corrente | alta | Futuro vira **flag** (`_*_futura`), não quarentena (o perfil §6 diz "investigar", não erro) (D21) |
| R3 | Negativos impossíveis de **outras fontes** (`potencia_kwp`, `energia_injetada_kwh_media_mensal`, `kwh_recuperado`) não eram tratados | média | Quarentena (`gd_negativo`, `kwh_recuperado_negativo`); fatura/nota negativas viram flag (estorno/ajuste/"sem avaliação") (D23) |
| R4 | `atendimentos_historico` usava `explode_outer`, inflando o grão (protocolo sem tratativa gerava 1 linha) | média | `explode` (D24); grão de saída = `sum(size(historico))` |
| R5 | Doc dizia que a sentinela `9999-12-31` "explica parte dos nulos" de `data_retirada` | baixa | Corrigido: os 31.796 nulos medidos são **vazios**, não sentinela; o tratamento da sentinela é defensivo (assunção) |

**Segunda revisão (18/10/2026), depois da anterior** — comparação das funções de normalização (Silver × perfil) e
confronto do notebook com o `Landing_to_Bronze.ipynb`:

| # | Achado | Gravidade | Correção |
|---|---|---|---|
| R6 | A janela de deduplicação desempatava por `_data_carga`, que é **constante por lote** — no empate de completude a linha escolhida era **arbitrária entre execuções** | média | Terceiro critério `_id_registro` (asc) na janela; deduplicação fica **determinística** (D25) |
| R7 | O status `futura` era calculado para UC, medidores, leituras, GD, inspeções, mas **não virava coluna** — o sinal se perdia (só faturas/ocorrências/atendimentos expunham flag) | média | Toda tabela com data expõe `_*_futura` (D26); contrato de saída atualizado |
| R8 | `vazio`/`texto` checavam placeholder **antes** de colapsar espaço: `SEM  INFORMACAO` (espaço duplo) não era reconhecido como vazio | baixa | Colapsa antes de checar; `numero`/`data` provados iguais ao perfil, divergência só no `vazio` (documentada em 14.5) (D27) |
| R9 | Se uma execução não rejeitasse nada, a `silver.quarentena` **anterior** ficava viva e era lida como se fosse desta rodada | baixa | `DROP TABLE IF EXISTS` no ramo vazio (D28) |
| R10 | O confronto não mostrava **data inválida**, **chave duplicada** das fontes não deduplicadas (GD/inspeções/ocorrências/atendimentos) nem a **cascata de órfão** | média | Seção 13 ganhou esses três blocos (D29); a cascata explica por que o órfão pode superar o perfil |
| R11 | A regra de normalização precisava de comparação explícita com o perfil | média | `numero`/`data` seguem os critérios do perfil; placeholders permanecem documentados como diferença consciente |

Conclusão da segunda revisão: nenhuma incoerência de contrato, de vocabulário de motivos ou de grão foi
encontrada; o que restou é **comportamento deliberado** (medido e documentado em 14.5) e pendência de negócio.

**Terceira revisão (18/10/2026)** — foco em **cobertura**: *todo achado do perfil chegou na Silver?* Confrontando o
notebook com o `Bronze_perfilamento.ipynb` célula a célula (dict `CHAVES`, laço de órfãos, regras de negócio):

| # | Achado | Gravidade | Correção |
|---|---|---|---|
| R12 | Órfão de UC só era tratado em `leituras`/`faturas`/`ocorrencias_rede` — o perfil mede também em **`medidores`** e **`geracao_distribuida`** (o laço dele cobre as duas) | média | Regra `uc_inexistente` nas duas, invariante de órfãos nas seis tabelas e linhas no confronto (D30) |
| R13 | `ocorrencias_rede` e `atendimentos` **não eram deduplicadas**, mas o dict `CHAVES` do perfil mede `chave duplicada` das duas — a saída podia ter chave repetida, contrariando o invariante "chaves únicas" (a §14.4 dizia "sem número", o que era falso) | média | Dedup por `id_ocorrencia`/`protocolo` (`id_ocorrencia_duplicado`, `protocolo_duplicado`); histórico sai dos protocolos aceitos (D31) |
| R14 | A seção `14.6` (inserida por mim) ficou **antes** da `14.5` | baixa | `14.5 Divergências`, `14.6 Próximos passos` (D35) |
| R15 | Não havia como saber se **todo** achado do perfil foi tratado | média | Bloco de **cobertura** na seção 13: lista todos os achados com ocorrências > 0, lidos do perfil (D32) |
| R16 | `mes_referencia` era validado só em `faturas`; o perfil checa o formato **nas duas** fontes | média | `mes_referencia_invalido` também em `leituras` (D33) |
| R17 | A regra ALTA do perfil `pagamento antes da emissão` não tinha tratamento | média | Flag `_pagamento_antes_emissao` em `faturas` (D34) |
| R18 | As regras de negócio MEDIA/ALTA do perfil (§9 dele) não estavam mapeadas na doc | baixa | Tabela de justificativa na §14.4 do notebook (viram sinal/flags, não rejeição) |

Conclusão da terceira revisão: as lacunas eram de **cobertura** (achado do perfil sem tratamento), não de lógica.
Com o bloco de cobertura da seção 13, a próxima execução prova item a item.

**Quarta revisão (18/10/2026)** — foco em **consistência da documentação com o código** (confronto da
§5.3/§5.5/§6/§7/§8 com o próprio notebook e com o `Bronze_perfilamento.ipynb`), depois das revisões anteriores:

| # | Achado | Gravidade | Correção |
|---|---|---|---|
| R19 | A §5.5 (tratamento por tabela) e a §6 (motivos) estavam defasadas de R7/R12/R13/R16/R17: não citavam flag de futuro em UC/medidores/leituras/GD/inspeções, órfão em `medidores`/`geracao_distribuida`, dedup de `ocorrencias_rede`/`atendimentos`/`inspecoes` (`id_ocorrencia_duplicado`/`protocolo_duplicado`/`id_inspecao_duplicado`), `mes_referencia` em `leituras` nem `_pagamento_antes_emissao` | média | Seções reescritas para espelhar o código; vocabulário de motivos completado |
| R20 | A §5.3 dizia que a regra de datas era **"idêntica à do perfil"**, mas o perfil **não** trata a sentinela `9999-12-31` — esse passo (e a flag de futuro) é decisão da Silver | média | Passos 1–3 marcados como iguais ao perfil; 4–5 como decisão da Silver |
| R21 | A §8 item 7 dizia que "as demais colunas numéricas não têm contagem no perfil"; o perfil mede "valor não numérico" em **todas** as colunas numéricas, mas só `valor_total` teve ocorrência não-zero (2) | média | Texto corrigido; a assunção sobre `nota_satisfacao` negativa foi declarada |
| R22 | O notebook (§1, decisão 9) sugeria que o perfil não classifica `nota_satisfacao` negativa como impossível; o perfil a inclui em `NEGATIVO_IMPOSSIVEL` (ALTA) | baixa | Redação corrigida + bullet na §14.4 (só markdown) |

Conclusão da quarta revisão: os ajustes são de **documentação** — nenhuma linha de código mudou (o hash do código
segue `bfd3ce6d6e72be37`). Naquele momento, as interpretações de negócio das seções 14.1–14.4 aguardavam discussão;
as regras implementadas posteriormente estão descritas no registro D53–D60 e no notebook atual.

**Quinta revisão (18/10/2026)** — foco no **núcleo do código** (helpers, `rejeitar`/`gravar`, contadores e a
reconciliação), lido linha a linha:

| # | Achado | Gravidade | Correção |
|---|---|---|---|
| R23 | `rejeitar` dava `append` na quarentena **incondicionalmente**, então `QUARENTENA` nunca ficava vazia e o ramo que **remove** a quarentena de uma execução anterior (D28/R9) era **inalcançável** — o código não fazia o que a decisão documentava | média | `append` só quando há rejeição (`n_rej > 0`); o `DROP TABLE IF EXISTS` passa a valer de fato (código — muda o hash) |
| R24 | A decisão "só `faturas.valor_total` rejeita não numérico" (as demais colunas viram nulo) estava só na doc; o notebook não a expunha | baixa | Bullet em §14.4 do notebook (markdown) |
| R25 | `atendimentos` só **tipava** as datas de abertura/fechamento (inválida → nulo), enquanto **as outras** tabelas com data quarentenavam inválida — e o perfil mede "data inválida" nas duas colunas (o `DATAS` dele inclui `atendimentos`) | baixa | Histórico da versão anterior; D59 registra a regra atual de enviar timestamps inválidos de `atendimentos` e `ocorrencias_rede` à quarentena |

Conclusão da quinta revisão: R23 é a única correção de **código** desde a terceira revisão; as demais foram de
documentação. Não há número novo — o ajuste é de **controle de fluxo** (não herdar quarentena antiga), não de
tratamento de dado. O hash do código passa a `1ea620fdfa0d83ff`.

**Sexta revisão (18/10/2026)** — foco na **verificação final** e na **consistência de tratamento** (código lido linha
a linha: helpers, blocos da seção 13 e os `select`s de saída):

| # | Achado | Gravidade | Correção |
|---|---|---|---|
| R26 | O bloco de **órfãos remanescentes** da §13 usava `left_anti` puro: como `null` não casa com nada, uma **chave estrangeira nula** era contada como órfã — mas a regra da Silver (`chave IS NOT NULL AND ausente no cadastro`) **não** trata nulo como órfão (a própria §13 diz "chave estrangeira nula não é órfã pela regra"). O "deve ser 0" podia dar **falso positivo**, contrariando o invariante | baixa | O check passa a filtrar `isNotNull` antes do anti-join (`orfaos_remanescentes`), medindo **órfão de verdade**; a chave nula segue reportada no bloco separado (código — muda o hash) |
| R27 | `cep` era gravado **só com dígitos**, mas vazio/placeholder virava **string vazia**, enquanto `cpf_cnpj` (mesmo tipo de campo: código extraído por dígitos) virava **nulo** — destoava do princípio "vazio vira nulo" (§5.2) | baixa | `cep` alinhado ao `cpf_cnpj`: só dígitos e **nulo** quando não há dígito (código — muda o hash) |
| R28 | Algumas flags podiam ficar **nulas** quando a coluna de origem era nula (`_abertura_futura`/`_fechamento_futura` em `atendimentos`, `_paga` em `faturas`, `_leitura_decrescente` em `leituras`), enquanto todas as outras flags do layer são booleanas **não nulas** — e `_abertura_futura`, com o **mesmo nome**, era não nula em `ocorrencias_rede` e nula em `atendimentos` | baixa | Flags com `F.coalesce(..., F.lit(False))`: toda flag é `true`/`false` (nunca nula) e o mesmo nome de coluna tem a mesma semântica em todas as tabelas (código — muda o hash) |

Conclusão da sexta revisão: R26 corrige um **falso positivo da verificação** (não do dado — sem FK nula o resultado é
idêntico); R27 e R28 são **consistência de tratamento/contrato** (campo de código e flags). Nenhum número do perfil
muda; nenhum invariante de dado é afetado. O hash do código passa a `f9228e8527173c51`.

A versão atual (após R1–R28) **ainda não rodou** na Free Edition: R1–R4, R12–R17, R23, R27 e R28 mudam o que o
notebook faz (R26 muda só o bloco de verificação), então precisa de **nova execução** para reconfirmar `delta = 0` e
as contagens de quarentena. As contagens citadas na seção 5 vieram da execução anterior e continuam válidas como
**entrada** (o perfil não mudou).

**Sétima revisão (18/10/2026)** — foco no **grão de `atendimentos_historico`** e no fechamento da §14.5:

| # | Achado | Gravidade | Correção |
|---|---|---|---|
| R29 | `sum(size(historico))` (grão de entrada de `atendimentos_historico` e coluna `qtd_tratativas`) dependia do comportamento de `size(null)` **na sessão**: sob ANSI devolve **nulo** (ok), mas fora dela devolve **`-1`** — nesse caso `qtd_tratativas` sairia `-1` e a reconciliação acusaria delta falso. `historico` é inferido do JSON, então uma linha pode chegar sem ele | baixa | `F.coalesce(F.size("historico"), F.lit(0))` nas três contas: protocolo com histórico nulo conta **0** tratativas, independente da sessão (código — muda o hash) |

Fechamentos de documentação da sétima revisão: a §13 e a §14.5 do notebook passam a explicitar a **4ª divergência
consciente** (o anti-join do perfil conta chave **nula** como órfã; a Silver não) — o número do perfil pode ser
**maior** que a quarentena de órfão, e o bloco de FK nula mostra a diferença.

Conclusão da sétima revisão: R29 remove a dependência de uma configuração de sessão e torna `qtd_tratativas` um
contador limpo; o restante é documentação. Nenhum número do perfil muda. O hash do código passa a
`75d91c8c7b86c51e`.

A versão atual (após R1–R29) **ainda não rodou** na Free Edition: R1–R4, R12–R17, R23, R27, R28 e R29 mudam o que o
notebook faz (R26 muda só o bloco de verificação), então precisa de **nova execução** para reconfirmar `delta = 0` e
as contagens de quarentena. As contagens citadas na seção 5 vieram da execução anterior e continuam válidas como
**entrada** (o perfil não mudou).

**Revisão de decisões do time (18/10/2026)** — depois de a primeira versão rodar sem erros na Free Edition, o time
respondeu às issues (§14.1–14.4 / D36–D37). Duas decisões mudam o **código** (e o hash):

| # | Decisão | Efeito no código |
|---|---|---|
| R30 | **Rastreio na Silver (opção A)** — `_arquivo_origem`/`_lote_id`/`_id_registro` em todas as tabelas e `_aba_origem` em `inspecoes`; `_data_carga` fora; `atendimentos_historico` herda do protocolo (D11 revisado) | `select` de 9 tabelas; contrato de saída; §13 troca o check "auditoria ausente" pelo de "rastreio presente"; a duplicata exata da §13 exclui o rastreio |
| R31 | **Sentinela preservada** — o valor `9999-12-31` fica na coluna tipada + flag `_*_sentinela`; `_tem_pagamento` exclui a sentinela (D15 revisado) | `add_data` deixa de anular; 12 flags novas; `_tem_pagamento`; contrato de saída |

As demais decisões **não** mudam código: data ambígua segue em quarentena (B) + evidência por arquivo (C) (D36);
achados que não rejeitam + `inspetor` mantêm as regras atuais, a quantificar no próximo perfilamento, com a
exibição do `inspetor` a confirmar (D37).

Conclusão: R30/R31 são **mudanças de contrato** pedidas pelo time; o resto é registro. O hash do código passa a
`3911197866596542`.

**Verificação da execução (18/10/2026)** — o time rodou a versão R30/R31 na Free Edition: todas as células
passaram e os invariantes fecharam:

- Reconciliação Bronze→Silver com `delta = 0` nas 8 tabelas; entrada da Silver = `gravadas` da ingestão em todas.
- Invariantes: 0 chave duplicada, 0 duplicata exata, 0 órfão remanescente, 0 negativo, 0 grafia divergente e 0 FK
  nula; contrato de tipos OK; rastreio presente nas 9 saídas (`_data_carga` ausente).
- Confronto com o perfil: duplicatas, negativos, datas ambíguas e "valor não numérico" batem **exatamente**.

Divergências **explicadas** (não são defeito):
- `medidor_inexistente` 8.609 → 66.823 = 8.609 órfãos reais + 58.214 por **cascata** (leitura cujo medidor saiu da
  Silver: 1.369 medidores removidos — `data_instalacao` ambígua [1.381 linhas] + 513 duplicados + cabeçalho).
- `id_uc_duplicado` 1.256 → 1.260 = chaves vs linhas excedentes (o outro achado do perfil, "id_uc duplicado no
  cadastro", já é 1.260 — bate exato).
- `faturas.uc_inexistente` 32.285 → 32.287 = +2 por cascata.
- "Data no futuro" = 0 em várias colunas: o perfil conta a **sentinela** como "no futuro"; a Silver a separa
  (`_*_sentinela`). `ocorrencias_rede`/`atendimentos` divergem em "data inválida" por **tipagem** (R25) + contagem
  inflada do perfil.

| # | Achado | Gravidade | Correção |
|---|---|---|---|
| R32 | O bloco de "data no futuro" só imprimia a flag de futuro — não dava para separar "futuro real" de **sentinela** pelas flags (várias colunas com perfil > 0 e flag 0) | baixa | Passa a imprimir `futura` e `sentinela` lado a lado (código — muda o hash) |
| R33 | O bloco de "data inválida" atribuía a divergência de `ocorrencias_rede`/`atendimentos` só a "placeholder", quando a causa é **tipagem** (R25) + contagem inflada do perfil; e o confronto de **data ambígua** não mostrava `medidores.data_instalacao` nem `inspecoes.data` (que a Silver **já** quarentena) | baixa | Nota corrigida e as duas linhas acrescentadas ao confronto (código — muda o hash) |

Conclusão da 10ª revisão: a Silver **passou** na verificação (execução real); os ajustes são de **verificação**
(deixar a divergência visível e explicada), sem mudar tratamento de dado. A cascata de órfão virou **decisão de
produto** (D38): documentada no notebook (§14.7) e na seção 10 item 9. O hash do código passa a
`d3c43b74214baf8b` (inalterado pela §14.7 — markdown).

**Revisão da contribuição do colega (19/10/2026)** — quatro itens propostos na revisão do PR #8, todos aceitos, mais
o efeito colateral que a revisão dele não previa (o perfilador). Os itens 2 e 3 fecham lacunas que o **ADR de Bronze
vigente naquela revisão** já declarava; os outros dois são da mesma família (rastreabilidade e momento da falha). O **R39** e o
**R40** não vêm da revisão: apareceram na primeira execução real no Databricks (R39) e na revisão do código de
verificação depois dela (R40):

| # | Achado | Gravidade | Correção |
|---|---|---|---|
| R34 | **Reconciliação por tabela** (item 1): `_arquivo_origem` era rótulo (`leituras/*.csv`) e cada tabela tinha **uma** linha. O §4.3 pede a conta "para cada fonte e lote": um ano das leituras que encolhesse, ou uma aba que sumisse do Excel, não apareceria em lugar nenhum | média | Uma linha por **origem**: 5 em `leituras` e 3 em `inspecoes`, com `_aba_origem` (D39). A Silver passou a **somar por `_tabela`** antes de comparar (§13.1b) — sem isso o confronto daria `DIVERGE` em toda leitura |
| R35 | **Localizador do registro** (item 2): `_id_registro` acha a linha **na tabela**, não no arquivo; o ADR de Bronze vigente naquela revisão já declarava isso como lacuna do DE-01 | média | Em 19/10, `_ordem_na_origem` apenas auxiliava a busca; em 20/10, o scanner passou a registrar ordinal e intervalo físico em CSV/JSON, e o leitor Excel guarda a linha da planilha (D40). Falta validar no Databricks |
| R36 | **Identidade do arquivo** (item 3): nada provava a **versão** do arquivo ingerido — o mesmo nome retificado na Landing entraria sem diferença visível | média | `bronze.arquivos_lote` com SHA-256, tamanho e modificação (D41); hash calculado no driver por streaming, com `status_hash` explícito quando não for possível |
| R37 | **Publicação por lote** (item 4): a versão revisada em 19/10 ainda sobrescrevia tabelas durante a leitura, então uma falha no fim podia expor lotes mistos | alta | A implementação de 20/10 grava no histórico e publica as vistas por atualização de um único ponteiro Delta (D42). Migração inicial, falha induzida e reexecução ainda precisam de evidência no Databricks |
| R38 | **Efeito colateral de R35 no perfilador:** o `AUDITORIA` do `Bronze_perfilamento.ipynb` não conhecia `_ordem_na_origem`; a coluna entraria como **dado** e, sendo única por arquivo, zeraria a duplicata exata — o mesmo falso negativo que `_id_registro` causava (D8) | alta | Coluna acrescentada ao `AUDITORIA` do perfilador (D43). Nenhum número do perfil muda: as três colunas de lote/posição seguem fora do cálculo |

| R39 | **A célula de dependência não executava** (achado na execução de 19/10): `%pip install openpyxl` estava numa célula **markdown** (a conversão `.py → .ipynb` tratou `# MAGIC %pip` como markdown), então nunca instalava nada. A carga parou na seção 6 com `ImportError: Missing optional dependency 'openpyxl'` — ambiente serverless sem o pacote | alta | Célula passou a ser **de código** (o conversor agora distingue `%md` de comando mágico) e a seção 6 traduz o `ImportError` do pandas numa mensagem que diz o que rodar. Nada muda no dado; muda o notebook abrir e executar |
| R40 | **A checagem de rastreio estourava em vez de reportar:** `f"faltando={faltando or 'nenhum':<18}"` aplica formato de texto a uma **lista** — funciona só no caso feliz (lista vazia → `'nenhum'`); com qualquer coluna faltando, o print levanta `TypeError` no meio da verificação e esconde justamente o problema que devia apontar | baixa | Faltantes e indevidos passam a ser unidos em texto antes do print. Sem efeito no dado: só o caminho de falha muda |

**Resposta do time à 5ª pendência (19/10/2026) — cascata de órfão (D38):** manter a **A** (a leitura só entra se o
medidor entrou na Silver), mas **não tratar a linha bloqueada como malformada**. As **58.214** leituras que apontam
para medidor existente na Bronze e removido na Silver passam a ter motivo próprio, ficam na Bronze com o registro
inteiro (origem + ordem) e podem ser reprocessadas quando a decisão da data ambígua (14.1) sair:

| # | Achado | Gravidade | Correção |
|---|---|---|---|
| R41 | **Cascata contada como defeito:** o motivo `medidor_inexistente` misturava dois fatos diferentes — 8.609 chaves que **não existem** na Bronze (erro de dado) e 58.214 leituras cujo medidor **existe** e caiu na quarentena (bloqueio). O confronto com o perfil aparecia como divergência (66.823 × 8.609) e o reprocessamento futuro não tinha como separar os dois | média | `uc_chk`/`med_chk` passam a levar o **status da chave** (`OK`/`QUARENTENA`); o motivo vira `uc_em_quarentena`/`medidor_em_quarentena`, e `*_inexistente` fica só para a chave ausente da Bronze. A validação continua contra a Silver; muda o **motivo**, não o destino (a linha já ia para a quarentena) |

Conclusão histórica da revisão de 19/10: os quatro itens eram de **rastreabilidade e momento da falha**; nenhum
tocava regra de negócio da Silver além do rastreio. A implementação Bronze foi revisada novamente em 20/10: D40
agora descreve o rastro físico por scanner, e D42 descreve o histórico com ponteiro único; as provas no Databricks
continuam pendentes. O R39 era um problema de **execução** encontrado em runtime. O R41 trata da semântica do motivo
de cascata na Silver e não muda o destino da linha.

**Pendências que continuam abertas:** data ambígua (D36) e os achados que não rejeitam / `inspetor` (D37) — as duas
dependentes de resposta do time. A cascata de órfão (D38) foi **decidida e implementada** (R41).

**Revisão final sobre os dados reais (19/10/2026)** — depois de a Silver rodar sem erro no Databricks, a leitura foi
feita **contra os arquivos brutos**, não contra o perfil: contagens independentes de datas, duplicatas, órfãos,
formatos e textos, com as funções reais da Silver. O que o perfil não media apareceu aqui:

| # | Achado | Gravidade | Correção |
|---|---|---|---|
| R42 | `uf` com **5 grafias** cruas do mesmo estado (`PE` 39.470, `pe` 1.826, `pernambuco` 1.729, `P.E.` 1.726, `Pernambuco` 1.709) passava pela carga como 5 valores — a seção 5.2 já dizia "UF padronizada" | média | `uf` mapeada para o **código de 2 letras** (27 UFs, sem acento/pontuação), com fallback para o texto limpo (D44) |
| R43 | `cep = "-1"` (162 linhas) virava `"1"`: a regra "só os dígitos" não exigia comprimento, e um CEP de 1 dígito é pior que nulo | média | `cep` só é publicado com **8 dígitos**; sentinela/placeholder → nulo (D44) |
| R44 | `logradouro` saía cru: **2.797** com espaço nas pontas e **1.551** com espaço duplo (`numero` idem, sem caso na amostra); eram **1.557** grafias para 217 ruas | baixa | `texto()` em `logradouro`/`numero`/`nome_titular` (apara e colapsa; a caixa do nome e do endereço é preservada) |
| R45 | A conferência "grafia divergente remanescente" era **tautológica**: agrupava `lower(trim(collapse(bruto)))` e contava `distinct(bruto)` **sobre a coluna já normalizada** — o valor da Silver já é maiúsculo/sem acento/sem espaço duplo, então dava sempre 0 e não pegava a UF | média | O bloco passa a mostrar o **colapso bruto → Silver** nas 5 colunas que o perfil mediu e a exigir o **domínio fechado** (UF nos 27 códigos; resultado com 2 valores) |
| R46 | `sequencia.cast("int")` era o único cast sem `try_`: um valor fora de faixa derrubaria a célula sob ANSI em vez de virar nulo | baixa | `try_cast` (mesma regra de datas e números) |
| R47 | §13.1c usava `max(_lote_id)` de `arquivos_lote` — o lote **tentado**, não necessariamente o **publicado**; uma tentativa que falhou antes de publicar mostraria os arquivos errados | baixa | Usa o último `PUBLICADO` de `controle_lote` (fallback para `arquivos_lote` se a tabela de controle não existir) |
| R48 | `tipo` de medidor saía com **5** valores (10 grafias cruas) para **3** tipos: `ELETRO-MECANICO`/`ELETROMECANICO` (hífen) e `SMART`/`SMART METER` (nome em inglês) não eram colapsados pela normalização cosmética, e a conferência não olhava o domínio | média | Mapa canônico no `tipo` e **domínio fechado** de 3 valores na §13.6 (D45) |

Números que sustentam os ajustes (medidos nos brutos, com as funções reais da Silver): leituras com data ambígua
**102.878**; `faturas.data_emissao` **61.226**; `medidores.data_instalacao` **1.381** (1.369 chaves + 12 cópias
exatas); `inspecoes.data` **45**; `UC.data_ligacao` **1** (cabeçalho). Duplicatas: leituras **21.523** exatas,
medidores **513**, faturas **1** (par de cabeçalhos), UC **1.256** chaves (1.260 linhas; 900 exatas, 360 não
exatas). Órfãos independentes: faturas **32.285**, leituras **8.609** (8.569 medidores), zero de UC em
leituras/medidores/GD/ocorrências. Cascata: **1.369** medidores ambíguos → **58.214** leituras bloqueadas; as **2**
faturas `uc_em_quarentena` são as linhas de cabeçalho de `faturas`, não cadastros reais.

Conclusão: os ajustes mudam **valor publicado** (R42–R44, R48), **verificação** (R45), **robustez** (R46) e **leitura
da prova** (R47); nenhum muda a chave, o grão ou o destino de linha. O hash do código da Silver passa a
`07a103e22251bf45`. O que continua **sem correção, por decisão**: `nome_titular` preserva a caixa (359 grupos com
mais de uma grafia de caixa/acento; a identidade é o `cpf_cnpj`), `mes_referencia` nulo não é rejeitado (não há nulo
no arquivo; o perfil mede o formato) e a Silver não é atômica **entre tabelas** (cada `saveAsTable` é atômico; uma
falha no meio deixa tabelas de versões diferentes — visível na §13 e reparável por reexecução).

### 11.2 Estado da revisão por lote (21/10/2026)

A revisão local desta etapa não é evidência de aceite de DE-02/DE-03. A única execução real disponível está em §11.3 e
corresponde à versão anterior; a versão atual aguarda execução no lote autorizado.

### 11.3 Execução no Databricks Free Edition (21/10/2026)

Dataset real no Volume autorizado, compute serverless, notebooks importados à mão (o Workflow ainda não inclui a Silver).

- **Bronze** (`Landing_to_Bronze` com o `cast("long")` de `_ordem_na_origem` na migração): lote `20261021T095426Z_106436a4`
  publicado, 10 fontes, 4.969.149 linhas, migrando as tabelas da Bronze anterior (`_ordem_na_origem` era `int`). Sem o
  cast, a migração falharia como em §11.2. 14 origens com `delta = 0` e 0 rejeitados no parse.
- **Perfil** (`Bronze_perfilamento`): `quality.perfil_bronze` com 108 linhas para o mesmo lote.
- **Silver**: run `20261021T101818Z_223235ca`, `CONCLUIDO`, 0 falhas, ≈ 7 min 45 s. Entrada → aceitos + quarentena:
  UCs 46.461 → 45.200 + 1.261; medidores 51.812 → 49.930 + 1.882; leituras 2.182.468 → 1.981.032 + 201.436;
  faturas 2.184.623 → 2.091.968 + 92.655; GD 3.510, ocorrências 180.000 e atendimentos 318.871 sem quarentena;
  inspeções 1.389 → 1.344 + 45; `atendimentos_historico` 636.857 tratativas. Soma de controle com `delta = 0,00`:
  faturas: total financeiro reconciliado entre aceitos e quarentena; montantes preservados no ambiente autorizado.
- **Bate com o perfil de 17/10** (somando as combinações de motivos): leituras com data ambígua 102.878, medidor
  inexistente 8.609, cascata `medidor_em_quarentena` 58.214; faturas com emissão ambígua 61.226, UC inexistente 32.285.
- **Consumo negativo:** 7.592 leituras somam −366,7 milhões de kWh (≈ −48 mil kWh por leitura). Por isso a soma bruta
  de `consumo_kwh` na Bronze (509,2 milhões) é **menor** que a aceita (813,3 milhões). Não somar consumo direto da Bronze.
- **Quarentena por data ambígua:** faturas com impacto financeiro registrado no ambiente autorizado só por esse motivo (60.368 linhas) e leituras 39,7 milhões
  de kWh (98.168 linhas). D52 é diagnóstico exploratório; a política vigente mantém B + C e não autoriza recuperar essas datas antes da análise por arquivo.

**Próximas verificações:** executar perfil e Silver revisados no lote autorizado, analisar os contadores de formato por arquivo, confirmar no contexto de produto se `inspetor` é exibido e encadear a Silver no Workflow. Instalação ambígua e datas ambíguas continuam segregadas pela política A/B enquanto a análise não justificar outra regra.

### 11.4 Revisão posterior ao run de 21/10/2026

O run de §11.3 valida somente a revisão anterior, não D53–D60. Nesta revisão, datas ambíguas permanecem em quarentena e a seção 13.6 mede evidências por arquivo, inclusive a compatibilidade das datas inequívocas com a competência; medidores com instalação ambígua e suas leituras ficam bloqueados pela cascata A; conflitos cadastrais não são resolvidos por completude; data futura ou sentinela não comprova quitação. A confirmação no Databricks exige executar perfil e Silver no mesmo lote, revisar os resultados por arquivo e reconciliar contagens e somas; o significado de `9999-12-31` não é presumido.

## 12. Referências

- [PRD](../docs/PRD.md) — IDs DE-01 a DE-09; §4 (regras de tratamento, perfil, reconciliação), §5 (arquitetura), §6.1.
- [Índice de decisões arquiteturais de outros módulos](../docs/decisions/README.md).
- [Serviço: engenharia de dados](../docs/services/data-engineering.md) — contrato por camada e invariantes.
- [Dicionário de dados Gold](../docs/dicionario_gold.md) — a preencher em DE-08.
- [Workflow de desenvolvimento e qualidade](../docs/agents/workflow.md).
- Notebooks (`data-engineering/notebook/`): `Landing_to_Bronze.ipynb` (reconciliação por origem, `_ordem_na_origem`,
  `bronze.arquivos_lote` e publicação por lote — R34–R37), `Bronze_perfilamento.ipynb` (R38) e
  `Bronze_to_Silver.ipynb` (a versão R30/R31 rodou e passou nos invariantes; a versão R34–R38 aguarda nova
  execução).
- Job: `data-engineering/configuracao/databricks/v-energy-grid-360.yaml`.
