# Consolidação dos cartões GenAI na Gold v2

Base: `c5501f2`, após os PRs #88 a #92, na branch `feat/genai-consolidacao-gold`.
Esta revisão mantém os estados oficiais IA do PRD. O fechamento de um cartão técnico não certifica todos os domínios ou a implantação de produção.

## GENAI-07 — auditoria integrada: comprovado

A pendência era propagação do escopo/correlação e destino durável obrigatório. A implementação integrada está em `answer_gold_question`, `EventTrace` e `BackendEventSink`. O teste `backend/tests/test_genai_session_postgres.py` atravessa login, rota pública, PostgreSQL com leitor restrito, planejamento/síntese em processos separados e ingresso durável por TCP. Confere eventos dos dois serviços, referência persistida, mesma correlação e ausência do filtro nos eventos. Token inválido e falha na confirmação final impedem resposta quantitativa.

O registro `genai-first-question.md` comprova a mesma primeira fatia na Gold local autorizada e no portal, com SQL independente e reprodução administrativa. A evidência posterior do GENAI-09 substitui a limitação histórica do GENAI-07; não habilita atendimento ou outros domínios ainda sem aceite.

## GENAI-08 — referência e privacidade: comprovados na primeira fatia

A referência efetivamente exibida no portal foi reconciliada e reproduzida conforme `genai-first-question.md`. A trilha liga pessoa autorizada, plano, publicação e digest do cálculo; não é apenas hash solto. O plano de replay recebe os valores de filtros privadamente e reautoriza a identidade atual.

Nesta consolidação, a matriz PostgreSQL existente ganhou uma prova de privacidade no fluxo público Gold: somente no suporte de teste, a evidência recebida na síntese contém aliases e estruturas derivadas/aninhadas artificiais. O adaptador de modelo confirma que recebe somente observação, valor, unidade e período. Os marcadores não aparecem na resposta pública (inclusive contexto), nos eventos persistidos, nas saídas/logs do subprocesso ou no registro de transporte que serve de relatório da prova. Guard, eventos e relatório de regressão também são conferidos pelas suítes existentes. Não foram enviados dados pessoais ou novas amostras a um provedor externo.

Verificações em 01/11/2026:

- Backend, PostgreSQL 16 descartável, `python -m pytest -q -p no:cacheprovider --tb=short tests/test_genai_session_postgres.py tests/test_genai_audit.py tests/test_ai_chat.py`: **21 passaram**, incluindo a prova pública estendida; o teste usa migrações reais e teardown.
- GenAI, `python -m pytest -q -p no:cacheprovider --tb=short tests/test_evidence_guard.py tests/test_safe_events.py tests/test_durable_audit.py tests/test_reusable_core.py tests/test_genai_regression.py`: **183 passaram**.

## Próximas verificações e limites preservados

| Cartão | Pendência a conferir |
| --- | --- |
| GENAI-02 | Aprovar regras dimensionais e controles independentes para todos os domínios. A primeira pergunta não aprova todos os domínios. |
| GENAI-03 | Itens técnicos de vocabulário comprovados nesta consolidação; expansão de escopo para outros domínios continua separada. |
| GENAI-04 | Completar a matriz de filtros e períodos pelo endpoint integrado; os cinco casos sem suporte não substituem os demais critérios. |
| GENAI-05 | Itens técnicos de credencial e grants comprovados no ambiente Gold local; não equivale a implantação em produção. |
| GENAI-06 | Amostra autorizada comprovada pelo consumidor integrado; permanece a cláusula composta de custo, cancelamento por desconexão e concorrência. Timeout isolado não certifica custo. |

GENAI-01 e GENAI-09 já tinham todos os itens comprovados. GENAI-07 e GENAI-08 passam a ter todos os itens técnicos comprovados para a primeira fatia. Os demais cartões permanecem abertos até as respectivas evidências; cancelamento por desconexão e operação sob carga não são presumidos.

## GENAI-03 — vocabulário público versionado

O contexto aplicado conserva `metric` e as chaves de `filters` como identificadores lógicos. Os campos opcionais `metric_label`, `metric_definition` e `filter_labels` transportam rótulos/definição do perfil efetivamente usado pelo planejador. O catálogo Backend já confere igualdade de rótulo, definição e unidade com esse perfil em `test_gold_catalog_backend_contract.py`; o portal consome os textos recebidos, sem outra tabela de tradução. Os rótulos de filtro só podem referenciar filtros aplicados existentes. As dimensões do trecho quantitativo também usam os rótulos do perfil.

O decoder anterior continua aceitando respostas sem esses campos e a tela usa o ID como fallback. O Backend deve ser atualizado antes da GenAI que publica os campos, pois os modelos antigos recusam extras; o portal novo aceita os dois formatos. A definição é acessível no título do recorte. Fórmulas, colunas físicas e permissões não entram nesses campos. O prompt mantém glossário lógico e evidência tipada, sem copiar as fórmulas físicas. Retirado o aviso histórico de que nenhuma consulta integrada existe; a limitação agora exige capacidades/escopo autorizados para a publicação v2.

Verificações: seleção de catálogo/envelopes/fundamentação GenAI, 210 passaram; contrato Backend, 119 passaram; consumidor/decoder/sessão do Assistente, 19 passaram. Build, fronteiras e lint frontend passaram (aviso preexistente no AuthProvider). Os testes cobrem resposta legada, rótulos novos e recusa de rótulo sem filtro correspondente. Os dois itens remanescentes do GENAI-03 ficam comprovados; isso não habilita novos domínios.

## GENAI-05 — instalação e consumo local comprovados

O executor privado existente foi reativado sem alterar sua configuração. A verificação lê o bloco final de validação do provisionador existente e o executa em uma transação `READ ONLY` na conexão operacional: não executa CREATE/ALTER/GRANT/REVOKE. O bloco verifica privilégios efetivos por coluna, escrita, CREATE/TEMP, esquemas, sequências e funções, incluindo privilégios herdados de PUBLIC. A fábrica `create_genai_gold_engine` validou a credencial privada configurada e o destino; a conexão resultante confirmou papel `venergy_genai_reader`, `default_transaction_read_only=on` e publicação `gold-csv-v2`. Saída sanitizada: `effective_acl_matches_approved_matrix=true`, `runtime_reader_and_publication_v2=true`.

A autorização da pessoa continua separada dessa inspeção administrativa: sessão, duas identidades, contexto adulterado, revogação e revalidação antes/depois da execução são exercitados pelo teste PostgreSQL público existente. Não há cache Gold servido; a obrigação de reautorizar eventual cache futuro permanece. A jornada real e a reprodução da primeira pergunta já comprovadas usam esse executor local. Os três itens do GENAI-05 ficam comprovados para esse ambiente; não declara instalação em produção.

## GENAI-06 — consumidor real e limite remanescente

O item de execução pelo orquestrador/endpoint com schema/dialeto reais e amostra autorizada está comprovado pela matriz PostgreSQL e pela jornada Gold local do GENAI-09, agora na mesma base integrada. Permanece aberto o item composto de limites de custo/cancelamento/concorrência: testes de timeout e devolução de conexão não equivalem a medir custo operacional ou comprovar cancelamento por desconexão HTTP. Essa cláusula não é encerrada pela primeira pergunta bem-sucedida.

## GENAI-02 — fonte do portal reconciliada

A fonte real `GET /api/v1/panorama`, usada pelo portal, foi exercitada no ambiente Docker `dev131-gold`, com sessão individual temporária de leitura. A competência mais recente foi obtida da API; SQL independente somou `receita_base_comparavel_reais` em `gold_v2.diagnostico_receita`, preservando a população comparável do Panorama (distinta do faturamento total GenAI). Tolerância de apresentação: R$ 0,01, sem mudar fórmula ou arredondamento da fonte. Identidade de lote e fingerprint foram comparadas ao registro de publicação; nova chamada com `expected_lote` e `expected_fingerprint` preservou o mesmo total.

Saída sanitizada: `portal_source_batch_matches_database=true`, `portal_source_total_matches_independent_sql=true`, `publication_pin_preserves_total=true`, `temporary_account_removed=true`. A conta e todas as suas sessões foram removidas em finally; nenhuma linha Gold ou permissão foi alterada. O ensaio testa a fonte efetiva do portal e os contratos existentes; não é nova revisão visual da interface. Os dois itens de regras dimensionais aprovadas e controles independentes de todos os domínios permanecem abertos.

A primeira tentativa no executor dedicado GenAI não passou: a conexão operacional não provisiona usuários e não lê o registro privado de carga exigido pelo contexto do Panorama. Isso não foi contornado com grants. A prova válida acima usou o ambiente do portal que já exercita essa fonte, sem mudar a configuração do executor. O teste intermediário com origem incompatível também não conta como aceite; todas as contas temporárias provisionadas foram removidas.

## GENAI-04 — recusas pela composição pública

A matriz pública PostgreSQL existente agora confere cinco pedidos com resultados independentes: receita paga, UC fora do escopo, últimos 12 meses sem cobertura completa, dias incompletos de competência e ranking sem suporte. Todos esclarecem ou recusam, sem resposta quantitativa e sem chamada de síntese/modelo. Executado `python -m pytest -q -p no:cacheprovider --tb=short tests/test_genai_session_postgres.py`: 1 prova integrada passou em 79,08 s, incluindo os cinco casos. As outras cláusulas compostas do cartão continuam abertas até conferir a matriz integral de dimensões, correções, contexto herdado e limites; cinco recusas não substituem toda a matriz.

## Reconferência final desta fatia

Após a extensão dos rótulos: suíte GenAI completa, **3.719 passaram e 4 skips** em 40,18 s. Backend sessão/PostgreSQL/auditoria/chat/cliente/envelopes: **130 passaram** em 75,25 s. Duas expectativas exatas do contrato demonstrativo precisaram incluir os campos opcionais novos; foram corrigidas e a suíte completa acima passou depois. Esses resultados substituem a primeira execução completa que teve duas falhas de expectativa. Nenhum requisito oficial IA foi concluído por contagem de testes.
