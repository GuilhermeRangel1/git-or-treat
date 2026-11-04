# Panorama — fidelidade à camada 01

## Escopo autorizado

Refatorar `/panorama` a partir de `origin/develop` (`4cd8c36`), na branch `refactor/panorama-prototipo`. Referência: seção `249:12229` do arquivo Figma `oTjmpIBgbA7OOYb9ZmMG9K`, frames claro `15:164`, escuro `16:1129` e mobile `195:3781`. Requisitos WEB-01 e WEB-07; integração IA-04 preservada.

A pessoa usuária definiu duas exceções à reprodução do protótipo: manter a barra/modal de ajustar filtros no padrão do portal e manter os insights da IA. Nos esclarecimentos, pediu posicionamento e largura útil como Receita, remoção dos termos `m-1`/`m-12` e retirada completa do desenho decorativo que tinha animação; o gráfico de receita permanece. Valores, competências e unidades continuam vindo do contrato mensal existente; os valores anuais/bimestrais ilustrativos do Figma não substituem a API.

## Execução

Dois implementadores GPT-6 Luna/high, conforme solicitado, trabalham em arquivos distintos; o agente principal revisa a integração e a aparência.

1. Reorganizar os quatro indicadores principais conforme o protótipo: valor faturado, energia faturada, consumo apurado e base de UCs; manter as oito métricas e suas definições nos fundamentos.
2. Reproduzir o painel de receita com uma série de valor faturado e alternativa tabular em modal, usando competências mensais reais e escala legível em telas estreitas.
3. Retirar o ornamento do topo e seu código/CSS, sem retirar o gráfico mensal de receita. Preservar o layout compartilhado, os temas e os componentes existentes.
4. Compor ações para Receita, Continuidade e Assistente, aviso de continuidade e fundamentos rastreáveis. Não criar estados de falha simulados na página operacional.
5. Aplicar filtros por modal com rascunho, aplicar/cancelar e retorno de foco, no mesmo padrão usado por Receita/Inspeções.

## Verificação planejada

- Revisar diferenças e conferir escopo, contratos e tratamento de ausência, parcial, erro e vazio.
- Executar testes afetados e gates do frontend.
- Exercitar API real em `http://localhost:5173/panorama`, filtros e seus rascunhos, tabela da série, fundamentos, navegação e temas.
- Conferir 320/390/768/1440 px e ausência de overflow horizontal. Registrar capturas em `work/`, sem versioná-las.
- Registrar resultados no PRD e no guia frontend; WEB-01 continua em validação enquanto não houver reconciliação com Gold.

## Limites

Esta mudança não altera backend, fonte analítica, contratos de IA nem configuração de credenciais. A indisponibilidade do serviço IA observada no ambiente local permanece apresentada pelo cartão existente. `frontend/package-lock.json` contém alteração anterior ao trabalho e deve permanecer fora desta entrega.

## Evidências — 25/10/2026

- Dois implementadores GPT-6 Luna/high executaram página/filtros e gráfico/ornamento. Revisão do agente principal corrigiu alinhamento, largura útil, semântica da navegação, precisão monetária/energética, escala do gráfico, dados anteriores após falha e refinamentos mobile. O pedido final removeu o ornamento, seus estilos e assets; nenhum arquivo de produção da IA foi modificado.
- `npm.cmd test -- --reporter=dot --maxWorkers=2`: 158 testes aprovados em 20 arquivos. Após os refinamentos, `npm.cmd test -- src/features/panorama src/shared/filters --reporter=dot --maxWorkers=2`: 35 testes aprovados em seis arquivos. Incluem rascunho/aplicação/cancelamento, URL inválida, falha inicial, atualização falha preservando dados, insight contextual, fundamentos, zero e centavos na série.
- Build/tipos, lint, fronteiras em 103 arquivos e formatação aprovados. `git diff --check` aprovado. Nenhuma dependência adicionada; a alteração preexistente do lockfile foi preservada.
- Navegador com API real em `http://localhost:5173/panorama`: indicadores HTTP 200; Recife muda valor faturado de R$ 76.500 para R$ 38.000, URL e recarga preservam recorte. Rascunho não altera indicadores; Escape descarta e devolve foco. Tabela mostra R$ 39.800 e R$ 38.000, soma R$ 77.800, para Recife; oito métricas e fórmula de receita conferidas nos fundamentos. O desenho decorativo não está no DOM e o gráfico mensal permanece.
- Capturas locais `work/panorama-final-{320,390,768,1440}-{light,dark}.png` e `work/panorama-filter-{320,390}-{light,dark}.png`: página e modal sem overflow horizontal. Capturas inspecionadas nos dois temas, incluindo desktop e mobile. A barra usa a largura disponível do layout, como Receita (1.120 px úteis na viewport de 1.440 px), com os mesmos alinhamentos laterais. Emulação de viewport não comprova zoom nativo a 200%.
- O serviço IA local respondeu 503; a mensagem, os dados observados, o retry e a análise detalhada foram preservados. A suíte simula respostas válidas para verificar o contrato/contexto existente. Não se declara homologação do provedor nem reconciliação Gold.
- Trello: tentativa de leitura do quadro oficial retornou recurso não encontrado ou sem acesso. Sincronização pendente. WEB-01 permanece `Em validação`; WEB-07 mantém seu estado no PRD.

## Fechamento da revisão DEV-02

A [revisão final por padrões e requisitos](2026-10-25-dev02-panorama-review.md) confirmou o checklist fornecido na conversa. Um P3 por eixo foi corrigido e reavaliado: formatação de data duplicada e ambiguidade da base zero no KPI principal. A verificação final aprovou 160 testes em 21 arquivos, lint, fronteiras em 105 arquivos, formatação e build. A API conferiu com as 21 linhas canônicas do backend em oito recortes, sem usar o helper legado do frontend como oráculo. Histórico de voltar/avançar e recarga foram exercitados no navegador com recorte e comparação. Não há achados abertos na revisão; o aceite continua restrito à base sintética.
