# DEV-05 — alinhamento visual e evidências disponíveis

**Data:** 23/10/2026. **Requisito:** WEB-04 permanece `Em validação`; WEB-05 permanece `Pendente`. Este registro consolida a referência visual e as evidências automatizadas/visuais reproduzidas. A implementação foi revisada nos pontos descritos abaixo; não se afirma equivalência pixel a pixel nem reconciliação com Gold.

## Referência visual

Arquivo Figma `oTjmpIBgbA7OOYb9ZmMG9K`, seção `04 · Inspeções` (`249:12375`):

| Estado | Nó | Evidência disponível |
| --- | --- | --- |
| Fila desktop claro | `15:773` | Contexto MCP completo recebido em 23/10/2026. |
| Detalhe desktop claro | `16:579` | Contexto MCP completo recebido em 23/10/2026. |
| Fila mobile claro | `195:7869` | Contexto MCP completo recebido em 23/10/2026. |
| Detalhe mobile claro | `195:8041` | Conferido visualmente no navegador após limite do MCP. |
| Fila e detalhe desktop escuros | `16:1738`, `16:1833` | Conferidos visualmente no navegador após limite do MCP; não se afirma contexto MCP nem metadados para os frames escuros. |

O contrato vigente descreve a apresentação autorizada em [inspection-dev05.md](../contracts/inspection-dev05.md): cinco colunas na fila desktop, registros verticais sem tabela horizontal no mobile, diálogo de filtros no padrão Receita e fundamentos auditáveis. Não se usam os exemplos numéricos nem classes alta/média do protótipo. A janela demonstrativa é janeiro–fevereiro/2025, sem comparação anual; `Criar ordem` permanece desabilitada, pois a operação pertence à WEB-05.

As referências orientam estrutura visual, não dados de negócio. Os valores exibidos vêm da API HTTP local configurada para a fonte sintética; prioridade e energia não usam exemplos do Figma. `Criar ordem` segue desabilitada intencionalmente porque ordens pertencem a WEB-05.

## Backend

O relatório local `work/dev05-backend-test-report.md` registra a execução integral já realizada:

- Ambiente: Python 3.11.9, `backend/.venv/Scripts/python.exe`.
- Comando: `python.exe -m pytest -q` (a partir de `backend/`).
- Resultado: **197 passaram, 2 ignorados**, 1 aviso Starlette/httpx.
- Os dois testes ignorados dependem de `TEST_POSTGRES_URL`, ausente; não foi usado banco externo.
- A alteração de código relacionada foi somente a expectativa do teste DEV-04 de cobertura. Não houve mudança ao comportamento de API, serviço, schema ou fórmula de DEV-05.

## Frontend e jornada no navegador

O relatório local `work/dev05-frontend-implementation-report.md` registra os gates concluídos:

- Suíte completa antes da correção Standards P2: `npm.cmd test -- --reporter=dot` — **130 testes em 16 arquivos**. Após a correção do resumo de alimentador, a suíte isolada passou com **131 testes em 16 arquivos**; a suíte focada passou **13/13**.
- `npm.cmd run lint`, `npm.cmd run check:boundaries` (**87 arquivos**), `npm.cmd run build` (TypeScript e Vite 8.3.4) e `npx.cmd prettier --check` para os oito arquivos alterados — todos passaram.
- Controlador executou também `npm.cmd run format:check` global — passou.

Jornada confirmada pelo controlador no navegador com o portal em `localhost:5173` e API HTTP local na porta `8000`, configurada para a fonte sintética DEV-05: abrir modal mantém URL inalterada enquanto edita rascunho; alterar direção para ascendente e depois descendente mantém o valor descendente; Escape fecha e devolve foco; reabrir descarta rascunho não aplicado; aplicar Olinda atualiza a URL e mostra fila vazia; limpar filtros restaura as duas UCs. `page_size=1` aplicado pelo modal, navegação da página 1 à 2 abre UC-1002 com referência ausente/estimativa nula; `Ver fundamentos` fecha por Escape e devolve foco; voltar preserva exatamente a URL da página 2. UC-1004 mostra `min(1; 0,6 + 0,32) = 0,92`, energia `max(0; 90 − 45) × 1 = 45 kWh` e comparativo 90/45 kWh/mês. `Criar ordem` permanece desabilitada.

### Ajuste de contexto do filtro Alimentador — revisão Standards

A revisão registrou um P2: selecionar um alimentador filtrava a API, mas o resumo não deixava visível o recorte. A correção exibe a segunda linha `Alimentador: <valor>` logo abaixo de Território após aplicar e remove a linha ao limpar filtros. O teste de regressão aplica `?alimentador=AL-03`, verifica o parâmetro na URL e na requisição, e confirma que limpar remove a linha e o parâmetro. Após a correção: testes focados **13/13** e suíte frontend **131/131 em 16 arquivos**; lint, fronteiras (87 arquivos), formatação global e build passaram. A validação manual no navegador confirmou `Alimentador: AL-03` a 1440 e 390 px, sem overflow (`scrollWidth == clientWidth`, 1440/375). Limpar pelo modal voltou à URL `/inspecoes?page=1`, removeu a linha e restaurou as duas UCs. Capturas locais: `work/dev05-feeder-fixed-1440.png` e `work/dev05-feeder-fixed-390.png`.

Uma execução concorrente inicial da suíte frontend expirou no teste preexistente de `/dev/contratos`; a repetição integral isolada passou com 131 testes. A suíte backend foi repetida após a correção: **197 passaram, 2 ignorados** em 12,59 s; os dois skips seguem condicionados à configuração PostgreSQL de teste ausente.

## Comparação com Receita e acessibilidade dos modais

Os estilos computados foram comparados entre Receita e Inspeções em claro e escuro, com igualdade JSON confirmada: acionador com mesmo fundo, cor, borda, font-weight 600, altura 44 px e raio 12 px; modal com largura 720 px e raio 16 px; botão de aplicação com fundo/cor correspondentes, font-weight 600 e altura 44 px; controles com mesmo fundo e altura 44 px. Cores do botão de aplicação: tema claro fundo `rgb(168, 63, 77)` e texto `rgb(255, 255, 255)`; tema escuro fundo `rgb(238, 135, 148)` e texto `rgb(33, 26, 28)`. Capturas locais: `work/dev05-compare-{receita|inspecoes}-filters-{light|dark}.png`.

Modal mobile verificado em 390×844 nos dois temas: `HTMLDialogElement` reportou `modal=true`; largura 337,2 px, menor que a área interna de 375 px; sem overflow horizontal (`scrollWidth == clientWidth == 320`); altura do diálogo 759,6 px, com rolagem vertical para filtros (conteúdo 818 px) e fundamentos (2319 px). O conteúdo de fundo não recebeu foco enquanto o modal estava aberto; Escape fechou e devolveu foco em ambos os temas. `document.hasFocus=false` ao atravessar a área do navegador corresponde à perda de foco nativa da janela durante automação, não a foco escapando do diálogo. Capturas: `work/dev05-final-filters-{theme}-390.png` e `work/dev05-final-foundations-{theme}-390.png`.

Reflow em viewport redimensionado 720×512: sem overflow horizontal (`scrollWidth == clientWidth == 705`), modal 666,8×460,8 px e conteúdo com 514 px de altura rolável; captura `work/dev05-reflow-720x512.png`. É reflow em janela reduzida, não teste de zoom nativo de 200%.

As capturas de fila/detalhe em claro/escuro e 390, 768, 1440, 1920 e 2560 px estão em `work/dev05-final-queue-{theme}-{width}.png` e `work/dev05-final-detail-{theme}-{width}.png`. Não foi observado overflow horizontal; mobile usa registros empilhados e desktop a tabela de cinco colunas. No detalhe, o H1 mede 68 px em mobile e 40 px em desktop. Após o ajuste final de espaçamento entre parágrafos e posição da nota WEB-05, as capturas do detalhe em 390 e 1440 px nos dois temas foram renovadas.

## Limites remanescentes

- Reconciliação da regra demonstrativa com Gold e homologação de produto.
- Sincronização do cartão Trello WEB-04: a leitura do quadro retornou `not found/no access`; não foi possível atualizar o cartão.

WEB-04 permanece em validação até reconciliar a regra e as métricas demonstrativas com Gold e obter homologação de produto. Não se afirma fidelidade pixel a pixel. Capturas e outros artefatos em `work/` são locais/ignorados e não foram adicionados ao repositório.
