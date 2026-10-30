# Controle de cobertura mensal da Gold

Atende à preparação produtora de DEV13.1 D02/D09, DEV13.2 C01 e às dependências de períodos da GenAI. Implementação em [Silver_to_gold](../../data-engineering/notebook/Silver_to_gold.ipynb); a tabela `cobertura_dominios` integra o pacote [gold-csv-v2](gold-csv-v2.md). `gold-cobertura-v1` é a versão das declarações de cobertura, não outra versão do pacote CSV.

## Grão e observação

Chave: `(dominio, competencia, recorte)`. Domínios: `consumo`, `faturamento`, `atendimentos`, `ocorrencias`, `medidores` e `gd`. Cada competência da janela tem linha para cada domínio, mesmo sem registros. Para ocorrências há também uma linha por alimentador do cadastro atual, com `recorte=ALIMENTADOR:<id>`; o total usa `DOMINIO`. Não somar os dois níveis.

As contagens usam exclusivamente a Silver publicada e fixada pelo notebook, excluindo UCs nulas/de teste e respeitando a elegibilidade das ocorrências. Competência vem de `mes_referencia` para leituras/faturas, abertura para chamados/ocorrências, instalação para medidores e conexão para GD. Flags de futuro/sentinela impedem atribuir datas inválidas; registros sem competência utilizável são contados separadamente.

**`qtd_registros` conta observações do snapshot completo, até a referência do notebook. Não é uma contagem filtrada pela data da declaração.** `data_corte_evidencia` informa o corte certificado pela evidência externa; `data_processamento_gold` registra a referência usada nas observações. Uma declaração parcial anterior à extração pode coexistir com registros posteriores ao seu corte: o consumidor não deve apresentar a contagem como um total naquela data. Consulta com corte intramensal exige os fatos datados, não este contador mensal.

## Estados e ausência

| Estado | Significado |
| --- | --- |
| `NAO_CERTIFICADA` | Não há declaração válida para aquele mês/recorte. Presença ou ausência de linhas não certifica completude. |
| `FECHADO` | Declaração vinculada ao lote e com corte posterior ao término de todas as competências declaradas. Não é deduzido de contagens. |
| `PARCIAL` | Evidência declara cobertura parcial. Não libera comparação que exige mês completo. |
| `AUSENTE` | Evidência declara ausência de cobertura e o snapshot não contém registros naquele recorte/mês. Não significa zero de eventos confirmado. |

`zero_registros_confirmado=true` exige `FECHADO` e contagem zero. É confirmação de **zero registros**, não preenchimento automático de consumo, receita ou duração nulos. Nenhum outro estado autoriza substituir ausência por zero.

Medidores e GD representam cadastros atuais: datas de instalação/conexão não provam uma população histórica mensal. Por isso esses domínios não aceitam `FECHADO` histórico. A tabela explicita essa limitação por `natureza_temporal`, sem inventar vigência.

Declarações contraditórias entre total e alimentador são recusadas: domínio fechado não pode ter alimentador explicitamente parcial/ausente; domínio ausente não pode ter alimentador explicitamente fechado/parcial. Não há propagação automática do estado global aos alimentadores sem declaração própria. Nenhum fechamento é aceito quando há registros sem competência utilizável no respectivo domínio/recorte.

## Configuração do notebook

- `COBERTURA_INICIO` e `COBERTURA_FIM`: janela esperada em `YYYY-MM`, informados juntos, até 240 meses e sem meses posteriores à referência. Permitem representar lacunas também nas extremidades.
- Se ambos estiverem vazios, usar os limites observados de consumo, faturamento, chamados e ocorrências, com `origem_janela=LIMITES_OBSERVADOS_NAO_CERTIFICADOS`. Isso não comprova que os limites do dataset são completos. Sem fatos datados, a janela precisa ser explícita.
- `COBERTURA_DECLARACOES_JSON`: opcional. Vazio gera cobertura observada não certificada. Limites: 64 KiB e 500 declarações por intervalo, sem sobreposição de chave.

O envelope contém exatamente `schema_version=gold-cobertura-v1`, `run_id_silver`, `lote_bronze_silver` e `declaracoes`. A identidade deve coincidir com a origem fixada. Cada declaração contém exatamente:

| Campo | Regra |
| --- | --- |
| `dominio`, `recorte` | Valores de domínio/recorte publicados; recorte por alimentador somente para ocorrências. |
| `inicio`, `fim` | Competências inclusivas, ordenadas e dentro da janela do controle. |
| `estado` | `FECHADO`, `PARCIAL` ou `AUSENTE`. |
| `data_corte` | ISO com offset; não posterior à referência da extração. Para `FECHADO`, ao menos o início do mês seguinte ao último mês declarado. |
| `referencia_evidencia` | Identificador opaco não vazio de até 256 caracteres; sem texto livre, dados pessoais ou segredo. |

As declarações são fornecidas pelo operador responsável com base em evidência de origem conferida. Identidade, formato e coerência são validados pelo código; preencher o JSON não produz aprovação externa nem prova, sozinho, a completude do fornecedor. Nunca utilizar saída de modelo ou texto do dataset como declaração de fechamento.

## Consumo por Backend e GenAI

Carregar o controle no mesmo lote das demais tabelas, preservando tipos, chave e contagem do manifesto. O Backend mapeia a cobertura física ao contrato temporal existente; a GenAI não recebe acesso à Silver nem ao cadastro pessoal por causa desta tabela.

Janelas que exigem meses completos só podem ser liberadas com todos os meses e recortes necessários certificados, além dos controles de qualidade da métrica. O primeiro/último mês observado não é automaticamente fechado; a interpretação de “último ano” e “ano passado” continua pertencendo ao contrato de linguagem aprovado. Não somar populações cadastrais, médias ou razões para fabricar histórico.

O [dicionário Gold](../dicionario_gold.md) define os campos físicos. A implementação e os cenários sintéticos preparam o controle; a certificação do lote e a integração com os consumidores precisam de evidência na execução autorizada.
