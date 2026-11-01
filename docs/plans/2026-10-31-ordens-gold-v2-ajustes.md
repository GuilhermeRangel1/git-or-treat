# Plano de ajustes e validação de Ordens com Gold v2

Data: 31/10/2026. Branch de referência: `dev13.1`.

**Objetivo:** finalizar a fatia de acompanhamento de ordens da DEV-13.1, com interface consistente com Panorama, evidência Gold v2 preservada e ciclo operacional validado.

**Execução:** usar `backend-coding-standards` e `frontend-coding-standards`; consultar `vercel-react-best-practices` para React e `supabase-postgres-best-practices` antes de mudanças SQL, migrações ou importações. Ler AGENTS das áreas, PRD, guias e contratos antes de implementar. Executar por tarefas verificáveis com revisão, usando `subagent-driven-development` ou `executing-plans` conforme o método autorizado.

## Escopo e fonte de verdade

- WEB-05: criar ordem a partir da fila, alterar estado, registrar resultado e cancelar, com transições válidas e persistência.
- WEB-07: filtros aplicados compreensíveis, URL, paginação e recorte consistentes.
- DEV-13.1: vínculo com a publicação Gold v2 real e preservação operacional entre cargas. Dependências: DEV-05/06/07/12, DE-04/06/08 e contrato de fila disponibilizado por Inspeções.
- WEB-04: validar a fronteira fila → criação → acompanhamento. Este plano não conclui toda a página Inspeções ou o aceite da estimativa individual de recuperação.
- WEB-10: preservar permissões de leitura/escrita já implementadas; a matriz futura de cargos não integra esta entrega.
- Referências: `docs/PRD.md`, `docs/contracts/inspection-orders-dev06.md`, `inspection-lifecycle-dev07.md`, `analytics-gold-dev13-1.md`, `docs/dicionario_gold.md` e guias dos serviços.
- O PDF do case, página 8, exige o ciclo das ordens. O PDF de avaliação de Design, página 6, traz os itens 5.1–5.3; a observação geral da página 7 pede hierarquia e menos informação sem finalidade.

Ordens são registros operacionais do portal. A Gold fornece a suspeita e os fundamentos congelados na criação; a lista de ordens não deve ser substituída por uma consulta à fila atual. Uma lista vazia pode ser legítima: UCs suspeitas não viram ordens automaticamente.

## Diagnóstico inicial — código e navegador

Inspeção autenticada somente leitura em `/ordens`, com sessão real e sem criar ou alterar ordens:

- O topo exibe “Ambiente demonstrativo” e atualização baseada apenas nas ordens da página corrente. Isso não representa atualização da Gold nem de todo o recorte.
- O rodapé afirma que todas as evidências são sintéticas, mesmo com suporte a snapshots Gold no código.
- O botão “Ver fundamentos” fica separado da tabela e seleciona automaticamente a primeira ordem visível.
- A ação por linha já é textual (“Ações” acompanhada do código). O apontamento de reticências precisa ser registrado como reavaliado, sem recriar um problema já resolvido.
- O formulário de filtros possui uma superfície/cartão dentro do modal. A inspeção posterior de Panorama vigente confirmou a mesma classe de superfície; diferenças de rótulo e espaçamento ainda precisavam ser conferidas.
- Há prioridade na URL/resumo, mas o formulário atual só altera UC, estado e resultado. É necessário tornar o controle coerente com o filtro aplicado.
- Fundamentos já suporta snapshot de criação versão 2; há testes Gold com contrato físico v1. É preciso comprovar o pacote físico `gold-csv-v2`, distinguindo essas duas versões.
- O guia DEV-07 ainda descreve a entrega original como exclusivamente sintética. Atualizar a distinção entre histórico da entrega e estado atual.

Nenhuma nova validação de escrita, recarga ou aceite funcional foi realizada neste planejamento.

### Ajuste do plano durante implementação

A revisão do código atual de Panorama mostrou que `FilterBar.tsx` também usa no formulário interno `rounded-xl border border-border bg-surface p-4 shadow-sm`. Portanto, o diagnóstico anterior que apontava essa superfície como diferença não corresponde à implementação vigente. Para cumprir a prioridade de fidelidade visual, Ordens deve manter a mesma composição efetiva de Panorama; a remoção isolada dessa superfície deixaria as telas divergentes. O componente Panorama permanece sem alteração.

A instrução de tabela foi refinada durante a revisão: “Fundamentos” deve ser uma coluna própria depois de “Ações”, com seis colunas desktop e alinhamento entre rótulos/células; no cartão mobile, as ações também devem ficar em linhas separadas. Esta interpretação mantém cada ação associada à mesma OS/UC e evita um grupo de controles desalinhado sob um único cabeçalho.

Outros refinamentos de aceite acordados durante a execução: a barra resumida mostra sempre quatro posições, incluindo “Prioridade” com “Todas as prioridades” quando não há filtro; filtros usam somente rótulos humanos no resumo. Na tabela, resultado longo fica limitado visualmente a duas linhas e permanece consultável no detalhe. Hash/fingerprint e referências técnicas ficam sob “Proveniência da publicação”, recolhida inicialmente. Para a prova de carga, o pacote final real é usado para reconciliação Gold→fila/API→snapshot/ordem e reload idêntico; cenários transacionais de publicação diferente, carga com falha, UC removida e concorrência usam pacotes pequenos em PostgreSQL descartável, pois já exercitam o importador real e não exigem repetir toda a carga de 1,12 GB.

## Tarefa 1 — Padronizar barra e modal de filtros

Arquivos: `frontend/src/features/ordens/OrderFilters.tsx`, `ordens-query.ts`, testes; referência visual `shared/filters/FilterBar.tsx` e `shared/ui/Modal.tsx`.

- [x] Usar o Panorama atual como referência de fundo, borda, raio, altura, espaçamento, tipografia, controles, ícones, botão de abertura e foco. Mesma aparência e comportamento, mantendo campos específicos de Ordens.
- [x] Manter na composição interna do modal a superfície/borda/sombra vigente de Panorama; alinhar título, descrição, padding, rodapé e foco. Botão de limpar usa o mesmo `RotateCcw` (`size-3.5`), variante ghost, tamanho sm e posição.
- [x] Padronizar rótulos e valores: “UC exata”, “Estado”, “Resultado” e “Prioridade”; usar “Todos os resultados” e “Todas as prioridades”, evitando “Todos” sem contexto.
- [x] Incluir prioridade no modal para alterar/remover um recorte recebido pela URL, com rótulos humanos e valores contratuais BAIXA/MEDIA/ALTA. Não confundir prioridade operacional da OS com categoria analítica da fila.
- [x] Rascunho local: abrir carrega o recorte aplicado; Cancelar/Escape descarta; Limpar restaura o rascunho padrão; somente Aplicar muda URL/consulta. Reabrir não recupera alterações canceladas.
- [x] Aplicar recorte reinicia página, preserva parâmetros suportados e remove o `order_id` transitório quando necessário para não reabrir uma ordem alheia ao novo recorte. Definir e testar esse comportamento no parser.
- [x] Mostrar todos os filtros ativos no resumo, incluindo prioridade e tamanho de página quando pertinente; valores válidos não podem aparecer como inválidos.
- [x] Preferir componentes/tokens existentes. Extrair apenas a composição compartilhada necessária; não acoplar Ordens aos filtros analíticos de Panorama nem fazer refatoração geral de outras telas.

Aceite: barra e modal visualmente iguais ao padrão de Panorama nos dois temas, com comportamento comprovado de aplicação/cancelamento/limpeza, validação e URL.

## Tarefa 2 — Limpar textos e organizar ações da tabela

Arquivos: `OrdensPage.tsx`, `OrdersTable.tsx`, `OrderActionsDialog.tsx` e testes.

- [x] Remover do topo “Ambiente demonstrativo · atualização das ordens neste recorte...” e do rodapé “Fonte: ordens registradas no portal. Evidências da fila são sintéticas, sem consulta à Gold.”
- [x] Remover o cálculo/imports de atualização sem uso após essa alteração. Conservar datas operacionais pertinentes nos detalhes/histórico e proveniência nos fundamentos da ordem.
- [x] Substituir o botão global ligado à primeira ordem por “Ver fundamentos” associado explicitamente à ordem selecionada, acessível pela respectiva linha e pelo registro mobile. Nome acessível identifica OS/UC; sem truncar a ação.
- [x] Manter “Ações” ou outro rótulo explícito associado à OS; não usar reticências decorativas nem botão sem nome compreensível. Ellipsis de carregamento não equivale a um menu de ações.
- [x] Ajustar a coluna de ações para comportar consulta de fundamentos e ação operacional sem overflow; evitar duplicar códigos longos em todos os botões se o contexto da linha já estiver claro.
- [x] Reavaliar o bloco permanente “Acompanhamento operacional”: manter somente orientação útil à tarefa, sem grande área de aviso repetitiva; destacar confirmações após ações e erros recuperáveis.
- [x] Harmonizar densidade/altura das linhas, estado, UC e resultado. Textos longos permitem consulta completa no detalhe sem ampliar toda a tabela ou cortar controles.
- [x] Garantir vazio legítimo com orientação para criar a partir da fila; distinguir “nenhuma ordem cadastrada” de “nenhuma ordem neste recorte”. Preservar filtros e caminho para limpar recorte.

Aceite: nenhuma afirmação sintética fixa na página, fundamentos inequivocamente ligados à ordem e ações legíveis em desktop/mobile.

## Tarefa 3 — Fundamentos corretos para ordens Gold v2 e legadas

Arquivos: `OrderFoundationsDialog.tsx`, `order-actions.ts`, `shared/api/orders.ts`, `backend/app/schemas/order_snapshot.py`; testes existentes e contrato Gold.

- [x] Confirmar no contrato de criação o snapshot imutável versão 2, com origem Gold, lote, fingerprint, regra, motivo e evidências efetivamente disponíveis na publicação física `gold-csv-v2`.
- [x] Validar decoder e apresentação contra resposta real v2, não apenas alterar fixtures v1. Manter suporte explícito aos snapshots antigos, manuais sem evidência e formatos desconhecidos.
- [x] Organizar detalhe em contexto operacional, fundamento da suspeita e proveniência consultável; padronizar título, campos, espaçamento, datas e modal com o portal. Usar linguagem de produto em mensagens principais.
- [x] Mostrar motivo e prioridade registrados na criação. Uma OS antiga não deve herdar motivo, categoria ou regra da fila atual.
- [x] Preservar nulo/zero e estados de recuperação. Média histórica é referência histórica, não estimativa daquela UC; apresentar método, período, intervalo e estado quando fornecidos. Não fabricar kWh recuperável.
- [x] Não rotular indiscriminadamente ordens existentes como Gold: a origem é a do snapshot daquela OS; ausência de evidência histórica permanece explícita.
- [x] Revalidar o detalhe consultado no servidor antes de exibir fundamentos; tratar erro, atualização e resposta atrasada sem trocar silenciosamente a ordem aberta.

Aceite: amostra criada com a Gold v2 confere campo a campo entre fila, snapshot persistido, API e modal; ordens antigas continuam consultáveis após mudança de publicação.

## Tarefa 4 — Comprovar ciclo operacional e filtros de ponta a ponta

Arquivos: `OrderActionsDialog.tsx`, `OrderHistory.tsx`, `ordens-query.ts`, `shared/api/orders.ts`, endpoints/serviços/repositórios de inspeções e testes de DEV-06/07.

- [x] Testar criação a partir de suspeita real v2 em banco descartável: UC, motivo, prioridade, referência, lote/fingerprint e snapshot corretos; acompanhar a OS criada pelo endpoint/ID retornado.
- [x] Testar suspeita obsoleta e ordem ativa existente em pacote pequeno do importador: resposta contratual adequada, sem duplicação, com atualização ou navegação para a ordem já criada.
- [x] Validar PENDENTE → EM_ANDAMENTO → CONCLUIDA com resultado; cancelamento permitido com confirmação OS/UC; estados finais somente consulta e transições inválidas negadas.
- [x] Conferir versão obrigatória, 409 em edição concorrente, rascunho preservado e revisão humana antes de reenviar. Falha de rede não pode produzir duplicação silenciosa.
- [x] Conferir histórico: ator autenticado, data, ação, estado, resultado/motivo e versão, após reload e reinício. Histórico legado não recebe dados inventados.
- [x] Validar leitura/escrita conforme permissões existentes no cliente e na API; leitor não altera ordens. Essa prova não conclui a matriz futura WEB-10.
- [x] Reconciliar filtros UC exata, estado, resultado, prioridade e combinações contra consulta independente dos registros operacionais. Verificar totais, ordenação determinística, paginação, página vazia, reload e link direto.
- [x] Conferir cache/invalidação após resultado, cancelamento e mudança de estado; resposta antiga não substitui nova seleção, associa fundamentos à OS errada ou apresenta recorte anterior como atual.

Aceite: efeitos persistem e aparecem na lista e histórico corretos, com comportamento permitido/negado comprovado pela API e pelo portal.

## Tarefa 5 — Provar preservação em nova carga e encerrar evidências

Arquivos: `backend/tests/test_gold_inspections_orders_postgres.py`, testes de publicação/recarga existentes, evidências DEV-13.1, contratos e PRD.

- [x] Usar PostgreSQL descartável com importador real e pacote final; criar ordem de teste com snapshot/resultado/eventos e reconciliar motivo, categoria/prioridade, posição e evidências de recuperação contra o CSV independente. A comparação precede a criação da ordem; não altera o banco local.
- [x] Exercitar recarga idêntica do pacote final e conferir ID, estado, resultado, snapshot e histórico. Nova publicação e carga que falha foram cobertas no pacote pequeno com importador real, em PostgreSQL descartável.
- [x] Demonstrar em pacote pequeno que nova publicação muda a fila atual sem reescrever evidências antigas e que UC removida não impede consultar/concluir ordem existente. Não atribuir esses cenários ao pacote final.
- [x] Aproveitar evidências reproduzíveis existentes; repetir apenas a prova insuficiente do pacote final após corrigir descoberta do CSV distribuído. Pacote pequeno foi mantido como prova separada de transações e concorrência.
- [x] Registrar volume do pacote (1,12 GB), duração observada de carga (14m34s na prova final aprovada), recorte operacional local de uma ordem, consulta de listagem pontual de 49 ms e paginação múltipla com `page_size=1` em banco isolado. Não há SLA/benchmark aprovado e não se alteraram índices.
- [x] Revisão visual em claro/escuro: 1366×768, 1280×720, 1440×900 e 390×844; filtros, tabela/linha/mobile e fundamentos conferidos. Sem overflow horizontal em mobile; teclado/Escape/foco de retorno testados sem escrita acidental. Ações, histórico e erros têm cobertura automatizada; inspeção visual do navegador foi somente leitura.
- [x] Executar testes afetados backend/frontend, limites (166 arquivos), formatação, lint e build; regressão sintética/legada executada. Resultados estão no relatório incremental. Ruff não está instalado na `.venv` do backend; arquivos Python alterados passaram pelas suítes pytest correspondentes.
- [x] Atualizar PRD, contratos DEV-06/07/Gold e guia frontend para distinguir o histórico sintético da integração Gold v2 atual; registrar evidência sanitizada e limites. Documentos-fonte privados permaneceram locais e não foram copiados para Git. O aceite do produto continua com a pessoa responsável.
- [x] Revisar nominalmente os itens 5.1–5.3 do PDF de Design e a observação geral da página 7, sem copiar os PDFs privados ao Git:
  - **5.1 — consistência dos modais:** os filtros de Ordens usam `Cancelar`, `Aplicar filtros` e `Limpar filtros`, com ícone, variante, tamanho e posição de limpar alinhados ao Panorama. A evidência visual atual cobre os modais e o retorno de foco.
  - **5.2 — reticências no botão:** a página já usa ações textuais identificadas por ordem; não há botão de reticências a corrigir. O plano registrou essa reavaliação, sem inventar uma mudança.
  - **5.3 — fundamentos associados à ordem:** “Fundamentos” é uma coluna própria após “Ações”, em cada linha/OS, e abre o detalhe da mesma ordem.
  - **Observação geral da página 7 — hierarquia e excesso de informação:** removidos o cabeçalho demonstrativo, a atualização derivada da página corrente e a afirmação fixa de evidências sintéticas; fundamentos ficam associados à OS, enquanto metadados de publicação ficam recolhidos na proveniência.
  - O vínculo registra como a implementação responde aos apontamentos de design; não equivale a aceite de produto nem altera o estado de WEB-05, WEB-07 ou DEV-13.1.

## Critério de fechamento

A fatia Ordens de DEV-13.1 pode ser fechada após revisão das cinco tarefas: criação com evidência Gold v2 reconciliada, ciclo operacional persistente, filtros corretos, modais padronizados, fundamentos por OS e preservação em carga comprovada. Falha ou ausência de evidência mantém o item pendente com causa/próximo passo.

Não declarar toda DEV-13.1, WEB-04, WEB-07 ou a página Inspeções concluída por esta fatia. Avaliar WEB-05 contra todos os seus critérios e evidências antes de propor mudança de estado no PRD.

## Restrições da execução

- Preservar as alterações locais de hooks; não incluir `.codex/hooks.json` ou `.claude/settings.json` em commits futuros desta entrega.
- Não adicionar PDFs, imagem de referência, datasets, credenciais ou capturas com dados privados ao Git. Trello foi dispensado pela pessoa usuária.
- Sem recarga destrutiva, exclusão de ordens reais ou escritas de demonstração no banco de uso local. Provas mutáveis usam ambiente descartável.
- Planejamento somente nesta entrega. Nenhum ajuste de produto, teste de mutação, status de requisito, commit ou push é realizado por este plano.
