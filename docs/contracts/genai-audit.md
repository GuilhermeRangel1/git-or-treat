# GENAI-08 — trilha durável e privacidade

## Política desta entrega

A pessoa usuária aprovou em 31/10/2026 **30 dias** de retenção para a auditoria técnica. O case e o PRD não estipulam um prazo; este é um critério operacional adotado pelo projeto. O prazo começa no recebimento confirmado pelo Backend, em UTC. A consulta administrativa oculta imediatamente registros vencidos. O lifespan do Backend habilitado para Gold ou ingresso de auditoria executa expurgo na inicialização e a cada hora; portanto, a remoção física pode levar até uma hora adicional enquanto o serviço estiver ativo. Se o serviço estiver parado, expurga ao reiniciar. Falha gera aviso fixo e exige intervenção operacional; não altera a data de expiração.

A tabela `public.genai_audit_events` é operacional. A migração `genai08000001` cria índices de correlação/data e expiração e revoga privilégios de `PUBLIC`. Nenhuma concessão é adicionada ao leitor Gold. A prova PostgreSQL verifica recusa de leitura, inserção e remoção pelo login analítico. Não usar a credencial do leitor para auditar nem conceder o token de auditoria a pessoas usuárias do portal.

## Caminho executado

Portal → Backend `app.main:app` → auditoria inicial confirmada → planejar GenAI → gate/consulta Gold → auditoria do resultado → sintetizar GenAI → confirmação durável → revalidação de escopo/publicação → resposta pública.

O Backend grava eventos pelo `AuditStore` com a conexão operacional. O adaptador `BackendEventSink`, composto por `create_app`, envia os eventos do `EventTrace` para `POST /api/v1/internal/genai-audit-events`. Esta rota aceita somente escrita por token dedicado; não chama a rota de perguntas nem executa SQL analítico. A confirmação 201 só ocorre depois do commit. Não existe GET público ou interno de leitura por esse token. A correlação no cabeçalho deve coincidir com o evento.

As credenciais são configuradas privadamente por `GENAI_AUDIT_WRITE_TOKEN` no Backend e `GENAI_AUDIT_URL`/`GENAI_AUDIT_WRITE_TOKEN` no serviço GenAI. Configuração parcial ou ambígua é recusada. O adaptador não segue redirecionamentos, usa timeout de 2 segundos e exige confirmação com referência opaca. Habilitar essa configuração torna a auditoria obrigatória também na composição GenAI. Tokens de sessão e de planejamento/síntese não substituem o token de auditoria.

O núcleo continua sem driver, HTTP ou imports do Backend. As requisições de auditoria são uma comunicação técnica interna adicional, sem callback para a API pública de perguntas. Cada gravação SQL tem timeout de 2 segundos e de lock de 500 ms. O coordenador conserva um único prazo de 35 segundos desde a auditoria inicial até a revalidação final; confirmar a trilha não renova o orçamento.

## Conteúdo permitido e limites de reprodução

Eventos têm schema fechado: estágio/código/estado, correlação, duração, contagens, versão de contrato/catálogo/prompt e fingerprints. Eventos do Backend vinculam também pessoa opaca, lote, origem e métrica admitidos no servidor. Pergunta, histórico, linhas, valores de filtros, SQL com valores interpolados, prompts completos, segredos e textos de exceção não são persistidos. `genai-grounding-v3` identifica as instruções efetivamente utilizadas pelos provedores; alteração de instruções exige nova versão. Hashes e IDs não são anonimização e a trilha permanece restrita.

`audit_reference` da resposta Gold é o UUID opaco de um evento persistido do Backend; a consulta administrativa por essa referência retorna a trilha correlacionada dos dois serviços dentro da retenção. Uma referência não concede acesso. O processo administrativo precisa de acesso autorizado ao ambiente operacional e ao banco; não há nova permissão concedida a sessões do portal.

**Estado atual:** a execução Gold persiste artefato fechado `gold-execution-v1` nos eventos de plano/fonte do Backend: plano estrutural aprovado com valores de filtro substituídos por posições, template PostgreSQL sem interpolação de valores, versões de compilador/catálogo e digest do catálogo, limites de linhas/bytes/timeout e digest do resultado agregado. O SQL retido é somente template parametrizado privado; não é SQL recebido do usuário e nunca é executado a partir da trilha. Não se guardam parâmetros pessoais ou linhas. O fingerprint original vincula os valores que foram omitidos; posições no plano retido não são valores de negócio.

O serviço `verify_audited_execution` recebe o planejamento original autorizado fora da trilha, confere identidade atual antes de ler o artefato, fingerprint/lote/catálogo/template e reexecuta pelo executor existente, com nova validação de escopo e publicação. Retorna somente igualdade do resultado. O digest desconsidera selo de prontidão e chave de cache, preservando valores, filtros, período e lote do cálculo. A prova PostgreSQL também compara o valor com SQL fixo independente do compilador. Isto é integração de software com dados sintéticos, não aceite Gold real.

**Limite restante:** o consumidor administrativo de reprodução agora existe no CLI e revalida a sessão individual atual antes de ler a referência. O operador ainda precisa fornecer o plano original privadamente; valores não podem ser recuperados da trilha. A referência de uma resposta HTTP pública ainda não foi reconciliada com um controle independente na mesma execução, e a privacidade integral em todas as superfícies permanece aberta.

## Operação administrativa

Executar no ambiente privado do Backend. `DATABASE_URL` resolve a sessão individual; `GENAI_GOLD_DATABASE_URL` abre o leitor restrito; `GENAI_AUDIT_DATABASE_URL` deve usar o papel dedicado `venergy_genai_audit_operator`, provisionado por `scripts/provision_genai_audit_operator.sql` e limitado a `SELECT`/`DELETE` em `public.genai_audit_events`. Todas as URLs apontam para o mesmo banco; credenciais ficam em configuração privada, nunca na linha de comando.

```sh
python scripts/genai_audit.py --reference <audit_reference>
python scripts/genai_audit.py --verify-reference <audit_reference> --plan-file <caminho-privado/plan.json>
python scripts/genai_audit.py --purge
```

`--reference` retorna somente eventos ainda válidos; referência desconhecida/expirada retorna lista vazia. `--verify-reference` pede a sessão atual sem eco, valida o mesmo chamador antes de consultar a trilha, recebe o plano original em arquivo privado e retorna somente a referência e `reproduced: true`; não devolve números, template SQL ou parâmetros. Sessão inválida, revogada, de outro chamador, plano divergente ou publicação alterada falha sem revelar o motivo. O arquivo do plano não deve ser versionado. `--purge` é idempotente e remove somente registros com `expires_at <= agora`. Falhas imprimem mensagem fixa, sem DSN ou detalhes SQL. Monitorar o aviso do expurgo e verificar sua execução antes de habilitar tráfego real. Backups e cópias externas precisam de política própria antes da implantação; o comando não remove backups.

## Evidência de integração

`backend/tests/test_genai_session_postgres.py` usa PostgreSQL 16 descartável, migrações reais, leitor analítico restrito, rota pública Backend e processos GenAI separados. O ingresso durável é outro processo `uvicorn app.main:app` por TCP, usando o mesmo banco operacional. O teste confirma eventos dos dois serviços, referência pública persistida e ausência do valor de filtro nos eventos. Token de auditoria inválido impede consulta métrica e resposta com evidência.

`backend/tests/test_genai_audit.py` cobre persistência após nova instância, consulta por referência, expiração exata em 30 dias, expurgo idempotente, autenticação do ingresso e rejeição de campos livres/aninhados. `ai-agent/tests/test_durable_audit.py` cobre confirmação inválida, indisponibilidade e bloqueio antes da fonte/modelo. As suítes existentes cobrem minimização, injeção, saída inválida e fundamentação. A evidência contém somente dados sintéticos; não conclui IA-03/IA-06 ou GENAI-08 integralmente.

## Fundamentação e prompts — continuação GENAI-08

O envelope realmente enviado por Groq e Gemini separa instrução de sistema de pergunta/histórico, glossário lógico (métrica, unidade e origem da proveniência) e evidência. O glossário também é dado sem autoridade para alterar instruções. A revisão atual usa `genai-grounding-v3`; o ingresso Backend mantém compatibilidade com eventos v1. O glossário não contém sinônimos livres nem redefine fórmulas do catálogo Gold v2.

Os adaptadores recusam término informado diferente de `stop` (Groq) ou `STOP` (Gemini), mesmo com JSON sintaticamente válido. Ausência de metadado de término continua compatível com os clientes existentes; JSON inválido, extras e conteúdo vazio seguem recusados. Fontes consultadas em 31/10/2026: [Groq Chat Completions](https://console.groq.com/docs/api-reference) e [Gemini FinishReason](https://ai.google.dev/api/generate-content#FinishReason). A consulta Context7 não encontrou o SDK Python adequado; a referência oficial da API foi usada.

Provas dirigidas:

- GenAI: `python -m pytest -q -p no:cacheprovider tests/test_groq_adapter.py tests/test_gemini_adapter.py tests/test_grounded_claims.py tests/test_evidence_guard.py tests/test_core_composition.py tests/test_safe_events.py tests/test_durable_audit.py`: **171 aprovados**. Cobre envio real ao transporte falso do provedor, saída inválida/truncada, IDs e claims incompatíveis, números inventados, período e injeção/minimização.
- Backend com PostgreSQL 16 descartável: `python -m pytest -q -p no:cacheprovider --tb=short tests/test_genai_executor.py tests/test_genai_session_postgres.py tests/test_genai_audit.py`: **11 aprovados**, um aviso preexistente. A prova integrada existente cobre agregações/razões e ausência, arredondamento aprovado, plano/filtros/lote e fluxo público. Denominador e cálculo pertencem ao executor/catálogo; o modelo não recebe autorização para recalcular.
- O ingresso de auditoria retorna mensagem fixa em erro de validação, sem refletir valores rejeitados.

Estes resultados sustentam dois critérios adicionais de robustez (observações antes da narrativa e prompts). Total GENAI-08: **6/10**. Reprodução independente e plano/template persistido permanecem abertos; o critério composto de privacidade em todas as superfícies também exige reconciliação adicional. Não equivale a aceite de lote real.


### Prova do artefato e reprodução

`python -m pytest -q -p no:cacheprovider --tb=short tests/test_genai_session_postgres.py tests/test_genai_audit.py tests/test_genai_executor.py tests/test_ai_chat.py`: **23 aprovados**, um aviso preexistente, PostgreSQL 16 descartável. A prova confirma artefatos na trilha do fluxo público, ausência de Lumenia no plano/template persistido, resultado 12 por SQL fixo independente e reprodução autorizada; escopo revogado é recusado. O engine operacional oculta parâmetros SQL inclusive quando echo está ligado. Ruff dos arquivos de artefato/coordenação/contrato e teste PostgreSQL passou.

GENAI-08 passa a **7/10** com persistência do artefato. O item de referência pública vinculada a controle independente permanece aberto pelo consumidor administrativo operacional e pelo aceite real; a prova sintética não fecha esse limite.

### Carga Gold v2 disponível para testes locais — 31/10/2026

Os CSVs Gold v2 recebidos foram carregados pelo `backend/scripts/load_gold.py --schema-version gold-csv-v2` em um PostgreSQL 16 local isolado, publicado somente em `127.0.0.1:5433`, com volume Docker persistente `genai08-gold-v2-data`. A configuração privada de conexão está no arquivo ignorado `.env.genai08-local`; não copiar credenciais para `.env`, comandos registrados, Git ou Trello. O banco da revisão DEV 13.1 na porta 5432 não foi alterado.

Resultado observado: uma carga publicada, com as 15 tabelas Gold v2; duas execuções duplicadas interrompidas foram registradas como falhas. A consulta restrita do leitor Gold e o controle independente de linhas/total financeiro do manifesto foram conferidos; privilégios de leitura/escrita fora do escopo e criação de tabela temporária foram negados. As verificações não exibiram valores de negócio. O volume permanece disponível ao trocar de branch ou worktree; o arquivo ignorado de configuração permanece somente nesta worktree e precisa ser configurado privadamente em outra.

### Consumidor administrativo de reprodução — 01/11/2026

O script existente `backend/scripts/genai_audit.py` agora aceita `--verify-reference` e exige o `LogicalReadPlan` original em arquivo privado e uma sessão `grid360_session` válida digitada sem eco. Revalida identidade e permissão antes de ler a trilha e novamente antes/durante a execução; compara o chamador, fingerprint, publicação, catálogo e artefato e usa o executor restrito existente. A saída contém apenas referência e resultado booleano. A conexão operacional consulta a identidade, a Gold continua no papel somente leitura e `GENAI_AUDIT_DATABASE_URL` usa o novo papel `venergy_genai_audit_operator`, restrito à trilha.

Prova dirigida no lote Gold v2 local: sessão temporária com permissão `orders:read` → plano determinístico → executor Gold → evento sanitizado gravado pelo papel operacional → `genai_audit.py --verify-reference` → reprodução aprovada. `SUM(receita_total_reais)` em SQL independente conferiu com o resultado; sessão inválida foi recusada sem saída de evento. A conta/sessão temporária foi removida depois da prova; nenhuma tabela Gold foi alterada. O comando `python -m pytest -q -p no:cacheprovider tests/test_genai_audit.py` passou: **3 aprovados**, um aviso preexistente Starlette/httpx. A verificação operacional do papel confirmou `SELECT`/`DELETE` apenas na tabela de auditoria, sem `INSERT`, leitura de usuários ou `CREATE/TEMP`.

GENAI-08 avança a **8/10**: a trilha agora pode ser consultada e reproduzida por operador autorizado com uma identidade atual, plano privado e controle real independente. Permanecem abertos: vínculo dessa amostra com a resposta pública HTTP do fluxo completo e privacidade integral comprovada em API, contexto, histórico, logs, traces e relatórios. O smoke usou plano determinístico, sem provedor real; não conclui IA-03/IA-06 nem GENAI-08 integralmente.

### Confirmação durável sem bloquear o processamento assíncrono

A fronteira `EventTrace.emit_async` aguarda o sink síncrono em thread. Planejamento, consulta, síntese e insights aguardam a confirmação antes de avançar; falha mantém a resposta Gold bloqueada. Cancelar a espera não interrompe I/O já iniciado na thread; o adaptador HTTP mantém seu timeout de 2 segundos.

Verificação da revisão: suíte GenAI completa com **3.713 aprovados e 4 ignorados**, incluindo auditoria lenta sem bloquear o loop, confirmação antes do próximo estágio, indisponibilidade e cancelamento após início efetivo da fonte. Ruff dos arquivos alterados passou.

## Consolidação da primeira fatia

As duas pendências históricas de referência pública reconciliada e privacidade de ponta a ponta ficam substituídas pela evidência do GENAI-09 e pela prova integrada adicional de aliases/campos derivados/aninhados. A matriz de teste verifica a remoção antes do provedor e ausência na resposta/contexto, persistência, logs do subprocesso e relatório de transporte. Resultados e limites em [consolidação](genai-consolidation.md). GENAI-08 com todos os itens técnicos comprovados nesta primeira fatia, sem encerrar automaticamente IA-03/IA-06 ou certificar uma implantação de produção.
