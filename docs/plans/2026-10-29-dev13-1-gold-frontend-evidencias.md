# DEV-13.1 — evidências da integração frontend

Data: 29/10/2026, atualizado em 30/10/2026. Base `a118766`, branch `dev13.1`. Implementação Gold autorizada do [plano aprovado](2026-10-29-dev13-1-gold-frontend-plano.md). As evidências anteriores a 30/10 abaixo preservam o estado observado em cada retomada; para autenticação por sessão, valem os resultados e limites da seção final. Nenhum aceite integral WEB/DE é declarado neste registro.

## Escopo implementado e revisão

- Contratos Gold v2 validados em execução, contexto comum de lote/fingerprint e aviso de atualização coordenada. Caches analíticos são reiniciados sem apagar caches operacionais de ordens; respostas em trânsito de uma geração anterior são recusadas.
- Panorama adapta opções reais, competência inicial, valores nulos, estados de comparação, proveniência e lacunas da série; insight sintético não é consultado para explicar Gold. A revisão exigiu separar descoberta global de dados exibidos sob recorte, validar o período efetivo e preservar deep links legítimos sem aceitar markup/controles.
- Ordens interpreta snapshots v2 preservando legado/v1. Fila/detalhe apresentam categorias e evidências reais, sem converter consumo em recuperação ou categoria em score. Nova criação usa fingerprint e regra confirmados; conflitos exigem confirmação explícita; reenvio de resultado incerto conserva intenção na jornada testada.
- Operação adapta resumo, ranking e detalhe agregado, com populações separadas DEC/FEC e sem paginação fictícia de ocorrências. A descoberta de filtros usa a extensão autenticada `GET /api/v1/operations/options`; fonte sintética é identificada explicitamente por 422 `unsupported_source`, sem fallback em 401/403/503.

A primeira prova dos decoders contra HTTP real encontrou o resumo de Operação interpretando um wrapper inexistente: a API Gold retorna `data` diretamente e `definition` na raiz. Decoder e fixtures artificiais foram corrigidos para esse contrato. Revisão também exigiu navegação React Router, estados de erro/atualização e manutenção dos filtros entre ranking e detalhe. Testes que apenas reproduziam a estrutura esperada pelo cliente não foram considerados prova da integração.


- Acesso local: a implementação então revisada cobria identidade individual, permissões `orders:read`/`orders:write` e limpeza dos caches ao trocar de identidade. Esse fluxo foi substituído; suas verificações não comprovam a sessão do Backend em implementação.

## Provas observadas

- Backend: `python -m pytest -q backend/tests/test_gold_operations_http_postgres.py backend/tests/test_operations_dev08.py backend/tests/test_operations_summary.py`: **83 passaram** em PostgreSQL 16 descartável. Novo teste de rejeição explícita da fonte sintética passou em execução específica; teste HTTP Gold passou novamente após mover a composição para o serviço. Role de teste sem superusuário; nenhuma escrita no banco real.
- HTTP real somente leitura: opções retornaram **48 competências e 122 alimentadores**. O acesso de revisão tinha apenas `orders:read`; proxy frontend sem credencial retornou **401**.
- Prova temporária em Vitest/Node com Fetch HTTP real: decoders de Panorama, fila/detalhe e Operação (resumo/ranking/detalhe) passaram após a correção de formato, conferindo mesma identidade de publicação em todas as respostas. Credencial efêmera existiu apenas no processo de teste; não foi enviada ao navegador ou inserida no bundle. Nenhuma resposta foi salva como fixture/log. Script temporário removido depois da execução.
- Verificações integradas finais: `npm test -- --maxWorkers=2`: **38 arquivos, 306 testes passaram em 68,87 s**. `npm run check:boundaries`: 149 arquivos verificados; `npm run lint`: sem avisos; `npm run format:check`, `npm run build` e `npm run test:proxy`: passaram. `compileall` e `git diff --check`: passaram.


- Gates de frontend registrados antes da migração: `npm.cmd run check:boundaries` (162 arquivos), `npm.cmd run format:check`, `npm.cmd run lint`, `npm.cmd run build`, `npm.cmd run test:proxy` (1 teste) e `npm.cmd test -- --reporter=dot` (**42 arquivos, 320 testes**) passaram. Esses resultados cobrem a revisão então executada, não a autenticação por sessão atual. `npm` via PowerShell foi bloqueado pela ExecutionPolicy; comandos equivalentes `npm.cmd` concluíram normalmente.

## Ambiente de acompanhamento e bloqueios

Frontend Vite: `http://localhost:5173`; proxy para API `http://127.0.0.1:8001`, conectada à Gold existente em `127.0.0.1:55432`. Portas publicadas somente localmente. Nenhuma carga CSV ou alteração de métrica/dados reais foi feita.

Na retomada de 29/10, autenticação por sessão do Backend, migração de banco e login real ainda não tinham prova. A atualização final de 30/10 está registrada na seção abaixo.

Na retomada de 29/10, a ferramenta de navegador não disponibilizou browser nem IAB; a jornada e a inspeção visual foram feitas e registradas posteriormente em 30/10. A prova visual não homologa métricas Gold nem reconcilia a extração.

Pagamento, energia faturada independente, recuperação, atividade cadastral histórica e ocorrências individuais continuam ausentes da exportação. Prova no navegador, homologação de negócio e reconciliação Delta → CSV → API → portal mantêm os limites do aceite integral DEV-13.1 e WEB-01 a WEB-07. Nenhum commit/push desta implementação foi solicitado nesta rodada.

## Revisão final e estado do plano

A atualização de autenticação por sessão e a jornada principal foram validadas parcialmente em 30/10, sem concluir aceite integral do plano ou requisitos WEB/DE.

A revisão final preservou município nulo permitido pelo esquema físico: a descoberta mantém o alimentador sem inventar território; lista municipal contém apenas nomes conhecidos; pontos Gold conservam `municipality=null`. A suíte backend final afetada passou **85 testes**, e o frontend de Operação passou seus testes de compatibilidade com essa ausência.

A primeira suíte frontend integrada encontrou expectativas antigas de descoberta de fonte e uma regressão de validação estrutural dos filtros do Panorama. Os casos foram corrigidos sem fallback; a execução final acima passou. Em Ordens, a revisão exigiu manter o componente de intenção montado durante reinicialização da consulta, evitando perder uma chave de reenvio de resultado incerto.

Varredura dos arquivos candidatos não encontrou nomes de dataset/segredos nem padrões fortes de credenciais. O Trello oficial retornou recurso não encontrado ou sem acesso; sincronização pendente. A revisão não criou commit/push. Frontend/API de acompanhamento permanecem locais; PostgreSQL de testes e credenciais efêmeras em disco foram removidos após as verificações. A Gold real não foi recarregada ou alterada.

## Retomada de validação local — 29/10/2026

- Docker Desktop estava desligado; iniciados o motor e o contêiner PostgreSQL existente. Detectada versão `goldv1000002`, incompatível com as tabelas no schema `gold` esperadas pelo código após integrar a develop.
- Criado backup privado dentro do contêiner em `/tmp/dev131-before-validation.dump`. Aplicada a migração existente `goldv1000003` em transação, com `lock_timeout=5s`; contagens de todas as tabelas Gold e operacionais presentes foram comparadas antes/depois e permaneceram iguais. Não houve recarga CSV. Esta migração preserva a carga legada e não atribui a ela nova origem ou `publication_id`.
- API e frontend locais foram iniciados para prova Gold somente leitura. Panorama, opções/resumo/ranking de Operação, fila e pesquisa de Ordens retornaram 200; as respostas analíticas conferiram mesma versão de origem e fingerprint. Uma identidade somente de leitura recebeu 403 ao tentar escrever; nenhuma OS foi criada e nenhuma escrita de operador foi ensaiada no banco real. Essa prova é de 29/10 e não substituía a sessão do Backend; a validação posterior está abaixo.
- Inventário de automação retornou `apps=[]` e `browsers=[]` na retomada de 29/10, sem browser disponível naquela ocasião. A revisão posterior do navegador, temas e dimensões está registrada na seção final; reconciliação independente com a origem Gold permanece pendente.
- Sem commit/push nesta retomada; aceite integral DEV-13.1 e WEB/DE permanece pendente.

## Evidências finais de autenticação e revisão visual — 30/10/2026

- Backend: em `backend/`, `python -m pytest tests -q -p no:cacheprovider`, contra o banco descartável `grid360_auth_fullsuite_test`: **534 passaram, 66 foram pulados, 1 aviso Starlette**.
- Banco operacional local: a migração `8f6a1c2d9e30` foi aplicada somente ao alvo local selecionado após backup privado; contagens Gold/operacionais permaneceram iguais. Contas artificiais reader/operator foram provisionadas em `work/local-auth/credentials.txt`, ignorado pelo Git.
- Frontend: suíte completa informada pelo principal aprovou **327 testes em 43 arquivos** antes dos ajustes cosméticos finais; o comando exato dessa execução não foi informado. Após remoção de controles, cópias e uma linha a pedido da pessoa usuária, `npm run build` e `npm run format:check` passaram. A suíte completa não foi repetida depois desses ajustes.
- Matriz original de **22 combinações** passou antes dos ajustes cosméticos. A jornada no navegador contra API real passou login/cookie, permissões reader/operator, reload, logout, replay e credencial inválida.
- Capturas e revisão visual abrangeram 1366×768, 1280×720 e 1440×900. Não foram fornecidos nomes de arquivos de captura neste registro.
- WEB-10 permanece `Pendente`: perfis e restrições de telas/ações por cargo não cobrem todo o escopo. WEB-11 também continua `Pendente`. A busca pelo quadro/cartão Trello retornou vazia; sincronização pendente.
