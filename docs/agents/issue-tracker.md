# Rastreador de trabalho

## Trello: acompanhamento dos requisitos

O quadro [V-Energy Grid 360 — Entregas obrigatórias](https://trello.com/b/eD8tWRha/v-energy-grid-360-entregas-obrigat%C3%B3rias) espelha os requisitos obrigatórios DE, WEB, IA e ENT do `docs/PRD.md`. Cada cartão usa o ID estável do PRD. O quadro é privado e requer a autorização OAuth da pessoa usuária em cada cliente MCP.

O PRD continua sendo a única fonte de verdade para escopo, critérios, estado oficial e evidências. Sempre que uma mudança de trabalho atualizar um ID no PRD:

1. Atualize o estado do requisito e seu Registro de progresso no PRD, com as evidências exigidas pelo workflow.
2. Localize o cartão pelo ID e atualize sua descrição para refletir o estado atual do PRD e apontar a evidência verificável (PR, commit, arquivos e comandos/resultados pertinentes).
3. Use `mark_done` no Trello somente quando o estado no PRD for `Concluído`. Para os demais estados, mantenha o cartão aberto e escreva o estado atual no início da descrição.
4. Se o MCP não estiver conectado ou a atualização falhar, não altere o PRD por causa disso. Registre no resumo da tarefa que a sincronização do Trello ficou pendente para retomada.

O quadro é um espelho operacional, não um gatilho de conclusão: alterações manuais no Trello não concluem requisitos no PRD. Não copie dados do dataset, credenciais ou evidências sensíveis para os cartões.

## Tickets técnicos detalhados

O quadro privado [GenAI — Gold real](https://trello.com/b/Vlnppr77/genai-gold-real) decompõe a adaptação do núcleo, chat e insights à Gold em cartões `GENAI-01` a `GENAI-16`. Esses IDs são técnicos e não substituem os IDs IA/DE/WEB do PRD. Ao executar esses cartões, siga o [guia GenAI e Gold](genai-gold.md), confira dependências e anexe evidências sem dados sensíveis. Avanço nesse quadro não conclui automaticamente o requisito no quadro obrigatório.

Use `.scratch/<tema>/issues/<NN>-<slug>.md` para decompor trabalho técnico criado por `to-tickets`, com bloqueios reais e ID(s) do PRD. Esses tickets podem detalhar subtarefas, mas não substituem o cartão do requisito nem `docs/PRD.md`. Tickets locais concluídos só alteram o PRD após a evidência de qualidade exigida.
