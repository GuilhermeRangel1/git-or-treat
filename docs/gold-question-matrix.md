# Matriz de perguntas Gold

**Cartão:** GENAI-04, parte 04a (vocabulário, filtros e períodos das perguntas reais). **Matriz:** `ai-agent/tests/fixtures/gold_question_matrix.json` (`gold-question-matrix-v1`). **Teste:** `ai-agent/tests/test_gold_question_matrix.py`. **Perfil:** `GRID360_GOLD_PROFILE` ([catálogo Gold](gold-catalog.md)).

**Natureza:** preparação. A matriz só tem perguntas sintéticas escritas à mão, sem valores, contagens nem nomes de lugar do lote. Os únicos municípios citados são os três do case. Status, domínio, métrica, período e filtros esperados vêm do case (PRD §7.6), do [dicionário Gold](dicionario_gold.md) e do catálogo, não da saída do código. Os trechos de mensagem esperados acompanham o texto atual do perfil e só conferem que o esclarecimento certo foi dado.

## Como o teste lê a matriz

Cada caso passa pela composição pública do núcleo (`compose_core`): pergunta, intenção, plano aprovado e fonte. A fonte é um espião que só captura o plano e responde sem evidência.

- **`ready`:** um plano chega à fonte, e o teste confere domínio, métrica, período, filtros (município, classe, GD e alimentador), dimensões e ausência de agrupamento. Também confere que o mapeamento físico tem uma fonte única para esse recorte, com a capacidade da prontidão indicada no caso.
- **`needs_clarification`:** nenhum plano chega à fonte, e a mensagem contém os trechos esperados. Nesses casos, domínio e período são só descritivos.
- **`known_gap`:** o esperado continua sendo o correto, e o caso é marcado `xfail(strict=True)`. Se a lacuna for corrigida, o caso passa, o xfail estrito vira falha e `known_gap` precisa ser removido. Um teste separado confere que cada lacuna mantém o estado atual registrado, para que ela não mude de forma em silêncio.

## Grupos de casos

| Grupo | Casos | `ready` | `needs_clarification` | O que cobre |
| --- | --- | --- | --- | --- |
| Perguntas do case (§7.6) | 3 | 0 | 3 | UCs com solar e queda de consumo (capacidade indisponível); bairro que mais perdeu volume (ranking); quanto cresceu a receita (comparação sem período) |
| Métrica com filtros | 8 | 8 | 0 | Receita, consumo, ticket médio, consumo médio por UC e tarifa efetiva, com município e classe |
| Sinônimos e grafia | 4 | 2 | 2 | "valor faturado" em caixa alta, "energia consumida" sem acento, "conta de luz" e "falta de luz" |
| Médias | 2 | 0 | 2 | "média do consumo" continua pedindo o total; "consumo por UC" continua sendo quebra |
| Geografia | 3 | 1 | 2 | Dois municípios, local desconhecido, correção na mesma frase |
| Classificação | 5 | 3 | 2 | GD Sim e Não, classe desconhecida, classe e GD juntas |
| Rede (DEC/FEC) | 3 | 0 | 3 | DEC sem alimentador, DEC por município, FEC de um alimentador |
| Quebra por dimensão | 4 | 0 | 4 | Por bairro, por bandeira, por subgrupo; "ticket médio por bairro" continua sendo quebra |
| Recorte sem suporte | 2 | 0 | 2 | Bairro nomeado, "energia solar" |
| Período | 3 | 1 | 2 | Mês isolado, ano corrente parcial, crescimento sobre base zero |
| Unidade | 1 | 0 | 1 | Consumo em reais |
| Capacidade indisponível | 7 | 0 | 7 | Um caso por grupo: faturas em aberto, atendimento, medidor, energia a recuperar, preço × volume, variação de consumo por UC, fila de inspeção |
| Contexto | 6 | 4 | 2 | Follow-up que herda métrica, classe, período ou ticket médio; correção na mensagem seguinte; histórico que tenta liberar capacidade indisponível |
| **Total** | **51** | **19** | **32** | |

Dos 51 casos, 3 são `known_gap`: `residential_with_gd` (esperado `ready`), `unknown_class_after_class_word` e `dec_without_feeder` (esperados `needs_clarification`).

## O que ainda não é suportado e por quê

Estas perguntas terminam em esclarecimento por limite do interpretador ou do plano, nunca em resposta com recorte errado:

- **Ranking e comparação entre recortes:** "qual bairro mais perdeu", "qual município teve a maior receita". O plano não tem agrupamento nem ordenação preenchidos pelo interpretador.
- **Crescimento e variação entre períodos:** "quanto cresceu" sem período pede o período; com um período, pede a base; com dois, o plano é recusado por não ter janela aprovada.
- **Quebra por dimensão:** "por bairro", "por bandeira", "por subgrupo", "por município", "por UC". A mensagem diz que o resultado ainda não é separado.
- **Bairro, bandeira, subgrupo, alimentador e UC nomeados:** o catálogo não tem a lista desses valores, que vêm do lote. Antes desta parte, o nome era ignorado e a resposta vinha sem o filtro.
- **"Solar":** o dicionário diz que GD é presença de cadastro, sem o tipo de fonte. O perfil não trata "solar" como GD.
- **Capacidades indisponíveis:** a mensagem diz que o dado ainda não está disponível na Gold carregada e oferece receita, consumo ou DEC/FEC.

Lacunas conhecidas (`known_gap`):

- **DEC/FEC sem alimentador** (`dec_without_feeder`): o mapeamento exige alimentador, mas o perfil lógico não declara dimensão obrigatória. Por isso, o plano chega à fonte, e só o executor recusaria. Fazer o núcleo pedir esclarecimento muda dois testes do GENAI-03 (`test_gold_catalog.py`), que hoje esperam o plano aprovado; a decisão fica em aberto.
- **Classe desconhecida depois da palavra "classe"** (`unknown_class_after_class_word`): o interpretador não detecta um valor desconhecido nessa posição e responde sem o filtro. Classes reais fora do perfil ("iluminação pública", "serviço público", "consumo próprio") já pedem esclarecimento.
- **Classe e GD juntas** (`residential_with_gd`): a intenção carrega um único filtro de classificação, por isso o núcleo pergunta "qual classe". Não amplia o recorte, mas a mensagem é imprecisa.

Fora da matriz, também fica pendente "receita em 2025": o ano isolado é lido como local desconhecido. O catálogo de períodos em tempo de execução é da parte 04b.

## O que depende da parte 04b e do executor

- **Parte 04b:** catálogo de períodos em tempo de execução, com mês e ano isolados ("agosto de 2025", "em 2025") e resolução das frases relativas contra as competências do lote.
- **Executor do Backend:** janela concreta, parcialidade do ano corrente, escolha da fonte física (`select_source`) e recusa de DEC/FEC sem alimentador ou entre meses.
- **Liberação para consulta real:** depende de GENAI-06, GENAI-07 e GENAI-10.

## Premissa a confirmar com Dados

- **Grafia de `municipio`:** o dicionário não fixa a grafia dos municípios. O perfil usa maiúsculas, com acento preservado (ex.: `JABOATÃO DOS GUARARAPES`; também `RECIFE` e `OLINDA`), e reconhece os nomes com ou sem acento e em qualquer caixa. A grafia foi conferida localmente contra o lote de 28/10, fora do repositório; Dados ainda deve confirmar que essa é a convenção da Gold.
- **Conferência local:** `python scripts/check_gold_dimension_values.py <diretório do lote>`, executado em `ai-agent/`, confere cada valor declarado (municípios, classes e Sim/Não de GD) nas colunas que o mapeamento lê. Imprime só o valor declarado, a tabela e coluna e `PASS exato`, `PASS normalizado` ou `FAIL`. `PASS normalizado` significa que a grafia do lote difere da declarada e que um filtro por igualdade não a encontraria. A conferência do lote de 28/10 foi feita localmente com este script, fora do repositório, e a saída não é versionada.
