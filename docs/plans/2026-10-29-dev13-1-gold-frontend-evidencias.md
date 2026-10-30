# DEV-13.1 — evidências da integração frontend

Data: 29/10/2026. Base `a118766`, branch `dev13.1`. Implementação autorizada do [plano aprovado](2026-10-29-dev13-1-gold-frontend-plano.md). Execução por três subagentes GPT-6 Luna/high (Panorama, Ordens/Inspeções e Operação), integração comum e revisão pelo principal. Nenhum aceite integral WEB/DE é declarado neste registro.

## Escopo implementado e revisão

- Contratos Gold v2 validados em execução, contexto comum de lote/fingerprint e aviso de atualização coordenada. Caches analíticos são reiniciados sem apagar caches operacionais de ordens; respostas em trânsito de uma geração anterior são recusadas.
- Panorama adapta opções reais, competência inicial, valores nulos, estados de comparação, proveniência e lacunas da série; insight sintético não é consultado para explicar Gold. A revisão exigiu separar descoberta global de dados exibidos sob recorte, validar o período efetivo e preservar deep links legítimos sem aceitar markup/controles.
- Ordens interpreta snapshots v2 preservando legado/v1. Fila/detalhe apresentam categorias e evidências reais, sem converter consumo em recuperação ou categoria em score. Nova criação usa fingerprint e regra confirmados; conflitos exigem confirmação explícita; reenvio de resultado incerto conserva intenção na jornada testada.
- Operação adapta resumo, ranking e detalhe agregado, com populações separadas DEC/FEC e sem paginação fictícia de ocorrências. A descoberta de filtros usa a extensão autenticada `GET /api/v1/operations/options`; fonte sintética é identificada explicitamente por 422 `unsupported_source`, sem fallback em 401/403/503.

A primeira prova dos decoders contra HTTP real encontrou o resumo de Operação interpretando um wrapper inexistente: a API Gold retorna `data` diretamente e `definition` na raiz. Decoder e fixtures artificiais foram corrigidos para esse contrato. Revisão também exigiu navegação React Router, estados de erro/atualização e manutenção dos filtros entre ranking e detalhe. Testes que apenas reproduziam a estrutura esperada pelo cliente não foram considerados prova da integração.


- Acesso local: frontend OIDC usa sessão individual em memória, injeta Bearer no transporte, diferencia 401 de 403 e limita ações operacionais por `orders:read`/`orders:write`. Logout/troca de identidade limpa caches; após refresh silencioso, o token é aceito somente se o `sub` continuar sendo o da sessão solicitante. Callback é idempotente sob StrictMode. Evento OIDC tardio após logout não foi exercitado separadamente.

## Provas observadas

- Backend: `python -m pytest -q backend/tests/test_gold_operations_http_postgres.py backend/tests/test_operations_dev08.py backend/tests/test_operations_summary.py`: **83 passaram** em PostgreSQL 16 descartável. Novo teste de rejeição explícita da fonte sintética passou em execução específica; teste HTTP Gold passou novamente após mover a composição para o serviço. Role de teste sem superusuário; nenhuma escrita no banco real.
- HTTP real somente leitura: opções retornaram **48 competências e 122 alimentadores**. O acesso de revisão tinha apenas `orders:read`; proxy frontend sem credencial retornou **401**.
- Prova temporária em Vitest/Node com Fetch HTTP real: decoders de Panorama, fila/detalhe e Operação (resumo/ranking/detalhe) passaram após a correção de formato, conferindo mesma identidade de publicação em todas as respostas. Credencial efêmera existiu apenas no processo de teste; não foi enviada ao navegador ou inserida no bundle. Nenhuma resposta foi salva como fixture/log. Script temporário removido depois da execução.
- Verificações integradas finais: `npm test -- --maxWorkers=2`: **38 arquivos, 306 testes passaram em 68,87 s**. `npm run check:boundaries`: 149 arquivos verificados; `npm run lint`: sem avisos; `npm run format:check`, `npm run build` e `npm run test:proxy`: passaram. `compileall` e `git diff --check`: passaram.


- Retomada OIDC: `npm.cmd run check:boundaries` (162 arquivos), `npm.cmd run format:check`, `npm.cmd run lint`, `npm.cmd run build`, `npm.cmd run test:proxy` (1 teste) e `npm.cmd test -- --reporter=dot` (**42 arquivos, 320 testes**) passaram. A suíte inclui callback sob StrictMode, transporte/401, permissões e refresh com identidade diferente. `npm` via PowerShell foi bloqueado pela ExecutionPolicy; comandos equivalentes `npm.cmd` concluíram normalmente.

## Ambiente de acompanhamento e bloqueios

Frontend Vite: `http://localhost:5173`; proxy para API `http://127.0.0.1:8001`, conectada à Gold existente em `127.0.0.1:55432`. Portas publicadas somente localmente. Nenhuma carga CSV ou alteração de métrica/dados reais foi feita.

Frontend OIDC foi implementado para o provedor local documentado em `docs/contracts/local-oidc-dev13-1.md`, sem credenciais persistidas no browser e sem injecao de credencial pelo proxy. A configuracao operacional do provedor, o login real e a jornada Gold autenticada no browser ainda nao foram comprovados nesta retomada. **A etapa de acesso e a ativacao Gold autenticada no navegador permanecem pendentes**; nao se declara aceita a etapa 1 nem o plano DEV-13.1 integral.

O recurso de navegador desta sessão não disponibilizou browser nem IAB. Portanto não há evidência visual de temas/responsividade/teclado no navegador, nem alegação de jornada Gold completa no browser. Testes de componentes e aceitação dos JSONs reais não substituem essa verificação.

Pagamento, energia faturada independente, recuperação, atividade cadastral histórica e ocorrências individuais continuam ausentes da exportação. OIDC, prova no navegador, homologação de negócio e reconciliação Delta → CSV → API → portal mantêm os limites do aceite integral DEV-13.1 e WEB-01 a WEB-07. Nenhum commit/push desta implementação foi solicitado nesta rodada.

## Revisão final e estado do plano

A etapa 1 permanece parcial: o cliente frontend OIDC e o transporte autenticado estão implementados e cobertos pelos gates. A configuração local do provedor foi validada por HTTP na retomada abaixo; a jornada autenticada no navegador permanece pendente. As etapas 2–4 têm código e testes revisados; a etapa 5 tem gates automatizados e prova de contratos com HTTP real, mas não tem inspeção visual no navegador. Portanto a implementação ainda não recebe aceite integral do plano ou dos requisitos WEB/DE.

A revisão final preservou município nulo permitido pelo esquema físico: a descoberta mantém o alimentador sem inventar território; lista municipal contém apenas nomes conhecidos; pontos Gold conservam `municipality=null`. A suíte backend final afetada passou **85 testes**, e o frontend de Operação passou seus testes de compatibilidade com essa ausência.

A primeira suíte frontend integrada encontrou expectativas antigas de descoberta de fonte e uma regressão de validação estrutural dos filtros do Panorama. Os casos foram corrigidos sem fallback; a execução final acima passou. Em Ordens, a revisão exigiu manter o componente de intenção montado durante reinicialização da consulta, evitando perder uma chave de reenvio de resultado incerto.

Varredura dos arquivos candidatos não encontrou nomes de dataset/segredos nem padrões fortes de credenciais. O Trello oficial retornou recurso não encontrado ou sem acesso; sincronização pendente. A revisão não criou commit/push. Frontend/API de acompanhamento permanecem locais; PostgreSQL de testes e credenciais efêmeras em disco foram removidos após as verificações. A Gold real não foi recarregada ou alterada.

## Retomada de validação local — 29/10/2026

- Docker Desktop estava desligado; iniciados o motor e o contêiner PostgreSQL existente. Detectada versão `goldv1000002`, incompatível com as tabelas no schema `gold` esperadas pelo código após integrar a develop.
- Criado backup privado dentro do contêiner em `/tmp/dev131-before-validation.dump`. Aplicada a migração existente `goldv1000003` em transação, com `lock_timeout=5s`; contagens de todas as tabelas Gold e operacionais presentes foram comparadas antes/depois e permaneceram iguais. Não houve recarga CSV. Esta migração preserva a carga legada e não atribui a ela nova origem ou `publication_id`.
- `scripts/start-gold-oidc.ps1` iniciou o provedor local, API e frontend. Portal `http://localhost:5173`; API `http://127.0.0.1:8001`; Keycloak `http://localhost:8082/realms/grid360`. Credenciais artificiais permanecem somente em `work/local-oidc/credentials.txt`.
- Prova privada `backend/venv/Scripts/python.exe work/dev131-oidc/probe.py`: login Authorization Code + PKCE de `reader` e `operator` passou; permissões conferidas. Panorama, opções/resumo/ranking de Operação, fila e pesquisa de Ordens retornaram 200 para ambos. As respostas analíticas Gold conferiram mesma versão de origem e fingerprint. A tentativa do leitor de criar ordem com corpo vazio recebeu 403; nenhuma OS foi criada e nenhuma escrita do operador foi ensaiada no banco real.
- Verificação HTTP do Vite: raiz e módulo do callback retornaram 200; módulo transformado importa `useSession.ts`. Proxy `/api/v1/panorama` sem token retornou 401.
- Inventário de automação retornou `apps=[]` e `browsers=[]`. Login visual, renderização, filtros interativos, temas, responsividade, teclado, logout e expiração no navegador permanecem sem comprovação. A prova HTTP não substitui navegador nem reconciliação independente com a origem Gold.
- Sem commit/push nesta retomada; aceite integral DEV-13.1 e WEB/DE permanece pendente.
