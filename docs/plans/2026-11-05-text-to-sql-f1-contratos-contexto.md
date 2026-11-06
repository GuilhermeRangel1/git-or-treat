# TSQL-04 — conferência de contratos e contexto F1

**Data:** 05/11/2026
**Estado:** concluída no escopo de contratos e preparação do contexto; integração na rota pública pertence à TSQL-07.
**Branch:** `feat/genai-text-to-sql`.

## O que foi conferido

- Backend e GenAI mantêm schemas Pydantic independentes para candidatos e transporte `text-to-sql-f1-v1`; os schemas e suas regras de estado são iguais sem importar um serviço no outro.
- Contratos de candidato e evidência usam fixtures comuns válidas/inválidas. O fixture HTTP agora também contém requests e responses inválidos para testar versão, correlação, orçamento, campos extras e coerência do envelope nos dois processos.
- Datas e períodos têm formato e calendário validados; parâmetros recusam coerção de tipos e valores não finitos. Valores decimais atravessam como strings. A revisão Backend liga nomes de parâmetros por AST e os testes rejeitam referências ausentes, extras ou substituídas antes da fronteira de conexão.
- Evidência versionada preserva aliases, unidade monetária, tipos, múltiplas medidas de comparação, linhagem e valores decimais sem conversão para `float`.
- O builder Backend inclui pergunta, turnos recebidos, publicação, cobertura, versões do catálogo, metadados autorizados e regras F1. O digest vincula identidade/escopo e conteúdo. Usa catálogo/modelos instalados, não introspecção do banco vivo; não envia identificadores de usuário como contexto.
- Testes confirmam que turnos conversacionais entram no conteúdo do contexto e que trocar o turno altera `context_version`. `prepare_sql_candidate` re-resolve caller/session e publicação antes da chamada ao modelo; pseudônimo de sessão é obrigatório. A resolução de proprietário/conversa já existe no caminho conversacional vigente; ligar o gerador SQL a esse caminho está reservado para TSQL-07.
- O contrato público de request/response permanece v1 e separado dos schemas de candidato. Um teste verifica `without_publication()`, preservação de pergunta/contexto e rejeição de `candidate`/`sql` na resposta pública.
- Excesso de 64 KiB falha explicitamente. O builder não corta contexto. O observador agora registra versões de catálogo/dicionário, IDs e colunas autorizados, contagens e `truncation=none`; contexto insuficiente registra motivo/tamanho. Os logs não incluem pergunta, turnos, valores dimensionais, credenciais ou evidência.
- O contrato público atual continua separado. A rota interna de candidatos exige autenticação técnica/correlação e a geração fica desligada por padrão; a nova rota de síntese ainda não existe.

## Verificações desta rodada

- `python -m pytest tests/test_sql_generation_contract.py tests/test_sql_evidence_contract.py -q -p no:cacheprovider --tb=short` em `ai-agent/`: **45 passaram em 1,94 s**, incluindo comparação de schema e aceitação/rejeição de fixtures no Backend em processo separado.
- Reexecução com teste do default-off: **46 passaram em 2,03 s**, mais Ruff aprovado para `tests/test_sql_generation_contract.py`.
- `python -m pytest tests/test_sql_candidate_http.py -vv -p no:cacheprovider --tb=short` em `ai-agent/`: interrompido após 30 s no primeiro teste ASGI; resultado inconclusivo, sem atribuir aprovação.
- `python -m pytest tests/test_genai_sql_context.py tests/test_genai_sql_client.py tests/test_genai_sql_evidence.py tests/test_genai_sql_parameters.py -q -p no:cacheprovider --tb=short` em `backend/`: não coletou, pois o Python disponível não tem `pwdlib`; o venv citado por rodadas anteriores não existe neste worktree.
- O teste HTTP cruzado dos envelopes candidato/request/response foi executado isoladamente dentro da primeira verificação e passou.
- Atualização de sessão/conversa: **19 testes focados passaram em 1,65 s**, cobrindo pseudônimo de sessão, escopo/publicação frescos antes da geração, turnos no digest, logs sanitizados e contrato público.
- `python -m ruff check app/services/genai_sql_context.py app/services/genai_sql_observation.py tests/test_genai_sql_context.py tests/test_genai_sql_observation.py tests/test_genai_sql_public_contract.py` em `backend/`: passou.

## Limites que seguem em outras etapas

1. Ligar `prepare_sql_candidate` à rota pública de conversa e comprovar o fluxo completo: TSQL-07. A preparação já exige escopo/publicação atuais e vincula os turnos recebidos ao digest.
2. Fazer implantação de ensaio Backend → GenAI em ambiente compartilhado antes de habilitar a flag. A ordem está definida e os contratos/default-off são testados; o ensaio distribuído é rollout posterior.
3. A suíte Backend completa e os testes ASGI não foram executados neste worktree: falta `pwdlib`, e o sandbox Windows bloqueia o socketpair usado pelo `asyncio`. Os testes específicos abaixo passaram sem o `conftest` global.

**Conclusão:** TSQL-04 está concluída como contrato/contexto de preparação. A rota pública generativa não foi alterada; a integração de ponta a ponta é TSQL-07. A ausência da suíte Backend completa está registrada, sem declarar cobertura que não foi executada. Não houve chamada de modelo, consulta a dados Gold, commit ou push.
