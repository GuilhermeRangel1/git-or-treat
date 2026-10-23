# DEV-05 — alinhamento de Inspeções ao Figma

**Objetivo:** recompor a fila e o detalhe da suspeita conforme `04 · Inspeções`, preservando os requisitos sintéticos WEB-04 e os contratos DEV-05.

**Arquitetura:** manter React, TypeScript, Tailwind, Lucide, TanStack Query e estado aplicado na URL. Reutilizar layout e componentes compartilhados apropriados; composição específica em `features/inspecoes`. Backend comportamental preservado; somente corrigir expectativa obsoleta em teste DEV-04.

**Referência:** Figma `oTjmpIBgbA7OOYb9ZmMG9K`, seção `249:12375`, fila desktop clara `15:773`, detalhe desktop claro `16:579`, fila mobile clara `195:7869`, detalhe mobile claro `195:8041` e fila/detalhe desktop escuros `16:1738`/`16:1833`. Contexto MCP completo foi obtido para os três primeiros em 23/10/2026. Detalhe mobile e frames escuros foram conferidos visualmente no navegador; não se afirma contexto MCP nem metadados de design para eles. Temas seguem tokens locais e composição equivalente.

**Spec:** solicitação atual; PRD WEB-04; `docs/contracts/inspection-dev05.md`; `docs/services/frontend.md`; `docs/architecture/frontend.md`. O protótipo orienta a apresentação; dados, pesos e cobertura vêm da API.

## Restrições globais

- Trabalhar na árvore atual `dev05`, em merge sem commit, preservando alterações existentes no índice. Não commitar, resetar ou criar outra branch.
- Execução por subagentes GPT-6 Luna/high; controlador planeja e revisa. Não delegar novamente.
- Não modificar comportamento da API ou fórmulas; avisar controlador caso isso pareça necessário.
- Manter prioridade numérica 0–1, sem inventar classes alta/média; manter UCs e números da API, sem copiar exemplos do desenho.
- Manter janela real janeiro–fevereiro/2025 e comparação não aplicada no resumo de filtros. Não anunciar recorte anual inexistente.
- A ação Criar ordem pertence a WEB-05: apresentar o espaço visual com botão desabilitado e explicação acessível, sem simular persistência ou criar ordem.
- Preservar ausência versus zero, erro versus vazio, última consulta válida após falha, cancelamento e decodificação de JSON.
- Não recriar sidebar/cabeçalho global. Evitar alterar outras páginas. Não adicionar dependências.
- Ícones do desenho são Lucide e têm equivalentes exatos instalados; marca local já corresponde ao Figma. Reutilizar esses recursos.

## Decisões de composição

1. Espaçamento vertical da página: 24 px desktop, 20 px mobile. Título 32/40 Manrope desktop, 26/34 mobile; subtítulo 14/22 DM Sans. Remover margem redundante de header, chip e relógio; usar linha de demonstração/atualização em texto discreto.
2. Fila: barra de resumo de filtros branca, raio 12, padding 16, quatro informações (Competência, Comparar com, Território, Classe), botão Ajustar filtros 44 px. Janela/valores são reais; comparação aparece como Não aplicada. Ajustes em diálogo nativo como Receita, com rascunho local, aplicar/limpar, Escape/fechar/retorno foco. Preservar município/bairro/classe/alimentador, ordenação/direção e tamanho de página.
3. Aviso azul Prioridade demonstrativa antes da fila; padding16 raio8, título14/20 e texto14/22. Usar tokens de status específicos se faltarem (alterações aditivas, sem mudar outras páginas).
4. Tabela desktop superfície sem cabeçalho/card extra, raio12, padding16; cinco colunas UC / prioridade, Motivo da suspeita, Indicador usado, Energia estimada, Ação. Colunas aproximadas Figma 15%,25%,17%,19%,restante; cabeçalhos mono12/18, linhas corpo14/22 e altura mínima56. Não usar barras, badges ou grandes botões por linha. Indicadores são rótulos da API, sem inventar percentuais. Ação sublinhada Ver evidência → com nome acessível por UC. Mobile usa registros empilhados com identificação 18/26, motivo e indicador lado a lado, energia e link abaixo; não tabela horizontal.
5. Abaixo da fila: ação escura Investigar <UC> apontando para o primeiro candidato visível, texto de ordenação/desempate e paginação compacta funcional. Sem três cartões de resumo. Contagem de resultados disponível na paginação, resumo técnico pode estar no fundamento se útil.
6. Detalhe: título e contexto UC/pontuação; linha de demonstração; painel O que motivou a investigação com janela da API, motivo, energia e orientação de verificar cadastro/medição/GD. Aviso amarelo Limite da evidência. Ações Criar ordem (desabilitada) e Voltar à fila abaixo, largura180 desktop/100%mobile, uma por linha como Figma; explicar indisponibilidade de ordens.
7. Rodapé de ambas telas: fonte sintética e link sublinhado Ver fundamentos →. Diálogo nativo acessível expõe metadados, limitações; no detalhe também os sinais/pesos, fórmula e teto da prioridade, desempate, referência/observação/horizonte/fórmula da energia e comparação de consumo existente. Não esconder os critérios de aceite sem acesso. Abrir/foco/Escape/retorno de foco obrigatórios; overlay rolável em telas pequenas.
8. Temas claros/escuros por tokens locais; preservar legibilidade e geometria; responsivo 390,768,1440,1920,2560px. Foi verificado reflow em viewport 720×512; isso não representa teste de zoom nativo de 200%.

### Orientação adicional da pessoa usuária — filtros iguais à Receita

A pessoa usuária confirmou que a barra abre um modal e solicitou explicitamente a mesma organização e os mesmos botões da página Receita. Essa referência local prevalece sobre detalhes diferentes do overlay demonstrativo do Figma: diálogo de 720px, raio16, cabeçalho com descrição e botão fechar40px, formulário com borda/raio12/padding16 e grade responsiva1/2/3 colunas. Controles têm fundo canvas e altura44. Ajustar filtros usa fundo canvas, borda control e font-semibold; Aplicar filtros usa fundo brand, texto accent-goiaba-text e altura44. Campos específicos da DEV-05 e janela fixa são preservados, sem inventar comparação/período editáveis. Referências executáveis: `ReceitaPage.tsx` e `RevenueFiltersForm.tsx`.

## Tarefa 1 — recompor frontend

Responsável: implementador Luna/high. Escopo `frontend/src/features/inspecoes/`, tokens adicionais se necessários, testes locais e regressões do roteador somente quando justificadas.

- [x] Ler skills frontend, React, Figma design-to-code e contexto local; ler os três arquivos de contexto Figma em `work/` antes de editar.
- [x] Inventariar componentes compartilhados e padrões Receita/UC; preservar o contrato da API.
- [x] Implementar a composição acima e adaptar testes de comportamento aos diálogos e registros mobile, mantendo cobertura funcional.
- [x] Testar abertura de fundamento e fórmula independente, retorno à fila com URL, filtros/aplicação/paginação, estimativa ausente, vazio, erro/refetch e Escape/foco.
- [x] Executar testes focados, lint, fronteiras, formatação e build. Não editar código de outras features para contornar falha.
- [x] Entregar relatório `work/dev05-frontend-implementation-report.md` com arquivos, comandos/resultados e pendências. Não commitar ou fazer stage.

## Tarefa 2 — reconciliar teste anterior de cobertura

Responsável: implementador Luna/high. Escopo somente `backend/tests/test_uc360_dev04.py` no teste identificado.

- [x] Ler `work/dev05-backend-validation-diagnosis.md` e contrato UC de cobertura independente.
- [x] Trocar expectativa de descartar janeiro por verificação independente de nulidade de billed_amount e conservação de paid_amount/energia cobertas, inclusive fatura com ID OUT-OF-COVERAGE.
- [x] Preservar verificações de estado parcial e comparação indisponível; não reduzir a cobertura do teste.
- [x] Executar caso focado e suíte SQLite backend (sem migrações/PostgreSQL quando não houver ambiente descartável).
- [x] Registrar resultado em `work/dev05-backend-test-report.md`. Não alterar comportamento ou documentação de métricas.

## Tarefa 3 — revisão, validação integrada e documentação

Responsável: controlador.

- [x] Revisar diff de cada tarefa em padrões e especificação, encaminhando ajustes ao mesmo implementador.
- [x] Executar gates completos frontend e backend aplicáveis; registrar versão Python local e limitações PostgreSQL/CI.
- [x] Iniciar frontend/backend sintéticos locais em portas livres e conferir fila/detalhe/fundamento/diálogo/teclado, vazios e URL com API HTTP local e fonte sintética.
- [x] Conferir screenshots em claro/escuro e viewports definidos, comparando os frames disponíveis; sem afirmar fidelidade pixel a pixel.
- [x] Atualizar contrato visual/guia, relatório datado e progresso PRD mantendo WEB-04 Em validação até Gold.
- [x] Encerrar com arquivos, testes, resultado visual e limites reais; preservar merge sem commit.
- [ ] Sincronizar Trello: pendente, pois leitura do quadro retornou `not found/no access`.

**Pendências de produto:** reconciliação/homologação Gold permanece em aberto; ela não é necessária para marcar as tarefas técnicas/documentais acima executadas e mantém WEB-04 `Em validação`. Zoom nativo 200% não foi testado; houve verificação de reflow em viewport 720×512.
