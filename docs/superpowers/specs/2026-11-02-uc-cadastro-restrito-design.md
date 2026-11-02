# UC 360 com cadastro de titular restrito

## Intenção

Exibir o nome de exibição do titular na visão UC 360 a partir do pacote
`gold-cadastro-v1` informado pela pessoa usuária. O nome deve permanecer fora do
schema analítico Gold v2, do leitor GenAI, de buscas em lista, logs, auditorias e
contexto de IA.

## Abordagem aprovada

O Backend importa o pacote cadastral separado, valida seu manifesto contra o
manifesto Gold v2 correspondente e armazena a projeção em `gold_cadastro`. Uma
conexão de runtime dedicada e somente leitura acessa apenas esse schema. A rota
de overview de UC usa a autorização `ucs:read` existente, disponível aos perfis
Atendimento e Admin, consulta o cadastro para a UC selecionada e devolve o nome
e um estado de identificação tipado. O Frontend apresenta nome disponível e
mensagem específica para ausência, conflito ou integração indisponível.

O CSV continua fora do Git e o cliente web nunca lê arquivos locais. O Backend
não envia nome para o catálogo, planejamento, evidência, síntese ou auditoria
GenAI. `customer_reference` continua nulo.

## Alternativas consideradas

- Incluir o cadastro em `gold_v2`: recusada porque o contrato separa dados
  cadastrais pessoais do leitor analítico.
- Ler o CSV diretamente no Backend em cada consulta ou no navegador: recusada
  porque ignora a publicação transacional e não aplica uma ACL do banco por
  credencial dedicada.
- Carregar em schema separado e consultar por escopo de sessão: aprovada,
  conforme `gold-cadastro-v1`, D20 e a autorização existente de UC.

## Limites e estados

- `DISPONIVEL` devolve o nome sanitizado conforme o produtor.
- `AUSENTE_NA_ORIGEM` e `CONFLITO_NA_ORIGEM` devolvem nome nulo e explicação
  correspondente.
- Pacote não carregado, referência incompatível ou falha na conexão restrita
  devolvem nome nulo com estado de integração indisponível; não significam
  ausência de titular.
- A consulta é feita apenas para a UC selecionada; resultados de busca não
  incluem nomes.
- A identidade da consulta deve corresponder à publicação analítica ativa e ao
  `cadastro_export_id` certificado pelo manifesto Gold v2.

## Restrições

- Fonte: pacote local Gold `GOLD_20261031T020143Z_fd69c375/dbc5928deefc45cead71f3fda8560136`.
- Schema físico cadastral e papel de leitura ficam separados de `gold_v2` e do
  papel `venergy_gold_reader`.
- Persistência e autorização são responsabilidade do Backend; o Frontend só
  apresenta o contrato.
- WEB-03 permanece em andamento e WEB-10 em validação até a evidência integrada
  cobrir os critérios completos de cada requisito.

## Verificação prevista

Importar somente o pacote cadastral que referencia exatamente o pacote
`gold-csv-v2` do mesmo `run_id`; conferir publicação, contagens e privilégios do
papel restrito sem exibir linhas pessoais. Pela API, verificar acesso autorizado,
acesso negado, nome disponível, ausência, conflito e indisponibilidade. Conferir
que a tela UC 360 apresenta os estados sem colocar o nome na busca ou na IA.


## Revisão aprovada em 02/11/2026

O pareamento cadastral/analítico usa os metadados dos manifestos, incluindo igualdade do instante Gold e IDs cruzados. `data_processamento_gold` das linhas cadastrais é metadado da projeção: precisa ter fuso, formato válido e ser uniforme no pacote, mas pode diferir dos manifestos. O importador persiste o timestamp declarado nas linhas e não o usa como chave de identidade da publicação.
