# GENAI-09 — primeira pergunta real: evidência local

## Resultado em 01/11/2026

Integração executável real pela API: login individual → POST /api/v1/ai/questions → planejamento HTTP GenAI → prontidão observada no PostgreSQL → executor restrito → síntese Gemini → resposta answered com referência durável. A jornada visual do portal ainda não foi executada nesta prova.

Base de código: 8274009 com alterações locais na branch feat/genai-primeira-pergunta-real. Backend usa app.main:app; GenAI usa app.gold_runtime:create_gold_app, perfil Gold v2 e fonte gold.local. PostgreSQL 16: container genai08-gold-v2-postgres e volume genai08-gold-v2-data, previamente carregado pelo importador oficial. C01/C02/C04 passaram e foram aprovados pela pessoa usuária apenas para esta entrega local. Nenhuma aprovação foi inferida para os demais controles.

## Reprodução privada

A amostra privada fica em work/genai09-local, ignorado pelo Git. result.json contém a pergunta, controle independente e envelope público, sem senha ou cookie. model-result.json contém a saída do modelo e evidência minimizada para diagnóstico autorizado; não publicar esses arquivos. O roteiro smoke.py cria identidade temporária orders:read, faz login HTTP e remove a conta em finally. Credenciais ficam no ambiente privado.

Pergunta: receita de um município em mês explícito coberto pelo lote. O recorte é escolhido deterministicamente pela competência mais recente e município ordenado com receita não nula. Controle independente, separado do compilador de planos:

```sql
SELECT competencia, municipio, SUM(receita_total_reais) AS total
FROM gold_v2.diagnostico_receita
WHERE municipio IS NOT NULL
GROUP BY competencia, municipio
HAVING SUM(receita_total_reais) IS NOT NULL
ORDER BY competencia DESC, municipio
LIMIT 1;
```

Comando privado observado: docker exec -e PYTHONPATH=/repo/backend -w /repo/backend genai09-local-backend-direct python /repo/work/genai09-local/smoke.py. Resultado: login 200, pergunta 200, answered, sem erro e com audit_reference. Conta removida ao final. O total Decimal do controle confere com a observação; a representação numérica e unidade dessa observação aparecem na resposta. Período, filtros e referência de origem conferem entre evidência e contrato público. O identificador do lote permanece na trilha interna autorizada; não é publicado no documento.

## Correções e verificações

- Criado entrypoint Gold implantável que reutiliza create_app; auditoria obrigatória e execução exclusivamente no Backend.
- Prompt genai-grounding-v3 esclarece que filtro de município não vira dimensão da linha agregada. A v2 produziu claims com dimensão ausente na observação e foi corretamente recusada; a v3 respondeu sem relaxar o guard.
- Backend aceita eventos de prompts v1/v2/v3; referência opaca fica visível no Assistente.
- GenAI: 99 testes de runtime/claims/adaptador e 25 de EvidenceGuard passaram. Backend: 3 de auditoria passaram, com aviso preexistente Starlette/httpx. Interface: 12 testes, tipos/build e fronteiras passaram; lint sem erros, com aviso preexistente AuthProvider.
- Prontidão pela rede host levou 32,94 s e uma chamada pública encerrou com 504. A ligação direta entre containers permitiu completar o fluxo dentro do prazo existente. Não foi aumentado o limite de 35 s.

## Limites

Ainda faltam navegação real do portal, repetição desta fatia com vazio/ambiguidade/acesso negado/indisponibilidade e falhas de modelo/auditoria, replay administrativo da referência desta resposta e revisão integrada dos consumidores. A evidência HTTP não conclui IA-01 nem GENAI-09 integralmente. Dataset, payloads privados e chaves não entram no Git. Instrumentação diagnóstica local não integra o código de produção.

## Continuação — falhas pela API real

Em 01/11/2026, `docker exec -e PYTHONPATH=/repo/backend -w /repo/backend genai09-local-backend-direct python /repo/work/genai09-local/failures.py` comprovou:

- Pergunta sem período: HTTP 200, needs_clarification, sem answer.
- Município não reconhecido: HTTP 200, needs_clarification, sem answer.
- Revogação de orders:read após login: HTTP 403, sem answer.

O roteiro cria conta temporária e a remove em finally; senha e cookie ficam em memória. Resultado sanitizado em work/genai09-local/failure-results.json. Município desconhecido não comprova recorte autorizado vazio. Permanecem vazios legítimos, fonte/modelo/auditoria indisponíveis e jornada visual. Nenhum novo critério composto foi marcado por estes três subcasos.

## Contrato de falhas de autorização e auditoria

A rota de chat traduz HTTPException 401/403 das dependências Gold para o envelope público v1: access_denied, retryable false e correlação. Detalhes privados da identidade não são refletidos. OpenAPI documenta ambos os estados. Isso permite ao consumidor Assistente reconhecer a recusa em vez de exibir uma falha genérica fora do contrato.

`tests/test_ai_chat.py` acrescenta casos de 401/403 e falha SQLAlchemy da auditoria na coordenação Gold pelo endpoint: resposta 503/service_unavailable, retryable false, sem answer ou detalhe privado. A dependência de recurso é controlada; a rota e o coordenador são os reais. Não é um ensaio de queda do PostgreSQL de produção.

Verificação Linux: ANALYTICS_SOURCE=synthetic, removendo GENAI_AUDIT_WRITE_TOKEN e GENAI_GOLD_DATABASE_URL apenas do processo pytest, `python -m pytest -q -p no:cacheprovider tests/test_ai_chat.py`: 15 passaram, aviso preexistente Starlette/httpx. Uma execução anterior herdou configuração Gold e falhou nos casos sintéticos; não foi contabilizada como sucesso. Sem novo aceite composto por essa seleção.

### Falha de publicação no contrato público

A rota agora traduz GoldPublicationUnavailable/GoldPublicationInvalid para HTTP 503, code service_unavailable e retryable false, com correlação e mensagem fixa. Publicação alterada preserva o tratamento específico HTTP 409. A indisponibilidade deixa de escapar como erro interno fora do envelope do chat.

Verificação: `docker exec -e ANALYTICS_SOURCE=synthetic -w /repo/backend genai09-local-backend-direct env -u GENAI_AUDIT_WRITE_TOKEN python -m pytest -q -p no:cacheprovider tests/test_ai_chat.py`: 17 passaram, aviso preexistente Starlette/httpx. A primeira execução herdou configuração Gold e falhou em seis casos demonstrativos; a execução limpa acima resolveu a interferência. Novos testes injetam falha na fronteira do coordenador: comprovam o contrato HTTP, não simulam queda real do PostgreSQL.

## Reprodução da referência pública real

Em 01/11/2026, o roteiro privado replay-smoke.py repetiu a pergunta pela API real com Gemini e chamou `backend/scripts/genai_audit.py::_verify_reference` sobre o audit_reference público. Plano privado reconstruído a partir do plano estrutural auditado e dos filtros originais da evidência minimizada; nenhum SQL livre foi fornecido ao replay. A sessão individual foi mantida apenas em memória. Leitura da trilha pela credencial de operador e reexecução pelo leitor restrito, com revalidação da sessão, plano, catálogo e publicação.

Comando: `docker exec -e PYTHONPATH=/repo/backend -w /repo/backend genai09-local-backend-direct python /repo/work/genai09-local/replay-smoke.py`.

Resultado observado: login 200; pergunta 200/answered; administrative_replay true; both_services true. Conta temporária removida em finally. O prompt efetivamente usado é v3, o catálogo lógico v1 sobre schema Gold v2, e a referência concreta do lote/controle permanece nos artefatos privados. O controle independente SUM está documentado acima. Não houve jornada visual nem preenchimento interativo do CLI: o roteiro chamou o consumidor administrativo com getpass substituído pela sessão em memória.

## Configuração executada e separação das evidências

A prova real usou o commit 2f71fcac0346b563e7d363894dff06ce0a3cfa9c com as alterações locais de tratamento de erros documentadas nesta continuação.

| Processo | Entrada executada | Versões observadas |
| --- | --- | --- |
| Backend local | app.main:app, container genai09-local-backend-direct, porta 8010 | Python 3.12.16; FastAPI 0.162.0; SQLAlchemy 2.1.6; psycopg 3.3.6 |
| GenAI local | app.gold_runtime:create_gold_app, fábrica Gold, porta 8011 | Python 3.12.6; FastAPI 0.136.3; google-genai 2.31.0 |
| Banco | genai08-gold-v2-postgres, volume persistente genai08-gold-v2-data | PostgreSQL 16; publicação Gold CSV v2 |

As versões foram obtidas por importlib.metadata nos processos/ambientes executados. A imagem Backend requereu instalação da dependência pwdlib[argon2], já declarada em requirements.txt. Não representa revisão da imagem final de implantação.

Configuração Backend: ANALYTICS_SOURCE=gold, ORDERS_AUTH_MODE=session, AI_AGENT_BASE_URL apontando para a GenAI local, GENAI_GOLD_DATABASE_URL com papel venergy_genai_reader, GENAI_AUDIT_DATABASE_URL com operador dedicado e GENAI_GOLD_APPROVED_CONTROLS=[C01,C02,C04]. Segredos não constam aqui. Conexão operacional usa v_energy_app com a leitura analítica local explicitamente autorizada. A conexão quantitativa permanece separada.

Configuração GenAI: perfil Gold v2, demonstração e roteamento demonstrativo desligados, provedor Gemini, token técnico e destino durável de auditoria. A instrumentação privada envolve o adaptador para guardar sua saída original, sem modificar a resposta ou substituir fonte/modelo. Essa instrumentação não integra a aplicação versionada.

Conectividade do modelo: chamada Gemini concluída. Cálculo: observação e representação pública conciliadas com SUM independente e replay da referência. Experiência do portal: testes de componente passaram, mas navegação real ainda não comprovada; controle de navegador indisponível nas configurações atuais do Work. Esses resultados permanecem distintos.

A busca privada por combinação vazia na competência mais recente não encontrou ausência entre município/classe nem município/classe/subgrupo observados. Isso não é um teste aprovado de vazio nem autoriza remover dados para fabricar um aceite.
