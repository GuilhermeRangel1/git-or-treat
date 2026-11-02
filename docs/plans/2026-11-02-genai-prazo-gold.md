# Prazo compartilhado do chat e insight Gold — 02/11/2026

Requisitos: IA-01, IA-04 e IA-06. A pessoa usuária aprovou a revisão da [ADR-0002](../decisions/0002-genai-gold-query-owner.md) após uma consulta válida atingir 35 s pela soma da prontidão e do provedor. Esta fatia entrega integração executável e revalidação local Gold v2; não altera o estado oficial desses requisitos.

## Caminho e comportamento

Portal → Backend autenticado → plano/prontidão → SQL restrito → síntese GenAI → auditoria/revalidação → consumidor. Chat e insight compartilham o limite vigente de **60 s** no Backend. O Assistente interrompe a espera em **70 s**; o transporte interno e o runner de validação recebem margem compatível. O Backend passa o saldo restante em milissegundos; os contratos dos dois serviços aceitam 1 a 60.000, com rejeição de 60.001. Cada etapa consome o mesmo relógio. SQL continua limitado ao menor valor entre 5 s e saldo, incluindo a preparação de prontidão. Prazos de auditoria e limites locais do provedor continuam aplicáveis.

`backend/app/core/genai_limits.py` concentra o teto usado pela coordenação, planejamento, executor, observação e configuração. A fonte efetiva é `gold.local`, catálogo `gold-catalog-v2`, schema `gold_v2`, publicação `gold-csv-v2`, perfil `v-energy-grid-360-gold`. A atualização local aplicou a GenAI antes do Backend; o banco e a carga persistida foram preservados.

Para implantar, atualizar primeiro a GenAI que aceita o novo saldo e depois o Backend que o emite. Instalações com `AI_AGENT_TIMEOUT_SECONDS=35` devem ajustar explicitamente para 60; o arquivo privado local foi atualizado. Os exemplos compartilhados exercitam o teto de 60.000 e a rejeição de 60.001. O número 35.000 ainda é um saldo válido depois de consumir parte do orçamento.

## Verificações automatizadas

- GenAI: `python -m pytest -c ai-agent/pyproject.toml --rootdir ai-agent ai-agent/tests -q -p anyio --tb=short -rs` em processo limpo, sem `.env` carregado: **4.160 passaram, 5 skips** por smoke opt-in, symlink Windows ou DSNs de integração ausentes.
- Backend, container com `DATABASE_URL=sqlite:///:memory:`, `ANALYTICS_SOURCE=synthetic` e documentos atuais montados: `python -m pytest -q -p no:cacheprovider tests`: **901 passaram, 114 skips** de integrações sem configuração; aviso preexistente Starlette/httpx. A primeira tentativa dirigida usou vetores antigos copiados na imagem e a configuração Gold indevida para as fixtures; a repetição correta passou (192 testes, 4 skips) antes da suíte completa.
- Frontend: `npm test -- src/features/assistente/api.test.ts`: **11 passaram**. O teste com relógio controlado garante que aos 60 s a chamada segue ativa e aos 70 s é cancelada, permitindo repetição manual.
- `npm run lint`: zero erros, aviso preexistente em `AuthProvider.tsx`; `npm run check:boundaries` e `npm run build`: passaram. Formatação dos dois arquivos foi aplicada pelo Prettier.
- Ruff nos arquivos Python alterados e `git diff --check`: passaram.
- O teste do prazo Backend conserva 20 s depois de 40 s consumidos, mantém SQL em 5 s, reduz para 1 s quando resta 1 s e recusa trabalho após 60 s. Os envelopes de plano/síntese recebem saldos decrescentes, sem renovação.

Os comandos de teste locais usam containers apenas como ambiente de dependências; as fixtures controladas não equivalem a reconciliação com o lote. A matriz privada de aceitação usa o lote real e controle SQL independente.

## Matriz Gold v2 e Gemini reais

Execução `20261102T104426_802753Z`, pela API pública, com sessão individual e controle SQL independente: **43 PASS, 5 BLOQUEADO, 7 SEM_AMOSTRA_NO_LOTE e 2 NAO_EXECUTADO**, sem falhas inesperadas/conhecidas ou erros de execução. Os dois não executados são SEG-06/07, verificados nas regressões técnicas separadas. CON-01 respondeu HTTP 200 `answered` em **15,93 s**; na matriz anterior esse caso havia atingido o prazo global de 35 s. A trilha confirmou modelo concluído em todas as **22 respostas numéricas**; a conta sem acesso continuou recebendo 403. Contas e sessões temporárias foram removidas, com contagem independente de zero usuários `matrix-*` remanescentes.

Os bloqueios continuam FAT-08 (arrecadação), INT-01/02/03 (cobertura de continuidade) e ATE-01 (atendimento mensal). Os sete recortes sem amostra também permanecem identificados. Essa execução não homologa os domínios nem demonstra garantia de latência futura. O prazo maior absorve variação; o custo de prontidão e o tempo do provedor continuam relevantes.

Reprodução privada: compose Gold local, `backend python /repo/work/genai-assistente-cleanup/run_matrix_private.py --output-dir /repo/work/genai-local-validation`, com diretório da worktree montado somente leitura e saída privada gravável. O harness usa a configuração já existente, perguntas permitidas e agregados minimizados, sem registrar senha ou enviar linhas brutas/dados pessoais. A saída fica ignorada em `work/genai-local-validation/20261102T104426_802753Z/`; a checagem independente da trilha está em `work/genai-assistente-cleanup/verify_timeout_matrix.py`.

### Insight do Panorama

Após autorização específica, o teste privado autenticou uma conta temporária somente leitura, consultou o Panorama Gold v2 e enviou o mesmo recorte/publicação para `POST /api/v1/ai/insights`. Resultado: **HTTP 200, answered em 15,12 s**, origem real e chamada do modelo concluída na auditoria. A conta e suas sessões foram removidas no `finally`. O harness privado `work/genai-assistente-cleanup/test_timeout_insight.py` usa a chave configurada no serviço e envia somente agregados minimizados ao Gemini. Trata-se de validação pela API real; a fronteira de cancelamento do navegador foi validada com relógio controlado no teste do transporte, sem nova jornada visual.
