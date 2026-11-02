# Contrato v1 — insight contextual do Panorama

**Estado:** contrato público v1 para demonstração explícita e integração Gold v2, referente a IA-04. A tela consome apenas o Backend; o Backend monta a evidência a partir dos filtros e do lote do Panorama e chama o endpoint de insight já existente na GenAI.

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

Campos extras são recusados. Em especial, o navegador não pode fornecer `observations`, valores numéricos, fórmula, fonte ou evidência. O Backend valida novamente os filtros com o serviço do Panorama, recalcula energia faturada na demonstração ou receita comparável na Gold v2 e monta `screen` com período, filtros efetivos, observações, referência e limitações.

## Backend → GenAI

Em `ANALYTICS_SOURCE=gold`, a sessão individual deve manter `orders:read`. O resolvedor da aplicação produz o escopo; cabeçalhos livres e filtros não concedem acesso. O Backend usa o mesmo pool de leitura restrita e `GoldPublicationContext` do chat, com snapshot PostgreSQL somente leitura. `read_gold_panorama_financials` e `gold_panorama_revenue_metric` são compartilhados com o KPI: soma de `gold_v2.diagnostico_receita.receita_base_comparavel_reais`, não receita total nem paga. Não consulta cadastro individual para gerar insight.

A Gold usa `POST /api/v1/internal/insight-syntheses`, protegido por token de serviço e composição Gold externa. Recebe `screen`, `access_scope`, `batch_ref` exclusivamente v2 e `remaining_timeout_ms` (saldo do prazo original de 35 s). A rota pública GenAI `/api/v1/insights` mantém o contrato demonstrativo e recusa referência real. O núcleo `ScreenInsightOrchestrator` é o mesmo; recebe números estruturados, valida escopo, minimiza filtros e escolhe observações autorizadas. O texto livre do modelo não é publicado.

Prontidão deve liberar `faturamento.receita` na mesma publicação, com controles aprovados na configuração do servidor. Competência comparativa ausente não invalida a observação atual; comparação e contribuição ficam indisponíveis. A decomposição exige grupos completos nas duas competências e reconciliação dos agregados. Usa soma Decimal, valores em reais com precisão de centavos e participação com uma casa decimal sobre movimentos do mesmo sinal. Grupos incompletos ou acima do limite produzem limitação explícita.

A sessão e a publicação são revalidadas antes da leitura, antes do modelo e antes da entrega, inclusive após confirmar auditoria. Revogação recusa a resposta; mudança de publicação produz 409. O orçamento SQL compartilhado é de 5 s; o cancelamento da coroutine não comprova cancelamento imediato de trabalho em thread. Não há fallback Gold → demonstração.

O caminho demonstrativo permanece:

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

## Auditoria, implantação e reprodução Gold

A migração `genai12000001` cria `gold.publicacao_contexto` com somente schema, lote, UUID de publicação, fingerprint e data de importação. Replica os grants SELECT explícitos da view de publicação anterior, exceto PUBLIC; não concede leitura da tabela operacional de carga. Os scripts de provisionamento incluem a nova view para leitores criados depois da migração. Execute migrações antes de atualizar o consumidor.

Eventos Backend de fluxo `insight` guardam referência de publicação, identidade opaca e SHA-256 do contexto canônico; não guardam os filtros em claro, números ou SQL. A referência pública é emitida após confirmação durável. Para reproduzir na publicação ainda corrente, o operador da trilha usa sua credencial separada, a sessão individual atual da pessoa dona da referência e um arquivo privado com o pedido original (filtros/lote, sem observações):

```powershell
python scripts/genai_audit.py --verify-insight-reference <referencia> --insight-request-file <pedido-privado.json>
```

O cookie é solicitado sem eco. A reprodução recalcula o contexto pelo leitor restrito e confronta o digest; escopo diferente, publicação alterada ou filtros adulterados não recebem confirmação. Não reconstruir uma publicação antiga a partir de uma Gold sobrescrita.

No portal, cache Gold inclui origem, lote, fingerprint e atualização, com revalidação na montagem e retorno à janela. Resposta de outro KPI/recorte é rejeitada; atualização em curso, erro e 409 prevalecem sobre sucesso antigo. O cartão usa a receita comparável, moeda brasileira e origem real; hipóteses, fundamento e limitações ficam separados. Demonstração conserva sua marca explícita.

## Evidência e limites

A prova local de 01/11/2026 usa Gold v2, sessão individual e Gemini, com controle SQL independente e referência reproduzida. Testes controlados complementam comparação, contribuições, zero/ausência/parcial, revogação, falha de auditoria, timeout e concorrência do consumidor. Veja o [registro GENAI-12](../plans/2026-11-01-genai12-panorama-gold.md). Esse aceite local não certifica produção, fechamento mensal ou causalidade e não conclui automaticamente IA-03/IA-04/IA-05.
