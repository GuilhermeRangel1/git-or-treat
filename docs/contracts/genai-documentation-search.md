# Busca em documentação autorizada

Cartão: [busca semântica](https://trello.com/c/gctQzTDV). Adicional conceitual do
Assistente, apoiando IA-02/03/05, sem alterar seus estados oficiais.

## Fonte e atualização

O corpus inicial contém as nove definições já aprovadas no [FAQ](indicator-faq.md).
Dados/negócio mantém as definições; Frontend/GenAI mantém seleção e publicação.
Público: usuários internos autenticados com leitura das métricas correspondentes.
Não inclui dataset, nomes de clientes, valores Gold ou documentos arbitrários.

Após `npm run generate:faq` em frontend, executar na raiz:

```text
python scripts/generate-genai-documentation.py
python scripts/generate-genai-documentation.py --check
```

O gerador confere texto/rótulo contra o catálogo Gold v2 e produz cópias idênticas
em `ai-agent/app/corpora/indicators.json` e `backend/app/corpora/indicators.json`.
O CI confere a reprodução. IDs de verbete são estáveis; a versão é SHA-256 do
conteúdo serializado, truncado a 12 caracteres, compatível com o FAQ. Uma mudança
de conteúdo exige nova versão e implantação dos dois serviços.

## Execução

Portal → Backend/sessão → coordenação Gold existente → planejamento GenAI →
`DocumentationResponder` → porta `DocumentationSource`/adaptador
`IndicatorDocumentation` → extração literal → Backend confere fonte/escopo/texto
e citação → auditoria → portal. O fundamento mostra título, seção, versão e ID.

O roteamento reconhece explicações conceituais e preserva o caminho quantitativo
para perguntas de valores/períodos. A composição Gold real injeta o adaptador;
composições demonstrativas não o habilitam automaticamente. A publicação Gold
continua sendo conferida pelo coordenador, mas a definição não representa uma
medição daquele lote e não recebe período/unidade numérica inventados.

Filtra perfil, fonte, operação, métricas, público, tela, vigência e conflitos antes
de enviar qualquer trecho ao provedor. Busca lexical atende apenas verbetes aprovados exatos ou frases que casam
integralmente com o rótulo do indicador;
nos demais casos, um seletor semântico Gemini opcional escolhe um ID do corpus
autorizado ou se abstém. A seleção distingue relevância (`id`) de suficiência
(`sufficient`); um trecho parcial só autoriza esclarecimento, com exemplo do
próprio verbete. O modelo recebe trechos como dados e não escreve a resposta.
Resposta é extraída literalmente, sem geração livre de regras. Sem seleção
segura, esclarece ou informa ausência; falha de fonte/provedor é explícita.

O envelope interno v1 admite `answered` e `no_evidence` sem plano. `answered`
exige `documentation_reference` com ID/versão. O Backend valida o conteúdo literal
contra sua própria cópia e rejeita texto/citação adulterados ou fora do escopo.
Implantar Backend compatível antes do GenAI; consumidores antigos recusam os
novos estados em vez de executar SQL indevido. Envelopes sem referência permanecem
inalterados para as respostas quantitativas existentes.

## Limites e segurança

Até 24 trechos, corpus de 64 KiB, trecho de 4 KiB, textos de 16 KiB e JSON
serializado de até 32 KiB. A recuperação consome o orçamento de fonte do
controlador. Seleção usa no máximo uma chamada de modelo, até 20 segundos, dentro
do prazo compartilhado e sem retries automáticos; a configuração de modelo pode
impor prazo menor. Saída limitada a 256 tokens e esquema fechado de ID/null. Só
`GENAI_MODEL_PROVIDER=gemini` com chave configurada habilita seleção remota; utiliza
`GENAI_GEMINI_MODEL`. Desabilitar o provedor não deixa uma chave residual provocar
chamadas. Os casos canônicos funcionam sem modelo. A chave permanece no GenAI.

Não foi adotado índice vetorial persistido: na avaliação inicial, embeddings
aproximavam conceitos diferentes e produziam abstinência excessiva. Para nove
verbetes curtos, seleção estruturada diretamente sobre o corpus filtrado demonstrou
melhor resultado, com uma chamada e sem estado derivado. O índice lexical é
reconstruído sob demanda. Essa escolha não implica usar o modelo para gerar SQL,
planos, fórmulas ou texto factual.

Não há índice/cache persistido nem extensão de retenção. Conteúdo e hash são lidos
a cada pedido; remoção/expiração/permissão são reaplicadas antes da citação e pelo
Backend após o retorno. Novas permissões requerem novo escopo autenticado. Pergunta
e documentos passam pelos controles existentes de segurança; trechos não podem
autorizar SQL ou ampliar acesso. Auditoria registra chamadas, referência resumida
por hash e resultado, sem mensagens, vetores ou definições nos eventos.

Desativar `GENAI_DOCUMENTATION_SEARCH_ENABLED=false` e reiniciar GenAI restaura o
planejamento anterior. Rollback não exige migração. Remover um documento requer
regenerar e implantar as duas cópias; divergência de versão falha fechada.

## Evidências e estado

Integração executável com aceite técnico local. Revisão dos dez critérios,
comandos, comparação, prova API/portal e limites em
[busca documental — evidências](../plans/2026-11-03-genai-busca-documental.md).
Não certifica nova cobertura Gold nem conclui automaticamente os requisitos
obrigatórios. Implementação permanece na branch até revisão/commit/PR/merge.


## Ampliação solicitada — 03/11/2026

A busca agora publica 16 verbetes: nove comparativos do FAQ e sete individuais,
com cobertura conceitual dos 14 indicadores do catálogo Gold v2. Os novos textos
são extraídos literalmente de `definition`/`label` do catálogo: consumo médio
por UC, satisfação mensal e acumulada, DEC, FEC, chamados por abertura e chamados
acumulados. Não expõe mapeamentos físicos ou dados operacionais. Cada definição
individual requer apenas sua própria métrica autorizada; verbetes comparativos
continuam exigindo todas as métricas que explicam.

O gerador preserva o FAQ original e recalcula a versão do corpus ampliado; a
versão documental passa a ser independente da versão do pacote FAQ. As duas
cópias de runtime continuam idênticas. Remover uma métrica do catálogo retira o
verbete individual na próxima geração; mudanças de versão invalidam referências
históricas anteriores conforme o contrato existente.

Expressões “me explica”, “pode me explicar” e “o que quer dizer” entram no caminho
conceitual. Datas e localidades explícitas continuam no caminho quantitativo.

A seleção de definições individuais é explícita em `INDIVIDUAL_METRICS` no
gerador, com status e vigência próprios. Retirar ou expirar o FAQ de receita
não altera esses verbetes. Incluir uma métrica nova no catálogo não autoriza sua
publicação automática: revisar seleção, responsável e vigência antes da geração.
