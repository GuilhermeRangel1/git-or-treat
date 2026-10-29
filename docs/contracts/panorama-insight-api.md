# Contrato v1 — insight contextual do Panorama

**Estado:** contrato provisório da etapa sintética, referente a IA-04. A tela consome apenas o Backend; o Backend monta a evidência a partir dos filtros e do lote do Panorama e chama o endpoint de insight já existente na GenAI.

## Portal → Backend

`POST /api/v1/ai/insights`

O portal envia somente o recorte aplicado e a versão que carregou:

```json
{
  "filters": {
    "periodo": "2024-04",
    "comparacao": "anterior",
    "municipio": "Recife",
    "classe": "Residencial"
  },
  "loteVersao": "panorama-sintetico-2024.04-v1"
}
```

Campos extras são recusados. Em especial, o navegador não pode fornecer `observations`, valores numéricos, fórmula, fonte ou evidência. O Backend valida novamente os filtros com o serviço do Panorama, recalcula a métrica de energia faturada e monta `screen` com período, filtros efetivos, observações, referência e limitações.

## Backend → GenAI

O Backend chama `POST /api/v1/insights`, encaminhando Bearer de serviço e `X-Correlation-ID`. A chamada usa o contrato `screen` publicado pela GenAI. O portal não recebe a credencial nem acessa diretamente a GenAI.

O Backend verifica o contrato e a correlação da resposta. Em estado `answered`, também exige que métrica, unidade, período, filtros e valores observados correspondam ao contexto calculado no servidor. A resposta é recusada como inválida se a GenAI devolver outro recorte.

## Resposta

O envelope contém:

- `insight`: estado v1, contexto, `observation.values`, `hypothesis` ou `message`, evidências, limitações e metadados de correlação/auditoria;
- `metric`: ID, definição e fórmula da métrica do Panorama;
- `analysis`: direção da variação percentual e, quando há comparação por grupos, maior contribuição positiva/negativa e compensação;
- `source`: tipo, lote, data de atualização, marca sintética e limitações da fonte.

`observation.values` representa números calculados pelo Backend. O bloco `analysis` identifica a direção e o percentual da mudança, além dos grupos que mais contribuíram ou compensaram a variação quando o recorte permite essa decomposição. `participacaoPercentual` é a parcela do movimento entre grupos que apontam na mesma direção (quedas para a contribuição principal; altas ou quedas compensatórias para a compensação), não a parcela do total líquido. Esses valores são recalculados a partir dos mesmos registros usados pelo Panorama. A interface apresenta a leitura e um próximo passo para investigar, sem atribuir causa aos dados. Se não houver comparação ou detalhamento suficiente, os campos correspondentes ficam indisponíveis.

Quando o recorte validado não contém registros, o Backend retorna HTTP 200 com `insight.status=no_evidence`, mensagem de ausência e listas de observações/evidências vazias, sem chamar a GenAI. Contexto, lote, definição da métrica e correlação são preservados; a análise fica indisponível. Registros existentes com valor zero continuam sendo observações válidas. A validação de filtros, lote e fonte ocorre antes dessa decisão.

## Erros

| HTTP | Código | Comportamento |
| --- | --- | --- |
| 409 | `invalid_context` | O lote mudou depois da consulta do Panorama; atualizar os indicadores antes de tentar de novo. |
| 422 | `invalid_request` | Contrato ou filtro inválido; não encaminhar à GenAI. |
| 502 | `invalid_upstream_response` | Contrato, correlação ou recorte devolvido pela GenAI é inválido. |
| 503 | `service_unavailable` | Fonte ou serviço indisponível; repetir somente quando `retryable` for verdadeiro. |
| 504 | `service_unavailable` | GenAI excedeu o timeout; repetir manualmente. |

HTTP 503 recebido da GenAI é tratado como indisponibilidade. Um envelope v1 válido e correlacionado preserva `error.retryable`; resposta genérica de proxy permite tentativa manual. Envelope que declara o contrato com versão, correlação ou campos inválidos continua sendo HTTP 502. O Backend não repete a chamada automaticamente nem expõe o corpo da falha upstream.

Erros públicos usam o envelope v1 com `message`, `error.code`, `error.retryable` e `correlation_id`. Nenhum detalhe interno, token, SQL ou conteúdo do modelo que não passe pelo contrato deve ser exposto.

## Limites desta versão

A fonte atual é a fixture sintética do Panorama e a rota falha fechada quando a fonte configurada não permite construir o contexto. A demonstração não comprova reconciliação com Gold, autorização de pessoa usuária, auditoria persistida ou resposta ao vivo de provedor. A integração com Gold deve preservar a construção de contexto no servidor e revisar o dicionário de métrica antes de liberar uma fonte real.
