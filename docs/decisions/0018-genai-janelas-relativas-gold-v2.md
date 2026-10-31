# ADR-0018 — Janelas relativas na cobertura mensal Gold v2

- **Estado:** Proposta implementada no núcleo; validação de Dados e Backend pendente.
- **Data:** 31/10/2026.
- **Contexto:** O contrato de planejamento já recebe competências mensais por métrica no envelope Gold v2, mas o planejador deixava frases relativas como texto sem limites. Assim, o executor poderia interpretar períodos de modo diferente ou ampliar silenciosamente o recorte.
- **Decisão proposta:** Resolver frases relativas pela competência mensal mais recente do lote: `último ano`/`últimos 12 meses` incluem essa competência e as onze anteriores; `mês passado` escolhe a competência imediatamente anterior; `ano passado` é o ano civil anterior ao ano da competência mais recente; `este ano` vai de janeiro à competência mais recente; `último trimestre`/`últimos três meses` são as três competências mais recentes. Limites de data são primeiro e último dia dos meses, ambos inclusivos, com granularidade mensal. Toda competência esperada deve constar na cobertura. Lacuna ou cobertura vazia gera esclarecimento, sem encurtar janela ou interpolar.
- **Alternativas consideradas:** Data do servidor como âncora; enviar a frase não resolvida ao executor; completar lacunas ou reduzir a janela. Todas poderiam mudar o significado ou incluir período sem evidência.
- **Consequências:** O plano lógico fica reproduzível e vinculado à cobertura do lote. O Backend deve calcular e validar a cobertura da mesma publicação; precisa interromper execução se lote ou cobertura mudarem. `kind: none` não gera calendário e só permite métrica que declare frase acumulada.
- **Limites:** Cobertura recebida descreve competências presentes no lote e não certifica completude do inventário da origem. Uma janela anual parcial ou lacuna exige esclarecimento; não se infere valor zero. Comparações não suportadas continuam pedindo as duas janelas ou esclarecimento.
- **Validação pendente:** Dados deve confirmar a semântica de `mês passado`, janelas anuais e trimestrais e calendário de competência; Backend deve confirmar os limites inclusivos e repassar a cobertura mensal e valores lógicos das dimensões da mesma publicação. Até essas confirmações e integração com executor Gold real, GENAI-04 não está concluído.

Contrato técnico: [genai-query-execution.md](../contracts/genai-query-execution.md), itens B2 e B5.
