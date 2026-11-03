# Memória de investigações anteriores

Cartão: [Memória para conversas mais longas](https://trello.com/c/Wen9zrG0).
Extensão opcional de IA-07, Gold v2. Estratégia `ordered-anchor-retrieval`, versão 1.

## Comportamento

O histórico já conserva o recorte atual além da janela curta. Esta extensão permite
retomar uma consulta mais antiga da **mesma conversa**, depois de mudar de assunto:

- “Retome a primeira consulta”.
- “Volte à consulta 2, só comercial”.
- “Retome a última análise mas agora em Olinda”.
- “Volte à consulta anterior”.

Primeira/segunda/terceira ou números de 1 a 200 identificam consultas concluídas,
na ordem em que foram feitas. Última é a mais recente;
anterior/penúltima é a imediatamente anterior a ela. Esclarecimentos, recusas e
tentativas interrompidas não contam como consultas concluídas. Se a consulta
escolhida não tiver intenção recuperável, pede reformulação sem selecionar outra.
Uma correção que
produz uma nova consulta ocupa uma nova posição; escolher expressamente uma posição
antiga recupera aquele recorte, não o substitui pelo da investigação mais recente.
Não há busca livre por tema nem seleção silenciosa de uma conversa diferente.

Sem complemento, consulta novamente o recorte escolhido. Com complemento, o núcleo
aplica as regras existentes de correção, acompanhamento ou nova pergunta completa.
O complemento original, incluindo negações e instruções indevidas, chega ao mesmo
controle de segurança. Mensagens normais continuam usando o contexto atual.

## Composição, proveniência e limites

Portal → rota existente `POST /api/v1/ai/conversations/{id}/questions` → sessão e
propriedade → `ConversationStore.memory` → `ConversationMemory` → referência
assinada existente → `ask_genai_question` → núcleo/plano → SQL restrito → síntese
e auditoria → armazenamento normal da nova troca.

`ConversationMemory` é interna: versão, autoria `user`, UUID da requisição de
origem, sequência, pergunta normalizada e publicação. O texto normalizado deriva
do plano capturado pelo servidor, não da resposta numérica. A memória não contém
SQL, números de resposta, prompt interno ou credenciais. O contrato público v1 e
as versões de histórico existentes são preservados; não há migração.

Recupera **uma** âncora de até 1.000 caracteres/4.096 bytes, em no máximo 200 trocas
da conversa. A atualização é sob demanda, apenas com referência explícita, lendo
o histórico atual. Não acrescenta chamadas de modelo para resumo ou seleção.
O núcleo recebe a mesma janela limitada de contexto, não centenas de mensagens.
O teto em bytes é um limite conservador para o texto, não uma medição do tokenizer.

Uma origem ausente, malformada, com versão incompatível ou de outro escopo gera
409 `conversation_conflict`, não repetível, com orientação para formular a consulta
novamente. Não escolhe outra origem como fallback. A seleção preserva posições
antes de conferir o escopo, evitando renumerar e retornar outra consulta após uma
mudança de permissões. Publicação precisa ser uma referência canônica Gold v2.

O Backend revalida identidade, permissões e catálogo; a referência é emitida na
sessão atual. O fluxo existente confere a publicação antes de executar/sintetizar
e produz uma nova auditoria. Fatos de negócio e causalidade não vêm do histórico.
O log de recuperação contém somente versão e sequência da origem.

## Retenção, falhas e implantação

Reutiliza as âncoras das trocas existentes, sem resumo, índice ou cache derivados
persistidos. Segue a política aprovada de 30 dias após a última mensagem; excluir
ou expirar a conversa torna a origem indisponível imediatamente. A expiração
física continua com `purge_history`. Não aumenta retenção nem cria acesso a outra
pessoa. O histórico também pode ser aberto por outra sessão autenticada do mesmo
proprietário; isso reemite a referência em vez de reutilizar o token antigo.

Não há sumarizador cuja falha possa produzir fatos: origem inválida encerra a
recuperação. Pergunta recuperada e complemento são replanejados e submetidos à
política; não se tornam instruções do sistema nem autorização.

Implantar o Backend desta entrega sobre os contratos atuais. Desativar por
`GENAI_CONVERSATION_MEMORY_ENABLED=false` e reiniciar o Backend conserva o histórico
e o comportamento anterior. Rollback do código não requer alteração de dados.
O frontend já consome a rota e os estados usados nesta entrega; não há novo layout.

Evidência, comparação e limites: [validação de memória](../plans/2026-11-03-genai-memoria-conversas-longas.md).


## Integração com busca documental — PR #114

A branch recebeu a develop `ef3a625` por merge `5a2dc82`, preservando os commits
originais e as duas documentações. A memória interna distingue `gold` de
`documentation`; isso não altera o envelope público nem exige migração.

Perguntas documentais respondidas contam na mesma ordem das consultas concluídas.
Ao retomar uma delas, o Backend confere o escopo e a vigência da citação e envia
somente a pergunta original para nova execução no núcleo. Limpa token/contexto
numéricos herdados. A resposta antiga nunca é usada como definição. A intenção
efetivamente executada fica em `anchor`, com `batch=None`, para que uma segunda
retomada recupere o conceito e não o comando “retome a consulta 2”.

Uma explicação documental encerra a âncora numérica implícita anterior: a próxima
pergunta curta não assume que o usuário ainda fala daquela consulta Gold. A
consulta numérica antiga continua recuperável por sua posição explícita. Retirada,
versão desatualizada ou escopo alterado tornam a origem documental indisponível,
sem renumerar as demais perguntas. `no_evidence` sem citação não é promovido a
memória documental. Complementos de recorte em retomada documental são recusados
nesta fatia; formule uma pergunta completa para iniciar uma medição Gold.

A seleção continua explícita e ordinal. Busca semântica sobre documentação não
significa busca semântica em mensagens antigas, nem resolve automaticamente toda
referência como “dele” após uma explicação. Consultas de números continuam exigindo
indicador/recorte e evidência Gold atuais.
