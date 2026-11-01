# GENAI-11 — Assistente com respostas Gold v2

Estado: 9/10 critérios técnicos comprovados; pendente exercitar movimento reduzido em navegador real. Branch `feat/genai-assistente-gold`, base `b804b58`; implementação registrada nos commits `4d0b985` e `e835d8e`.

## Caminho e resultado

Portal `/assistente` → Backend `/api/v1/ai/questions` → plano GenAI → executor Backend com leitor restrito → síntese GenAI → confirmação de auditoria → resposta pública. O núcleo e os consumidores existentes foram estendidos. Contrato físico `gold-csv-v2`, catálogo `gold-catalog-v2`, schema `gold_v2`, perfil `v-energy-grid-360-gold` e fonte `gold.local`.

Respostas usam nomes de negócio, valores em reais no formato brasileiro, meses por extenso e linhas por observação em séries. Origem, lote, definição e referência de conferência ficam nos fundamentos; filtros e limitações permanecem legíveis. Aviso de demonstração é visível sem expandir detalhes. HTML e links são texto simples. O frontend não recebe SQL, acesso direto ao banco ou chave do provedor.

O envio tem trava síncrona, prazo de 40 segundos e foco de retorno ao campo. Rascunho é preservado em falhas; erros e recusas são excluídos do contexto. HTTP 409 remove respostas e retentativas incompatíveis. 401/403, 422 e 429 orientam nova ação. Rede e timeout permitem retentativa manual.

## Evidência observada em 01/11/2026

- `ai-agent`: pytest nos arquivos `test_gold_planning_http.py`, `test_question_flow.py` e `test_sql_demo_http.py`: **64 passaram**; Ruff dos arquivos afetados: passou.
- `backend`: pytest `tests/test_ai_chat.py tests/test_genai_internal_contract.py`: **97 passaram**.
- `frontend`: `npm test -- src/features/assistente`: **33 passaram**; `npm run build`, `npm run format:check` e `npm run check:boundaries`: passaram. `npm run lint`: sem erros, com aviso preexistente em `AuthProvider.tsx:108`.
- Docker: PostgreSQL com volume local existente, Backend e GenAI da branch montados em rede isolada. A pergunta mensal de receita usou Gemini real e retornou `answered`; o total coincidiu, até centavos, com `SUM(receita_total_reais)` da mesma competência em `gold_v2.diagnostico_receita`. Resposta confirmou lote v2, referência de auditoria e `is_demo=false`. Conta temporária de leitura removida ao final. A chave existe na configuração privada; seu valor não foi registrado.
- A tentativa inicial via encaminhamento de portas do Windows retornou timeout; a comunicação direta entre containers na mesma rede passou. O filtro de hosts foi preservado com o alias permitido `backend`.
- Revisão em dois eixos identificou filtros omitidos sem rótulo e retentativas antigas após 409; ambos corrigidos, com regressão pela tela para a invalidação das retentativas. Também foi documentado o campo opcional `batch_reference`.

## Critérios do cartão

Comprovados: configuração/metadados reais; apresentação de número/período/filtros/unidade/origem/lote/fundamento/limites; estados de negócio; associação e contexto após erro/recusa; envio/retentativa e invalidação de lote; tratamento HTTP/rede/timeout; texto seguro.

A continuação da validação liberou o navegador integrado. A jornada autenticada real confirmou resposta Gold com Gemini, lote, definição e auditoria nos fundamentos, recusa de alteração e esclarecimento de período. Desktop e viewport 390 × 844 foram inspecionados nos temas claro e escuro: sem transbordamento horizontal; campo de envio disponível; retorno de foco ao campo; fundamentos alcançados por Shift+Tab com contorno visível; histórico rolado ao fim com Ctrl+End; anúncio configurado em log polite. Console sem erros na amostra.

Os textos principais e secundários medidos no claro ficaram em 15,53:1 e 5,52:1; no escuro, 13,24:1 e 7,15:1. O rótulo de recusa escuro apresentou 4,31:1 e foi corrigido para o token existente `action-danger-text` (#ffb4ab); o aviso demonstrativo passou a usar `status-warning-text`. A cor corrigida foi confirmada no navegador. Respostas fora de ordem após troca de identidade e de rota, dupla submissão no mesmo ciclo e ausência de contexto herdado passaram nos testes da tela. A conta temporária foi desconectada e removida; viewport restaurado. Captura local sem valores privados: `work/genai11-local/assistente-mobile-claro.png`, ignorada pelo Git.

Pendente somente o exercício com movimento reduzido ativo no navegador: `prefers-reduced-motion` retornou falso nesta sessão. A regra `motion-reduce:animate-none` está implementada no indicador, mas não foi validada sob essa preferência real. O último item de robustez/acessibilidade permanece aberto por essa prova; não representa uma certificação completa por leitor de tela.

IA-03 e IA-05 preservam seus estados oficiais no PRD; este registro não conclui o card integralmente. Scripts, credenciais e resultados privados ficam em `work/`, ignorados pelo Git; nenhum conteúdo do lote foi copiado para esta evidência pública.
