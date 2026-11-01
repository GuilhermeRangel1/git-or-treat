# Contrato de chat entre portal, Backend e GenAI

**Versão:** v1, em implementação para desenvolvimento local.

**Estado:** contrato técnico provisório integrado no portal para desenvolvimento local; revisão dos responsáveis por Backend, GenAI e Frontend pendente.

**Escopo:** envelope público v1 de perguntas, compatível com fonte sintética explícita e Gold v2. A consulta Gold segue o [contrato interno](genai-query-execution.md), a [coordenação](genai-gold-coordination.md) e a [auditoria](genai-audit.md). Histórico persistido e insight IA-04 têm escopos próprios.

## Caminho da chamada

O navegador chama somente o Backend. Em modo sintético, ele encaminha o envelope ao endpoint conversacional GenAI. Em modo Gold, o Backend resolve a sessão individual, solicita plano à GenAI, valida prontidão e executa SQL parametrizado com leitor restrito; depois envia evidência tipada à síntese GenAI. O núcleo mantém interpretação, guardrails e fundamentação. Falha Gold não ativa demonstração.

```text
Portal → POST /api/v1/ai/questions → Backend
  Sintético: Backend → POST /api/v1/questions → GenAI
  Gold: Backend → plano GenAI → executor Gold Backend → síntese GenAI
Portal ← envelope público v1 validado pelo Backend
```

O endpoint legado `POST /api/v1/ai/query` continua separado do chat e responde 503 para entradas válidas; não executa consulta analítica.

O cliente do portal mantém as mensagens na memória da página e envia no máximo três turnos anteriores junto da nova pergunta. Não há armazenamento em `localStorage`, persistência de conversa no Backend ou restauração após recarregar. A sessão de autenticação por cookie é independente do histórico do chat. O contexto é não confiável e não concede identidade ou permissão. O navegador não chama o GenAI diretamente e não recebe credenciais de serviço ou a chave do Gemini.

## Requisição pública

`POST /api/v1/ai/questions`, `Content-Type: application/json`.

```json
{
  "contract_version": "v1",
  "question": "Qual foi o consumo em Olinda?",
  "context": [
    {"role": "user", "content": "Considere o período de demonstração."},
    {"role": "assistant", "content": "Vou considerar o período demonstrativo."}
  ]
}
```

| Campo | Regra |
| --- | --- |
| `contract_version` | Literal `v1`; opcional na requisição por compatibilidade, com default `v1`; `null` ou outra versão é rejeitada. |
| `question` | Texto não vazio após trim, até 1.000 caracteres. |
| `context` | Opcional, até três turnos em ordem; cada turno só aceita `role` (`user` ou `assistant`) e `content` não vazio de até 1.000 caracteres. |
| `expected_publication` | Opcional, só na fonte Gold: `{lote, fingerprint}` da publicação exibida na tela (fingerprint com 64 hex minúsculos). Divergência da publicação atual retorna 409; no modo sintético retorna 422. Não autoriza nem seleciona dados e não é repassado à GenAI. Ver [invalidação](genai-invalidation.md#6-publicação-esperada-informada-pelo-consumidor). |
| Campos adicionais | Rejeitados. |
| Corpo HTTP | Limite global de 65.536 bytes no Backend. Os limites de campo reduzem o payload esperado do chat. |

O contrato não inclui `user_id`, escopo, métricas autorizadas, SQL nem ID de sessão. O cliente pode reenviar contexto em cada chamada, mas esses turnos são conteúdo não confiável; não concedem autorização. A conversa é stateless: não há histórico persistido pelo Backend ou GenAI neste recorte.

## Resposta de negócio

Solicitações aceitas retornam HTTP 200 e o envelope v1 do GenAI, validado novamente pelo Backend. Os estados de negócio são `answered`, `needs_clarification`, `refused`, `no_evidence` e `recoverable_error`. `answered` contém `answer` e ao menos uma evidência; os demais estados contêm `message`. O envelope também pode incluir `evidence`, `limitations`, `analysis_context`, `model_tier`, `error`, `audit_reference` e `correlation_id`.

Exemplo de resposta sintética:

```json
{
  "contract_version": "v1",
  "correlation_id": "0123456789abcdef0123456789abcdef",
  "audit_reference": null,
  "error": null,
  "status": "answered",
  "model_tier": "light",
  "answer": "Resposta demonstrativa.",
  "message": null,
  "evidence": [
    {
      "source": "synthetic.fixture",
      "description": "Cenário sintético de consumo.",
      "is_demo": true
    }
  ],
  "limitations": ["Valor fictício; não representa a Gold."],
  "analysis_context": null
}
```

O exemplo é ilustrativo, não uma resposta numérica aprovada. A interface deve exibir as limitações e identificar `is_demo`; não deve transformar texto de esclarecimento, recusa ou erro em resposta quantitativa.

## Erros HTTP e repetição

Erros de protocolo usam o envelope seguro `status: "error"`, `contract_version`, `correlation_id`, `message` e `error: {code, retryable}`. Nenhum erro encaminha stack trace, SQL, credenciais, corpo upstream ou detalhes de exceção.

| HTTP | Código | Retry | Condição |
| --- | --- | --- | --- |
| 401/403 | `access_denied` | Não | Sessão ausente/inválida ou leitura Gold não autorizada. |
| 409 | `invalid_context` | Sim | Publicação Gold alterada; nova pergunta deve capturar plano/lote atuais. |
| 409 | `invalid_context` | Não | `expected_publication` difere da publicação atual; recarregar a tela antes de perguntar de novo. |
| 422 | `invalid_request` | Não | Campo ausente/inválido, versão incompatível ou campo extra. |
| 502 | `invalid_upstream_response` | Não | Status diferente de 200/503, JSON de sucesso inválido ou envelope/correlação incompatível. |
| 503 | `service_unavailable` | Conforme a origem | URL ausente, serviço não alcançável ou HTTP 503 genérico da GenAI. Em HTTP 503 com envelope v1 válido e correlacionado, preservar `error.retryable` (inclusive falso). Configurar URL sem token impede a inicialização do Backend. |
| 503 | `service_unavailable` | Não | Catálogo físico Gold incompatível entre os serviços, métrica fora do catálogo do Backend, schema `gold_v2` divergente ou publicação não v2. Ver [invalidação](genai-invalidation.md). |
| 504 | `service_unavailable` | Sim | Chamada excedeu `AI_AGENT_TIMEOUT_SECONDS`. |

O Backend não repete chamadas automaticamente. O campo `retryable` informa ao consumidor se uma nova tentativa pode ser útil; não garante que repetir produza resultado diferente.

O portal valida o envelope v1 em tempo de execução antes de mostrar o conteúdo. Para HTTP com erro válido, a mensagem pública e `retryable` orientam a tela; falha de rede permite ação manual de repetição, sem repetição automática. Respostas são renderizadas como texto, sem interpretar HTML ou Markdown recebido do modelo. O estado de esclarecimento, recusa, ausência e erro não é apresentado como resposta quantitativa.

## Comunicação Backend → GenAI

- O Backend usa `AI_AGENT_BASE_URL`: modo sintético faz `POST /api/v1/questions`; modo Gold usa `POST /api/v1/internal/question-plans` e `/api/v1/internal/question-syntheses`. Os envelopes internos não são aceitos do navegador.
- `AI_AGENT_SERVICE_API_TOKEN` é enviado como `Authorization: Bearer ...`; o serviço GenAI valida esse token quando configurado. Tokens têm pelo menos 32 caracteres e permanecem no servidor.
- `X-Correlation-ID` é criado pelo Backend, propagado ao GenAI e devolvido no cabeçalho e envelope da resposta. O ID correlaciona uma chamada; não é identidade nem trilha de auditoria persistida.
- `AI_AGENT_TIMEOUT_SECONDS` tem default 35 s e faixa de 0,1 a 120 s; o timeout total interno configurado no GenAI também pode interromper antes.
- Redirecionamentos HTTP são desabilitados pelo cliente para não encaminhar credenciais a outro host.
- O contrato é síncrono HTTP/JSON, sem retry automático. O endpoint do GenAI deve ser acessível apenas pela rede privada do serviço em implantação.

## Identidade e sessão: limites desta versão

O token autentica o serviço Backend perante a GenAI. No modo Gold, a pessoa é autenticada pelo cookie HttpOnly grid360_session e sua permissão de leitura é revalidada no servidor. O Backend deriva AccessScope e o envia somente pelas operações internas; pergunta, histórico e cabeçalhos públicos não concedem acesso. Demonstração permanece exclusiva de fontes synthetic.* com configuração local explícita.

O contexto não é gravado em banco, não recebe ID de sessão e expira com o estado em memória do consumidor. O Frontend não deve anunciar histórico restaurável nem compartilhar contexto entre conversas. Persistência, expiração, exclusão, retenção e serialização por sessão ficam pendentes de decisão e implementação posteriores.

A referência pública audit_reference é preenchida somente após confirmação durável. A trilha autorizada permite reproduzir a execução; correlação sozinha não é auditoria. O Assistente mostra a referência, respeita is_demo e descarta mensagens/contexto quando a identidade confirmada muda. Estados de negócio e erros HTTP não são convertidos em resposta quantitativa.

O contrato está integrado na fatia Gold v2 do GENAI-09; cobertura dos demais domínios e aceite oficial IA-01/IA-05 permanecem separados. Evidências e limites em [primeira pergunta](genai-first-question.md).

## Rótulos do catálogo no contrato público v1

`analysis_context.metric` e as chaves de `filters` preservam os IDs lógicos. Os campos opcionais `metric_label`, `metric_definition` e `filter_labels` vêm do perfil validado contra o catálogo Backend, e o Assistente os usa para apresentar métrica, definição e dimensões. Só filtros aplicados admitem rótulos. Respostas antigas continuam aceitas pelo portal novo; Backend com o schema estendido deve preceder a GenAI nova, por causa da validação estrita de campos. Não foram alterados IDs, autorização, fórmulas ou versão Gold. Evidências em [consolidação](genai-consolidation.md).
