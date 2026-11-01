# Consolidação dos cartões GenAI na Gold v2

## Aceite do GENAI-02 — 01/11/2026

Nova execução de `observe_domain_readiness` no PostgreSQL do ambiente `dev131-gold`, com a competência mais recente lida da própria publicação, confirmou `passed` para C01/C02/C03/C04/C10/C11/C12/C13/C14/C15. O observador foi chamado sem controles aprovados e sua saída foi reduzida a estados, sem valores de negócio, identificadores ou registros. Depois dessa execução, a pessoa usuária aprovou expressamente as regras documentadas e esses controles para a entrega local. A aprovação foi registrada no dicionário e no cartão; não altera a configuração de runtime automaticamente.

Receita, bairro e consumo têm períodos fechados no recorte verificado. Atendimento mensal e DEC/FEC continuam sem cobertura certificada nesse recorte; controles passados não os tornam utilizáveis. As tolerâncias e casos de zero/nulo/ausência/parcial existentes permanecem conforme `gold-readiness.md` e as regressões de domínio. Com a conferência API/portal já comprovada e esse aceite, GENAI-02 tem **11/11** itens técnicos para o lote local, sem concluir automaticamente requisitos oficiais ou habilitar capacidades candidatas.

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

## Estado consolidado e limites preservados

| Cartão | Estado técnico local |
| --- | --- |
| GENAI-02 | 11/11: regras e dez controles aprovados expressamente para o lote local; cobertura insuficiente continua bloqueada. |
| GENAI-03 | Itens técnicos de vocabulário comprovados nesta consolidação; expansão de escopo para outros domínios continua separada. |
| GENAI-04 | Matriz pública ampliada conforme o fechamento abaixo; comparações/ranking sem suporte esclarecem. |
| GENAI-05 | Itens técnicos de credencial e grants comprovados no ambiente Gold local; não equivale a implantação em produção. |
| GENAI-06 | Limites estruturais, janela, recursos PostgreSQL, tempo e concorrência reunidos no fechamento abaixo; benchmark operacional continua separado. |

GENAI-01 e GENAI-09 já tinham todos os itens comprovados. GENAI-07 e GENAI-08 têm todos os itens técnicos comprovados para a primeira fatia. Os estados finais dos GENAI-02/04/06 constam nas seções de aceite desta consolidação; as etapas intermediárias abaixo permanecem como histórico. Benchmark de carga e cancelamento por desconexão HTTP não são presumidos.

## GENAI-03 — vocabulário público versionado

O contexto aplicado conserva `metric` e as chaves de `filters` como identificadores lógicos. Os campos opcionais `metric_label`, `metric_definition` e `filter_labels` transportam rótulos/definição do perfil efetivamente usado pelo planejador. O catálogo Backend já confere igualdade de rótulo, definição e unidade com esse perfil em `test_gold_catalog_backend_contract.py`; o portal consome os textos recebidos, sem outra tabela de tradução. Os rótulos de filtro só podem referenciar filtros aplicados existentes. As dimensões do trecho quantitativo também usam os rótulos do perfil.

O decoder anterior continua aceitando respostas sem esses campos e a tela usa o ID como fallback. O Backend deve ser atualizado antes da GenAI que publica os campos, pois os modelos antigos recusam extras; o portal novo aceita os dois formatos. A definição é acessível no título do recorte. Fórmulas, colunas físicas e permissões não entram nesses campos. O prompt mantém glossário lógico e evidência tipada, sem copiar as fórmulas físicas. Retirado o aviso histórico de que nenhuma consulta integrada existe; a limitação agora exige capacidades/escopo autorizados para a publicação v2.

Verificações: seleção de catálogo/envelopes/fundamentação GenAI, 210 passaram; contrato Backend, 119 passaram; consumidor/decoder/sessão do Assistente, 19 passaram. Build, fronteiras e lint frontend passaram (aviso preexistente no AuthProvider). Os testes cobrem resposta legada, rótulos novos e recusa de rótulo sem filtro correspondente. Os dois itens remanescentes do GENAI-03 ficam comprovados; isso não habilita novos domínios.

## GENAI-05 — instalação e consumo local comprovados

O executor privado existente foi reativado sem alterar sua configuração. A verificação lê o bloco final de validação do provisionador existente e o executa em uma transação `READ ONLY` na conexão operacional: não executa CREATE/ALTER/GRANT/REVOKE. O bloco verifica privilégios efetivos por coluna, escrita, CREATE/TEMP, esquemas, sequências e funções, incluindo privilégios herdados de PUBLIC. A fábrica `create_genai_gold_engine` validou a credencial privada configurada e o destino; a conexão resultante confirmou papel `venergy_genai_reader`, `default_transaction_read_only=on` e publicação `gold-csv-v2`. Saída sanitizada: `effective_acl_matches_approved_matrix=true`, `runtime_reader_and_publication_v2=true`.

A autorização da pessoa continua separada dessa inspeção administrativa: sessão, duas identidades, contexto adulterado, revogação e revalidação antes/depois da execução são exercitados pelo teste PostgreSQL público existente. Não há cache Gold servido; a obrigação de reautorizar eventual cache futuro permanece. A jornada real e a reprodução da primeira pergunta já comprovadas usam esse executor local. Os três itens do GENAI-05 ficam comprovados para esse ambiente; não declara instalação em produção.

## GENAI-06 — registro intermediário de consumidor e limites

O item de execução pelo orquestrador/endpoint com schema/dialeto reais e amostra autorizada foi comprovado pela matriz PostgreSQL e pela jornada Gold local do GENAI-09. A primeira pergunta bem-sucedida não encerrava sozinha os limites de custo/cancelamento/concorrência. A revisão final abaixo confere o texto do critério e as evidências em conjunto; cancelamento por desconexão HTTP e benchmark operacional não são exigências adicionais implícitas desse item.

## GENAI-02 — fonte do portal reconciliada (registro intermediário)

A fonte real `GET /api/v1/panorama`, usada pelo portal, foi exercitada no ambiente Docker `dev131-gold`, com sessão individual temporária de leitura. A competência mais recente foi obtida da API; SQL independente somou `receita_base_comparavel_reais` em `gold_v2.diagnostico_receita`, preservando a população comparável do Panorama (distinta do faturamento total GenAI). Tolerância de apresentação: R$ 0,01, sem mudar fórmula ou arredondamento da fonte. Identidade de lote e fingerprint foram comparadas ao registro de publicação; nova chamada com `expected_lote` e `expected_fingerprint` preservou o mesmo total.

Saída sanitizada: `portal_source_batch_matches_database=true`, `portal_source_total_matches_independent_sql=true`, `publication_pin_preserves_total=true`, `temporary_account_removed=true`. A conta e todas as suas sessões foram removidas em finally; nenhuma linha Gold ou permissão foi alterada. O ensaio testa a fonte efetiva do portal e os contratos existentes; não é nova revisão visual da interface. Os dois itens de regras dimensionais aprovadas e controles independentes de todos os domínios permanecem abertos.

A primeira tentativa no executor dedicado GenAI não passou: a conexão operacional não provisiona usuários e não lê o registro privado de carga exigido pelo contexto do Panorama. Isso não foi contornado com grants. A prova válida acima usou o ambiente do portal que já exercita essa fonte, sem mudar a configuração do executor. O teste intermediário com origem incompatível também não conta como aceite; todas as contas temporárias provisionadas foram removidas.

## GENAI-04 — registro intermediário de recusas públicas

A matriz pública PostgreSQL existente agora confere cinco pedidos com resultados independentes: receita paga, UC fora do escopo, últimos 12 meses sem cobertura completa, dias incompletos de competência e ranking sem suporte. Todos esclarecem ou recusam, sem resposta quantitativa e sem chamada de síntese/modelo. Executado `python -m pytest -q -p no:cacheprovider --tb=short tests/test_genai_session_postgres.py`: 1 prova integrada passou em 79,08 s, incluindo os cinco casos. As outras cláusulas compostas do cartão continuam abertas até conferir a matriz integral de dimensões, correções, contexto herdado e limites; cinco recusas não substituem toda a matriz.

## Reconferência final desta fatia

Após a extensão dos rótulos: suíte GenAI completa, **3.719 passaram e 4 skips** em 40,18 s. Backend sessão/PostgreSQL/auditoria/chat/cliente/envelopes: **130 passaram** em 75,25 s. Duas expectativas exatas do contrato demonstrativo precisaram incluir os campos opcionais novos; foram corrigidas e a suíte completa acima passou depois. Esses resultados substituem a primeira execução completa que teve duas falhas de expectativa. Nenhum requisito oficial IA foi concluído por contagem de testes.

## Continuação GENAI-04 — matriz quantitativa pública (registro intermediário)

O mesmo teste PostgreSQL agora percorre cinco perguntas positivas pela rota pública, com sessão, SQL restrito e síntese: sinônimo faturamento, grafia de município em minúsculas, correção explícita de cidade, filtro sem GD e classe residencial, além de zero observado. As expectativas de métrica/filtros, janela mensal, ausência de agrupamento/ordem, teto de linhas e medida são literais; o plano recebido na síntese deve ser idêntico ao plano produzido.

Quatro recusas adicionais cobrem múltiplas cidades, unidade incompatível, município desconhecido e GD contraditória. Medida nula é verificada após execução, como esclarecimento sem número; a síntese desse estado é permitida e não equivale a gerar uma resposta quantitativa. A prova de revogação agora envia pergunta de acompanhamento com histórico e exige 403 antes do planejamento.

A fixture usa `RESIDENCIAL` e GD `Não`, conforme o domínio do dicionário v2. As tentativas iniciais identificaram `N` incorreto na fixture e uma pergunta de consumo sem a capacidade aprovada pelo gate artificial; não foram ampliados grants ou prontidão para contorná-las. Também foi corrigida a expectativa de que nulo não passaria pela síntese. Nenhuma dessas tentativas falhas conta como aceite.

Essa ampliação não comprova a matriz integral de bairro/alimentador/períodos ou os controles de outros domínios. O cancelamento por desconexão e as aprovações dimensionais permanecem separados.

Verificação final: em `backend/`, `python -m pytest -q -p no:cacheprovider --tb=short tests/test_genai_session_postgres.py`, com as duas DSNs de teste apontando para PostgreSQL 16 descartável: **1 passou em 124,11 s**, incluindo a matriz, autorização, privacidade, rollback, concorrência e rotação existentes. Ruff E4/E7/E9/F dos dois arquivos alterados e `git diff --check` passaram. O item original de ambiguidade/grafia/base zero/período parcial/recortes sem suporte fica comprovado na interface pública; GENAI-04 passa a **15/20**, sem conclusão integral ou alteração dos estados oficiais IA.

## Fechamento GENAI-04 — 20/20

A matriz integrada existente foi ampliada, sem outro interpretador ou executor, para todos os grupos de comportamento pendentes:

| Critério | Evidência pelo fluxo público Backend → GenAI → PostgreSQL → síntese |
| --- | --- |
| Plano entregue à fonte | Métrica, filtros canônicos, ausência de agrupamento/ordem e teto de linhas conferidos; plano recebido pela síntese idêntico ao produzido. Ranking sem suporte esclarece. |
| Dimensões autorizadas | Município, bairro, classe, GD e alimentador executados; UC sem capacidade e conflitos/unidade incompatível/desconhecidos esclarecem sem ampliar o recorte. Bairro e DEC têm valores literais independentes. |
| Contexto e qualidade | Acompanhamento troca município e conserva classe/GD/período; revogação com histórico resulta em 403 antes de planejar. Zero responde, nulo esclarece e lacuna não produz número parcial. |
| Períodos | Último ano usa exatamente onze meses adicionais mais janeiro existente, com competências/valores esperados independentes; dados temporários removidos e janela incompleta esclarece. Pagamento, recorte diário e comparação não suportada não viram outra medida ou percentual. |
| Matriz e regressão | Casos representativos da matriz versionada atravessam a composição pública; a regressão completa conserva os perfis e os casos anteriormente corrigidos. Não é implementação de ranking ou percentual sem suporte. |

A prova encontrou uma falha real: `TESTE`, classe presente no vocabulário dinâmico, era reconhecida dentro do identificador completo `AL-TESTE`. O interpretador agora usa o valor completo para absorver esse fragmento; menção separada da classe continua aplicada e nomes idênticos entre dimensões continuam ambíguos. Duas regressões específicas conferem os dois comportamentos. Bairro/alimentador receberam dados e aprovação de capacidade exclusivamente artificiais na fixture; nenhum grant ou gate de produção foi ampliado.

## Fechamento GENAI-06 — 10/10

O Backend agora reaplica, antes da conexão e também na borda executora, o teto de janela do perfil Gold: diferença entre datas de no máximo `366 * 5` dias, além do teto estrutural de 1.200 competências. A aritmética foi alinhada à do núcleo. Um plano adulterado com fingerprint recalculado e janela maior é negado sem SQL; a fronteira exata tem teste dirigido. A leitura de cobertura também evita avançar o calendário após o último mês.

O critério restante exige limites de custo além do resultado limitado, cancelamento no banco quando suportado e recuperação. As evidências reunidas são: máximo de 20 filtros/20 valores por filtro/10 dimensões; compilação de identificadores aprovados sem SQL livre, CTE ou JOIN; 100 linhas e 16.384 bytes; timeout SQL de até 5 s consumindo saldo global de 35 s; papel com 8 conexões; pool de uma conexão sem overflow; `work_mem=4MB`, `temp_file_limit=16MB`, `lock_timeout=2s` e transação ociosa limitada a 5 s. Os parâmetros efetivos são conferidos na conexão PostgreSQL. Contenção cancela no servidor com SQLSTATE `57014`, inclusive em duas consultas simultâneas; rollback e devolução ao pool são comprovados, e a consulta seguinte recupera o resultado. A nona conexão é negada; liberar uma vaga permite reconectar.

Assim, o item composto fica comprovado pela janela, complexidade, recursos e tempo de execução, além dos limites de saída. Cancelamento imediato por desconexão HTTP e benchmark operacional do GENAI-15 continuam fora dessa evidência; não eram cláusulas adicionais do item. As afirmações intermediárias acima de que esses ensaios impediam o fechamento ficam superadas por esta revisão do texto do cartão.

## Verificações do fechamento

- GenAI: `python -m pytest -q -p no:cacheprovider --tb=short`: **3.721 passaram, 4 skips**, 41,57 s; inclui as regressões de sobreposição de dimensões.
- Backend/PostgreSQL 16 descartável: `python -m pytest -q -p no:cacheprovider --tb=short tests/test_genai_session_postgres.py tests/test_genai_executor.py tests/test_genai_plan.py tests/test_genai_planning_metadata.py tests/test_genai_client.py tests/test_genai_deadline.py`: **109 passaram**, 169,58 s.
- Após alinhamento da contagem de dias, `python -m pytest -q -p no:cacheprovider --tb=short tests/test_genai_executor.py`: **9 passaram**, incluindo os dois lados da fronteira. Ruff dos arquivos alterados e diff-check passaram.
- Revisões independentes de padrões e especificação: nenhum bloqueio funcional; corrigidas a contagem de dias e as referências documentais de pendências intermediárias.

Os três cartões técnicos GENAI-02/04/06 ficam concluídos para esta entrega local. Isso não altera os estados oficiais IA nem certifica cobertura inexistente ou implantação de produção. Novas alterações permanecem locais até autorização de commit/push.
