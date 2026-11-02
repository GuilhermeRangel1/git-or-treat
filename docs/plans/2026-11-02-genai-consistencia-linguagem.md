# Consistência de linguagem do Assistente Gold v2 — 02/11/2026

## Escopo e caminho executado

IA-01, IA-02 e IA-06; continuação da branch `fix/genai-prontidao-gold-local`, sobre `e565d2c`. Correções pequenas no interpretador, calendário e perfil existentes. O contrato físico continua `gold-csv-v2`, catálogo `gold-catalog-v2`, schema `gold_v2` e fonte `gold.local`. Não há novos indicadores ou permissões.

Caminho: sessão individual no Backend → publicação/metadados → planejamento HTTP do núcleo Gold → prontidão/SQL restrito → revalidação e síntese no núcleo → fundamentação/auditoria → resposta pública. A normalização atua na pergunta e nas falas da pessoa usuária; não reescreve mensagens do Assistente. A autorização e os controles atuais continuam sendo conferidos pelo servidor.

## Problemas reproduzidos e correções

| Situação | Comportamento corrigido |
| --- | --- |
| `marco`, `ate`, `janeiro com março de 2025` | Aceita as grafias equivalentes e o ano compartilhado explícito. |
| `03/2025`, `março/2025`, `no mês de março de 2025`, `na competência março de 2025` | Reconhece a competência completa sem confundi-la com lugar ou recorte diário. |
| `janeiro a março de 2025`, `variação de janeiro para março de 2025`, comparação com `versus` | Preserva a diferença entre intervalo e par de meses comparados. |
| Espaços repetidos, tabulação, quebra de linha e acentos Unicode decompostos | Conserva indicador e valores de filtro reconhecidos. |
| `classe de consumo residencial` em pergunta sobre receita | O termo `consumo` dentro do rótulo do filtro não cria uma segunda métrica. Um pedido explícito de receita **e** consumo continua exigindo esclarecimento. |
| `Qual foi o município com maior receita?`, `Em qual município...`, `receita por classe de consumo` | Usa os agrupamentos já declarados no perfil. Valores desconhecidos e múltiplas aberturas não são apagados para consultar o total. |
| `bairro X de Y`, quando Y existe como bairro e município | O valor de bairro reconhecido e o qualificador explícito identificam Y como dimensão pai, conforme o catálogo. Y sozinho continua ambíguo; a relação do recorte continua sendo conferida pela fonte. |
| `sem ser residencial`, `excluindo Olinda`, `fora do município de Olinda` | Pede esclarecimento em vez de inverter exclusão em inclusão. O valor categórico autorizado `sem GD` permanece válido. |
| `receita arrecadada`, `faturamento recebido/pago` | Não substitui arrecadação por faturamento; conserva recorte e período se a pessoa confirmar receita faturada. |
| Limites não representados, como `superior a 1000`, `igual a 1000`, `>=1000` | Pede esclarecimento em vez de ignorar a restrição e responder o total. A métrica específica aprovada de GD com queda superior a 30% continua reconhecida. |
| `Em março de 2025?` após uma consulta | Conserva indicador e filtros anteriores. Sem contexto da pessoa usuária não inventa indicador. |
| `E o consumo?` após comparar receita | Conserva ambos os meses quando o novo indicador admite comparação; uma abertura anterior não é silenciosamente descartada na troca de indicador. |
| Intervalo com extremo malformado ou pergunta de perda sem base de comparação | Não reduz a consulta ao único mês válido nem transforma perda de receita em menor receita mensal. |

## Verificações controladas

- `ai-agent/tests/test_gold_language_http.py`: 65 casos de regressão, incluindo planejamento → revalidação → síntese com evidência artificial e modelo controlado. As falhas de comportamento foram reproduzidas antes das correções; casos adicionais preservam os bloqueios. Somado aos testes existentes de planejamento/filtros/calendário, o recorte dirigido passou com 192 testes.
- Suíte completa final: **4160 passaram, 5 skips**, em 70,95 s. Execução a partir de diretório sem `.env`, com `PYTHONPATH` apontando para `ai-agent`, plugins automáticos desligados e `-p anyio`. Comando: `python -m pytest -c <ai-agent>/pyproject.toml --rootdir <ai-agent> <ai-agent>/tests -q -p anyio --tb=short -rs --junitxml=<work>/pytest-language-final.xml`.
- Skips: smoke Groq real opt-in, três testes PostgreSQL sem DSNs de teste e criação de link simbólico indisponível no Windows. Não são falhas convertidas em aprovação.
- `python -m ruff check .` em `ai-agent/` e `git diff --check`: passaram.
- Varredura exploratória privada: 135 variações de caixa, espaço, Unicode, datas, sinônimos, filtros, acompanhamento e impedimentos, sem divergências frente aos planos/estados esperados. É prova artificial suplementar; não acrescenta casos aprovados à matriz Gold oficial.

## Rodada real autorizada

Serviços Docker existentes iniciados sem nova carga ou alteração do banco; serviço GenAI reconstruído com as correções. Gemini real `gemini-3.5-flash-lite`, cache de modelo desativado; nenhuma chave foi registrada. Sessões e contas de teste são temporárias e removidas no `finally` dos harnesses privados.

Matriz oficial, execução `20261102T100421_528580Z`: **42 PASS, 1 FAIL, 5 BLOQUEADO, 7 SEM_AMOSTRA_NO_LOTE, 2 NAO_EXECUTADO**. A falha foi CON-01, HTTP 504 por prazo global de 35 s; não foi divergência numérica. A auditoria mostrou preparação até cerca de 19,6 s e término da chamada de modelo por volta do limite restante de 15,4 s. O resultado original foi preservado em `work/genai-local-validation/20261102T100421_528580Z/`.

Medição privada do observador: 19,531 s no lote local, sendo 7,584 s em `_monthly_groups`; a passagem de cobertura por recorte consumiu 0,217 s. A medição não justifica remover reconciliação, aumentar prazo ou introduzir cache entre consultas. Não houve alteração nessas políticas.

### Variações reais da linguagem

Execução `language-20261102T100820_527167Z`: **17 PASS e 1 FAIL** em 18 variações. L04 revelou a colisão entre nomes de bairro e município; foi reproduzida com dados artificiais e corrigida pela relação de dimensão pai já declarada. O esclarecimento sem qualificador foi preservado. Reteste `language-20261102T101723_909516Z`: **L04 PASS**, resposta numérica em 21,82 s, reconciliada pelo controle de FAT-04. A primeira falha permanece registrada; o resultado mais recente de cada uma das 18 variações é PASS.

| IDs locais | Base e controle independente | Variação conferida | Estado esperado observado |
| --- | --- | --- | --- |
| L01–L03 | FAT-01 / C04 | Mês/ano numérico, prefixo mês, prefixo competência | answered |
| L04 | FAT-04 / CTL-FAT-BAIRRO | Classe de consumo e relação bairro → município | answered após correção |
| L05 | FAT-06 / CTL-FAT-TARIFA | Espaços repetidos no nome do indicador | answered |
| L06–L07 | AMB-05 / CTL-FAT-MUN-CLASSE | Acompanhamento somente com período, preservando classe/município | answered |
| L08 | CON-06 / CTL-CON-COMPARACAO | Troca para consumo preservando os dois meses comparados | answered |
| L09–L10 | FAT-01 / C04 e amostra do município de maior receita | Duas formas de perguntar o maior município; sem filtro municipal indevido | answered |
| L11–L18 | AMB-03 / estado sem valor | Limite numérico, exclusões, arrecadação, data inválida e perda sem base | needs_clarification |

Verificação independente da trilha das 18 variações: **10 respostas com chamada de modelo concluída e 8 esclarecimentos sem etapas de modelo ou executor quantitativo**. Contagem de contas temporárias `language-*`/`matrix-*` remanescentes: zero. Relatórios privados preservados em `work/genai-local-validation/`; não integram o Git.

Rechecagem isolada de CON-01: execução `20261102T101912_392670Z`, **PASS**, HTTP 200 `answered` em 22,04 s, com o mesmo prazo e controle SQL. Essa rechecagem não substitui o registro da matriz completa e não comprova eliminação do risco de timeout. Não houve mudança no prazo, nas reconciliações de prontidão ou nas políticas de cache.

Para reproduzir a matriz oficial, use `python scripts/run_gold_domain_scenarios.py --output-dir ../work/genai-local-validation` em `ai-agent/`, com a configuração privada descrita no runner. O reteste isolado usa `--ids CON-01`. As variações são transformações dos casos e controles da tabela acima, executadas pelo harness privado `work/genai-assistente-cleanup/run_language_real.py`; elas não alteram os 57 casos oficiais nem seus critérios de aprovação.

## Limites

Os estados oficiais do PRD não mudam. Arrecadação não disponível, cobertura mensal não certificada e recortes sem amostra continuam limitando a matriz. Uma forma não reconhecida, como abreviação de mês não suportada, pode continuar pedindo esclarecimento. Testes e variações adicionais não homologam os domínios nem garantem disponibilidade ou latência do provedor externo.
