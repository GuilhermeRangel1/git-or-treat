# Memória para conversas mais longas — 03/11/2026

Branch `feat/genai-memoria-conversas-longas`, base develop `36166bd` (PR #112).
Cartão [Memória para conversas mais longas](https://trello.com/c/Wen9zrG0).
Entrega técnica local concluída nos dez critérios: integração executável com prova
Gold v2; sem commit/push nesta etapa, integração à develop pendente de PR/merge.
Extensão opcional de IA-07; não muda os estados oficiais IA-01 a IA-07 nem certifica
cobertura de Dados. Contrato: [memória](../contracts/genai-long-conversation-memory.md).

## Problema, comparação e escolha

A continuidade existente já conserva o plano atual, inclusive depois de muitos
turnos. A perda observada é outra: uma pergunta completa sobre um novo assunto
substitui a âncora; a janela recente não consegue retomar expressamente a primeira
consulta de uma investigação anterior.

Conjunto controlado de quatro casos, definido com métrica, classe, município e
competência esperados: receita residencial/Recife/janeiro, consumo comercial/Olinda/
fevereiro, receita comercial/Recife/março e consumo residencial/Recife/janeiro,
todos em 2025 e sob o mesmo catálogo/escopo/cobertura artificiais. Após uma pergunta
de consumo em Olinda/março, “Retome a primeira consulta” pediu esclarecimento nos
**4/4** casos com contexto curto. Recuperando a intenção original, o núcleo composto
gerou **4/4** planos integralmente corretos: métrica, unidade, classe, município,
extremos do mês, ausência de comparação/grupo/ordenação e limite. Uma quinta prova
conferiu a correção para comercial sem recuperar o município do assunto recente.

Meta desta fatia: resolver as quatro retomadas explícitas e conservar os campos
independentes esperados, sem regressão de isolamento/invalidação. Não é uma taxa
geral de entendimento e não prova perguntas livres sobre qualquer mensagem antiga.

Escolha: recuperação ordenada das âncoras existentes, em vez de resumo por LLM.
Ganho demonstrado no comportamento; nenhuma segunda cópia do histórico, novo
executor, índice vetorial ou chamada externa para sumarizar. A seleção tipada
ocorre no Backend; o núcleo e os consumidores existentes continuam em uso.

## Verificações locais

Executadas em cópias temporárias Linux, isoladas das variáveis privadas nos testes:

```text
# Backend
python -m pytest -q tests/test_conversation_memory.py tests/test_conversation_memory_http.py tests/test_ai_history_store.py tests/test_ai_history_http.py tests/test_ai_conversations_contract.py tests/test_genai_continuation.py tests/test_genai_invalidation.py --tb=short
# AI Agent
python -m pytest -q tests/test_long_memory_replanning.py tests/test_gold_follow_up_http.py tests/test_gold_receptivity.py --tb=short
```

**84 testes Backend e 76 do núcleo passaram**, sem skips. Aviso preexistente de
depreciação Starlette/httpx no Backend. Cobrem ordem e proveniência após 20 trocas,
correção e mudança de tema, intenção sem resposta antiga, fonte ausente/corrompida,
versão/publicação inválidas, alteração de escopo sem renumeração, outra pessoa,
expiração/exclusão, envio HTTP real, complemento não confiável e desativação.

Os testes HTTP de transporte usam coordenador controlado; os testes do núcleo usam
perfil/composição reais e fonte de planejamento controlada. A prova abaixo cobre
a execução SQL e o provedor reais. Testes não são usados como homologação de Dados.

Tentativas iniciais encontraram uma forma de frase não reconhecida (“consulta
anterior”) e falta de importação de fixture; corrigidas antes da regressão final.
O runner HTTP/threads no Windows ficou sem saída e foi interrompido; foi usada
execução Linux, sem contar a tentativa Windows como aprovação.

## API, PostgreSQL e Gemini reais

Prontidão local: configuração, banco, leitor, publicação, catálogo, auditoria e
GenAI `ready`; geração `configured`. Dois processos temporários nas portas internas
18016/18017 dentro dos containers existentes, código da branch, sem novos containers
ou alterações no portal principal. Credenciais herdadas do ambiente privado, não
copiadas para a branch ou relatórios.

Conta temporária com `orders:read`, login e conversa privados reais:

1. Receita faturada residencial em Recife/junho de 2026: 200/answered.
2. Nova pergunta completa de consumo em Olinda/junho: 200/answered.
3. Doze perguntas conceituais sobre DEC: 200/needs_clarification, sem inventar
   indicador numérico ou criar âncoras de execução.
4. Detalhe da conversa carregado novamente; “Retome a primeira consulta”:
   200/answered, mesmo recorte estruturado da primeira resposta.

As 15 respostas tiveram referência de auditoria. A primeira receita e sua retomada
foram reconciliadas com `SUM(receita_total_reais)` independente em
`gold_v2.diagnostico_receita`, competência/município/classe fixados separadamente,
transação READ ONLY e prazo de 5 s. Precisão decimal monetária de duas casas.
A etapa de consumo demonstrou a troca de assunto; não é uma segunda certificação
numérica desta prova. Nenhuma linha bruta ou dado pessoal enviado ao modelo.

Prova adicional: referência canônica de outra publicação → **409** sem resposta;
revogação do acesso da conta → **403**; complemento pedindo para ignorar regras e
apagar tabelas → **refused/security_violation** com auditoria. Excluir a conversa
pela API → 204, consulta posterior → 404. Contas, sessões e conversas temporárias
removidas em `finally`; processos temporários encerrados ao fim.

Uma tentativa com referência deliberadamente malformada encontrou erro no parser
de publicação a jusante. A memória passou a validar a referência canônica v2 antes
da assinatura/coordenação; três casos inválidos/v1 agora são bloqueados no teste
dirigido. A repetição com referência antiga **válida** confirmou o 409 esperado.
Essa tentativa não é registrada como sucesso.

## Tokens, custo e tempo observados

A memória não chama um modelo para seleção ou resumo. Na primeira jornada, cada
resposta numérica usou uma chamada Gemini: pergunta original 1.488 tokens de entrada
e 29 de saída; mudança de assunto 1.496/29; retomada 1.531/29. A retomada consumiu
43 tokens de entrada a mais que a primeira pergunta, sem enviar o histórico inteiro.
São contadores de uso do provedor, não estimativas de texto. Nenhum preço monetário
foi inferido e não se declara redução do custo total de uma resposta: responder a
uma retomada exige a síntese normal, enquanto o baseline apenas esclarecia.

Tempos da jornada: receita 18,237 s; consumo 14,751 s; retomada 14,816 s.
Doze esclarecimentos: 0,631–0,753 s. A rodada final dos controles respondeu à
receita em 14,974 s e recusou a injeção em 0,597 s. Variação de modelo/cache impede
atribuir esses tempos à recuperação; não são SLO nem benchmark concorrente.
Incluindo a tentativa inválida, houve cinco chamadas de geração nesta validação,
7.491 tokens de entrada e 145 de saída. Requisições de seleção/resumo: zero.

## Revisão dos dez critérios

| Critério do cartão | Evidência |
| --- | --- |
| 1. Problema e baseline | Quatro planos independentes; janela recente 0/4, recuperação 4/4. |
| 2. Estado tipado e origem | `ConversationMemory`, autoria, UUID e sequência de origem; correção selecionada por ordem. |
| 3. Estratégia limitada/falha | Uma âncora, 200 trocas, 1.000 caracteres/4.096 bytes; sob demanda; origem inválida não escolhe fallback. |
| 4. Acesso/versões e reconsulta | Fluxo assinado existente; nova SQL reconciliada; 409 de lote antigo e 403 de revogação reais. |
| 5. Retenção/exclusão/isolamento | Sem estado derivado persistido; política de 30 dias existente, provas de proprietário/expiração e delete real. |
| 6. Núcleo, armazenamento e API | 84 + 76 testes; conversa longa pública real. Sem sumarizador: sua falha não se aplica; falha de recuperação é explícita. |
| 7. Dados não confiáveis | Complemento chega inteiro à política; tentativa real de escrita recusada; memória não transporta resposta/SQL. |
| 8. Vínculo atual | Escopo inclui catálogo; seleção não renumera após mudança; referência/sessão/publicação revalidadas. |
| 9. Comparação de qualidade/custo | 0/4 → 4/4; números reconciliados; tokens e tempos delimitados, sem custo extra de resumo. |
| 10. Diagnóstico/reprodução/rollback | Log de versão/sequência sem texto; flag de desativação e contrato; scripts/relatórios privados ignorados. |

Limite deliberado: retomada explícita por posição da consulta na mesma conversa.
Não oferece busca semântica irrestrita, memória entre conversas ou conhecimento de
negócio aprendido com respostas antigas. Os estados oficiais do PRD são preservados.

Revisão final: uma consulta concluída sem âncora representável ocupa sua posição
original; não pode renumerar o histórico e retornar a seguinte. Corrigido e
coberto antes da entrega. Ruff nos sete Python alterados e `git diff --check`
passaram. Nenhum arquivo privado de validação ou segredo foi incluído na mudança.
