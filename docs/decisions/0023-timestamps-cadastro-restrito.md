# ADR-0023: Pareamento do cadastro restrito pelos manifestos

- **Data:** 02/11/2026
- **Estado:** aprovada pela pessoa usuária
- **Escopo:** carga Backend do pacote `gold-cadastro-v1` pareado a `gold-csv-v2` (WEB-03)

## Contexto

O pacote local possui timestamps `data_processamento_gold` nas linhas cadastrais 425 segundos anteriores ao timestamp do manifesto. Run, linhagem e referências cruzadas dos manifestos identificam a mesma publicação; o instante Gold declarado nos dois manifestos coincide. A validação anterior exigia ainda igualdade entre cada linha e o manifesto, bloqueando o pacote apesar da identidade pareada.

## Decisão

Parear a publicação por `run_id`, linhagem, `data_processamento_gold` e IDs de exportação/schemas cruzados entre os dois manifestos. O timestamp em cada linha continua obrigatório, com formato e fuso válidos, e precisa ser uniforme no pacote; pode diferir do timestamp dos manifestos. O Backend persiste o valor presente na linha, mas não o usa para identificar ou parear a publicação.

## Alternativas consideradas

- Rejeitar o pacote e pedir nova exportação com timestamps idênticos: mantém a validação mais estrita, mas bloqueia dados cuja identidade já está comprovada pelos manifestos.
- Substituir o timestamp de cada linha pelo instante do manifesto: simplifica consumidores, mas altera silenciosamente um valor de origem.
- **Aprovada:** preservar timestamps das linhas e usar os manifestos pareados como identidade; exige uniformidade do valor de linha para recusar lotes temporalmente mistos.

## Consequências e validação

- Divergência entre os timestamps das linhas e dos manifestos deixa de ser falha por si só; os manifestos continuam obrigados a coincidir entre si.
- A carga conserva proveniência temporal por registro e a auditoria identifica a publicação pelos metadados dos manifestos.
- O carregador local registrou `status=unchanged`, `restricted_cadastro.status=loaded`, 45.000 registros e `available_to_genai=false`; a publicação analítica já estava ativa. Smoke autenticado com perfil `admin`: login e overview HTTP 200, identificação `available`, nome presente; UC e valor do nome foram suprimidos. Health da API e frontend retornaram HTTP 200. WEB-03 permanece em andamento até o aceite integral.
