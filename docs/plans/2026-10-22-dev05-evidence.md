# DEV-05 — evidência de validação

Data: 22/10/2026. Branch de entrega: `dev05`. Base: `origin/develop` em `54534a7b79f5eef3739a3055b8289261854fd5de`, com DEV-01 já integrada. As referências locais `develop` (`7f7de669ef4db63d6d799a1402f028f459adf2d4`) e `dev02` (`c571f31070b2e1d27d242f58e00dacccc07d962b`) permaneceram inalteradas. Não houve merge, push ou publicação em develop.

## Verificações automatizadas

No diretório `backend`, ambiente existente `venv`, Python 3.14.3 local:

```powershell
.\venv\Scripts\python.exe -m pytest -q
.\venv\Scripts\python.exe -m compileall -q app tests scripts
```

Resultado: **119 passed, 1 skipped**, compilação sem erro. O teste ignorado exige PostgreSQL descartável; não houve alteração de schema ou migração. A versão local difere do Python 3.12 declarado para CI/Docker, cujas execuções não foram realizadas nesta sessão. Aviso de depreciação Starlette/httpx já presente, sem falha de teste.

`tests/test_inspection_queue_dev05.py` valida API real com fonte sintética: controle independente 0,92/45 kWh, estimativa nula, paginação/filtros/vazio, erros 422/404/503, null last nas duas direções, empate e zero conhecido. Verifica também que uma fonte marcada como real não recebe a regra demonstrativa.

No diretório `frontend`:

```powershell
npm.cmd test -- --reporter=dot
npm.cmd run check:boundaries
npm.cmd run lint
npm.cmd run format:check
npm.cmd run build
```

Resultado: **85 testes passaram em 6 arquivos**; limites de importação, lint, formatação, TypeScript e bundle aprovados. Os testes novos cobrem abertura/retorno com recorte, filtros e ordenação enviados à API, paginação, fila vazia, estimativa ausente, carregamento/erro/repetição, link direto inexistente, query inválida, decoder e falha de atualização preservando cache com aviso. Os testes de navegação foram ajustados para permitir consultas somente nas jornadas implementadas.

O sandbox bloqueou rename no cache temporário do Vite e deixou a inicialização Python sem progresso; testes foram executados com permissão fora dele. A formatação normalizou LF no checkout conforme `.gitattributes`, sem mudança de conteúdo nos arquivos fora da tarefa. `git diff --check` passou.

## Conferência com API real em execução

Backend em `127.0.0.1:8055` com `ANALYTICS_SOURCE=synthetic`, SQLite em memória e CORS para `127.0.0.1:5185`; Vite em `127.0.0.1:5185` com `VITE_API_URL` apontando para essa API. Nenhum arquivo `.env` foi alterado. Configuração limitada à demonstração; as ordens não foram exercitadas.

A consulta HTTP de `/api/v1/inspections/queue/UC-1004` retornou prioridade 0,92, pesos 0,60/0,32, referência 90, observação 45, horizonte 1 e estimativa 45 kWh, com regra `dev05-v1` e proveniência demonstrativa explícita.

No navegador integrado, foram percorridos:

1. Fila padrão com UC-1004 e UC-1002; prioridade, motivo e estimativa disponíveis na tabela.
2. Detalhe UC-1004 com soma dos pesos e expressão `max(0; 90 − 45) × 1 = 45 kWh`.
3. Uma UC por página; avançar da página 1 à 2 apresentou UC-1002 com estimativa indisponível.
4. Detalhe UC-1002 mostrou referência comparável ausente, leitura 82 kWh, regra e limitações. Retorno manteve `page_size=1&page=2`.
5. Filtro Olinda retornou zero suspeitas e reiniciou a página em 1, com mensagem que não conclui ausência de perdas.
6. Remoção do filtro e prioridade crescente apresentou UC-1002 antes de UC-1004.
7. Temas escuro/claro e detalhe em viewport 390 × 844 conferidos visualmente. O viewport temporário foi restaurado. Não é uma certificação completa de acessibilidade/contraste ou de todos os níveis de zoom.

As capturas nativas foram inspecionadas durante a sessão. O Figma MCP não estava disponível; a referência consultada foi o registro local dos frames de Inspeções `15:773` / `16:1738`, com reutilização da identidade, tokens e layout existentes. Não se afirma conferência atual pixel a pixel do arquivo Figma.

## Standards

A revisão local em agente separado encontrou um P2: atualização silenciosa em segundo plano e ocultação de dados válidos após falha de refetch. Corrigido com aviso de atualização, aviso de falha mantendo cache e teste de regressão observável. Nenhum outro problema acionável de padrões foi identificado nessa revisão inicial.

## Spec

A revisão local em agente separado não encontrou desvio funcional no checklist DEV-05. Confirmou reprodução dos controles pela interface e ausência de dependência da DEV-02. Essa revisão foi estática; os testes e a conferência de navegador acima complementam a evidência.

## Limites e próxima etapa

WEB-04 fica **Em validação**, pois o cenário é sintético. Homologar pesos, sinais, referência comparável, GD, sazonalidade, cobertura e horizonte com o time; depois reconciliar com a Gold e implementar o adaptador real. A regra demonstrativa falha explicitamente em fonte não demonstrativa. Ordens de campo pertencem à DEV-06/WEB-05.

MCP Trello não está conectado nesta sessão: sincronização do cartão WEB-04 pendente. Nenhum dado real, segredo ou imagem do enunciado foi incluído. A homologação de produto e a CI remota ficam pendentes; não foi criado PR nesta entrega local.

## Revisão visual após capturas fornecidas — 22/10/2026

Acesso de leitura ao Figma aceitou a autenticação fornecida, mas o editor falhou ao abrir os frames. A pessoa usuária então forneceu duas capturas da seção Inspeções, usadas como referência autorizada para a adaptação. Nenhuma credencial ou captura foi salva no repositório. O resultado preserva a identidade local e acrescenta resumo do recorte, filtros recolhíveis, indicadores e barra de pontuação na fila, além de destaque do motivo e cartões de fundamento no detalhe. Não se afirma reprodução pixel a pixel ou inspeção estrutural por Figma MCP.

O backend agora devolve `data.summary` calculado antes da paginação e `items[].signals` com rótulos/pesos. Controle sem filtros: duas UCs, maior pontuação 0,92, uma com estimativa e uma indisponível. `page_size=1&page=2` apresenta UC-1002 com pontuação 0,61 e estimativa ausente, mantendo o resumo completo 2/0,92/1/1. Olinda: contagens zero e maior pontuação nula. O teste HTTP novo verifica esses controles literais e a consistência das opções/indicadores.

Mesmos comandos das seções anteriores: backend **120 passed, 1 skipped** e compileall aprovado; frontend **85 testes aprovados**, fronteiras (56 arquivos), lint, formatação e build aprovados. Os testes de interface também verificam abertura dos filtros e preservação do resumo ao paginar; o decoder recusa resumo contraditório. A revisão Standards não encontrou bloqueadores e sugeriu remover validação duplicada dos sinais no detalhe, corrigida. A revisão Spec não encontrou desvios.

Conferência no navegador com backend sintético em 8055 e Vite em 5185: temas claro/escuro, cabeçalho de detalhe, pontos 0,92/0,61, projeção 45 kWh e ausência, filtros expansíveis e paginação. Viewport 390 × 844: leitura do detalhe, controles e tabela com rolagem horizontal/instrução visível. Os valores continuam no mesmo período/fonte. O viewport temporário é restaurado após a validação. A verificação não certifica todos os níveis de zoom ou conformidade completa de acessibilidade.

Quality gate compartilhado executado na raiz com entrada `cwd` do projeto e `hook_event_name: Stop`, usando `backend/venv/Scripts/python.exe .hooks/quality_gate.py`. Primeira passada apontou somente formatação do último ajuste do cabeçalho; corrigida com Prettier. Segunda passada terminou com código 0 e saída `{}`. Skills e hooks foram consultados, sem mudanças em sua configuração. `git diff --check` também passou.

Quality gate compartilhado executado na raiz com entrada `cwd` do projeto e `hook_event_name: Stop`, usando `backend/venv/Scripts/python.exe .hooks/quality_gate.py`. Primeira passada apontou somente formatação do último ajuste do cabeçalho; corrigida com Prettier. Segunda passada terminou com código 0 e saída `{}`. Skills e hooks foram consultados, sem mudanças em sua configuração. `git diff --check` também passou.
