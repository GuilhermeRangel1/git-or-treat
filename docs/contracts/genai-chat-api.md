# Contrato de chat entre portal, Backend e GenAI

**Versão:** v1, em implementação para desenvolvimento local.

**Estado:** contrato técnico provisório integrado no portal para desenvolvimento local; revisão dos responsáveis por Backend, GenAI e Frontend pendente.

**Escopo:** perguntas conversacionais com a fonte sintética atual. Não define a consulta Gold, identidade de usuário, retenção de histórico nem o insight contextual IA-04.

## Caminho da chamada

O navegador chama somente o Backend. O Backend valida o contrato público e encaminha a pergunta ao endpoint conversacional do serviço GenAI. O serviço GenAI segue responsável por interpretação, guardrails, fonte de evidência e resposta. O Backend não executa SQL nesta rota.

```text
Portal → POST /api/v1/ai/questions → Backend → POST /api/v1/questions → GenAI
       ← resposta v1            ← validação e encaminhamento ← resposta v1
```

O endpoint legado `POST /api/v1/ai/query` continua separado do chat e responde 503 para entradas válidas; não executa consulta analítica.

O cliente do portal mantém as mensagens na memória da página e envia no máximo três turnos anteriores junto da nova pergunta. Não há armazenamento em `localStorage`, sessão no Backend ou restauração após recarregar. O contexto é não confiável e não concede identidade ou permissão. O navegador não chama o GenAI diretamente e não recebe credenciais de serviço ou a chave do Gemini.

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
| 422 | `invalid_request` | Não | Campo ausente/inválido, versão incompatível ou campo extra. |
| 502 | `invalid_upstream_response` | Não | Status diferente de 200/503, JSON de sucesso inválido ou envelope/correlação incompatível. |
| 503 | `service_unavailable` | Conforme a origem | URL ausente, serviço não alcançável ou HTTP 503 genérico da GenAI. Em HTTP 503 com envelope v1 válido e correlacionado, preservar `error.retryable` (inclusive falso). Configurar URL sem token impede a inicialização do Backend. |
| 504 | `service_unavailable` | Sim | Chamada excedeu `AI_AGENT_TIMEOUT_SECONDS`. |

O Backend não repete chamadas automaticamente. O campo `retryable` informa ao consumidor se uma nova tentativa pode ser útil; não garante que repetir produza resultado diferente.

O portal valida o envelope v1 em tempo de execução antes de mostrar o conteúdo. Para HTTP com erro válido, a mensagem pública e `retryable` orientam a tela; falha de rede permite ação manual de repetição, sem repetição automática. Respostas são renderizadas como texto, sem interpretar HTML ou Markdown recebido do modelo. O estado de esclarecimento, recusa, ausência e erro não é apresentado como resposta quantitativa.

## Comunicação Backend → GenAI

- O Backend usa `AI_AGENT_BASE_URL` e faz `POST /api/v1/questions` com o mesmo JSON v1.
- `AI_AGENT_SERVICE_API_TOKEN` é enviado como `Authorization: Bearer ...`; o serviço GenAI valida esse token quando configurado. Tokens têm pelo menos 32 caracteres e permanecem no servidor.
- `X-Correlation-ID` é criado pelo Backend, propagado ao GenAI e devolvido no cabeçalho e envelope da resposta. O ID correlaciona uma chamada; não é identidade nem trilha de auditoria persistida.
- `AI_AGENT_TIMEOUT_SECONDS` tem default 35 s e faixa de 0,1 a 120 s; o timeout total interno configurado no GenAI também pode interromper antes.
- Redirecionamentos HTTP são desabilitados pelo cliente para não encaminhar credenciais a outro host.
- O contrato é síncrono HTTP/JSON, sem retry automático. O endpoint do GenAI deve ser acessível apenas pela rede privada do serviço em implantação.

## Identidade e sessão: limites desta versão

O token autentica o serviço Backend perante o GenAI, mas não identifica a pessoa que usa o portal. Nesta etapa, a autorização de demonstração ainda depende da configuração local explícita do GenAI (`GENAI_ENVIRONMENT=local` e `GENAI_ENABLE_DEMO_ACCESS=true`). O Backend não encaminha identidade ou permissões de usuário, pois o projeto ainda não tem uma autenticação de usuário acordada.

O contexto não é gravado em banco, não recebe ID de sessão e expira com o estado em memória do consumidor. O Frontend não deve anunciar histórico restaurável nem compartilhar contexto entre conversas. Persistência, expiração, exclusão, retenção e serialização por sessão ficam pendentes de decisão e implementação posteriores.

**Este contrato permite integrar e testar a jornada demonstrativa sem Gold. Não conclui IA-05**, não valida autenticação de usuário ou isolamento de sessões reais e não autoriza uso do endpoint com dados Gold.
