# Operação Text-to-SQL F1

Este procedimento cobre diagnóstico e recuperação do caminho F1. Alertas são
relatórios sanitizados gerados a partir dos logs selecionados; o repositório
ainda não encaminha notificações para PagerDuty, e-mail ou chat.

## Coleta e geração de relatórios

1. Selecione no coletor a janela operacional que deseja investigar (padrão
   recomendado: últimos 15 minutos) e exporte somente logs do Backend e GenAI
   necessários à estratégia `text_to_sql_f1` para arquivos locais protegidos.
2. Não publique nem anexe logs brutos a issues. Eles podem conter dados de
   requisição fora dos campos estruturados sanitizados.
3. No container Backend ou em ambiente com os requisitos do Backend, execute:

   ```sh
   python scripts/summarize_text_to_sql_trace.py \
     --logs /caminho/privado/backend.log /caminho/privado/genai.log \
     --prices config/text_to_sql_price_book_2026-11-07.json \
     --as-of 2026-11-07 > /caminho/privado/summary.json
   python scripts/evaluate_text_to_sql_alerts.py \
     --summary /caminho/privado/summary.json \
     --policy config/text_to_sql_alert_thresholds.json \
     > /caminho/privado/alerts.json
   ```

4. Compartilhe somente `summary.json` e `alerts.json`, após confirmar que os
   campos `contains_request_ids` e `contains_question_or_sql` são `false`.
   Correlações são deliberadamente omitidas; para depuração individual,
   pessoas autorizadas consultam os logs no ambiente protegido.

Opcionalmente, entregue o relatório a um coletor HTTP(S) previamente
configurado com `--webhook-url URL`. O POST contém apenas o relatório agregado
sanitizado. O comando tem timeout padrão de três segundos, ajustável por
`--webhook-timeout`; falha de conexão ou resposta não 2xx encerra com erro.
Use somente um destino operacional autorizado. A evidência atual cobre um
coletor efêmero na rede Docker local, não encaminhamento permanente externo.

## Limiares e resposta

| Código | Condição inicial | Ação operacional |
| --- | --- | --- |
| `http_error_ratio` | Mais de 5% de respostas HTTP 429/5xx, com pelo menos 20 requisições na janela | Verifique disponibilidade e quota do provedor, readiness/publicação e tendência por serviço; não reenvie em lote. |
| `provider_failure_ratio` | Mais de 5% de chamadas do modelo falham, com pelo menos 10 eventos de uso/falha | Separe quota, indisponibilidade e erro de contrato pelos motivos/status agregados; confira painel de quota no provedor. |
| `request_latency_p95` | Aviso em 45 s; crítico em 54 s | Compare fila e trabalho do modelo com duração total; acima do crítico, reduza admissão e investigue antes de elevar timeouts. O limite total configurado é 60 s. |
| `sql_latency_p95` | 4 s ou mais | Confira execução e pool no PostgreSQL; preserve limite SQL de 5 s e não aumente timeout sem plano de capacidade. |
| `database_failures` | Aviso a partir de 1; crítico a partir de 3 falhas na janela | Cheque pool, conectividade, grants/readiness Gold v2 e drift; valide uma recuperação antes de reabrir tráfego. |

Os limiares são valores iniciais, versionados em
`backend/config/text_to_sql_alert_thresholds.json`; devem ser ajustados após
tráfego representativo. A estimativa do pricebook assume a tarifa Standard
pública como teto por token, inclui tokens de pensamento no lado de saída e
não conhece descontos, créditos nem elegibilidade Free Tier. Ela não equivale
a cobrança observada. Chamadas sem tokens/modelo tarifável permanecem
desconhecidas.

## Recuperação e registro

1. Preserve limites de concorrência, timeout, somente leitura, allowlist e
   bloqueio de drift; não contorne falhas desativando validações.
2. Se publicação ou banco falhar, mantenha o 503 sanitizado, confira
   conectividade e grants e repita uma requisição controlada após a
   recuperação. Uma publicação que mudou durante a análise deve continuar
   retornando conflito e precisa ser reavaliada do início.
3. Em erros de provedor, confirme quota e disponibilidade antes de retomar;
   retries são limitados pelo contrato atual. Não repita consultas SQL já
   executadas como se fossem novas solicitações idempotentes.
4. Registre janela, código do alerta, resultado da checagem e versão implantada
   no sistema operacional privado. Não copie pergunta, SQL, parâmetros,
   credenciais ou payloads para o registro compartilhado.
5. Se a falha continuar, reduza/desative a admissão F1 pela configuração
   operacional e encaminhe para engenharia; não mude o fluxo legado sem
   validação de rollback.

O CI usa apenas fixture sintética para validar a geração de relatórios. A
execução real com Gemini, coleta contínua, limiares ajustados por SLO e
notificações externas ainda exigem ambiente operacional e autorização próprios.
