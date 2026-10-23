# ADR-0008 — Exploração demonstrativa da receita por extremos

**Data:** 2026-10-21

**Estado:** aprovada pela autorização de execução do desenho/plano DEV-03 nesta sessão; implementação e aceite em andamento.

**IDs do PRD afetados:** preparação de WEB-02 e WEB-07; suporte a ENT-01.

## Contexto

A DEV-01 fornece contrato e cálculo sintéticos de Receita, mas sua página ainda não tem exploração funcional. O dicionário Gold não tem definições reais aprovadas. É necessário exercitar filtros, decomposição e reconciliação sem apresentar a demonstração como diagnóstico do case.

## Opções consideradas

1. Interface estática com valores do protótipo: permite conferir aparência, mas não comprova filtros, cobertura ou consistência HTTP.
2. Antecipar as duas janelas anuais e o modelo físico Gold: depende de competências e definições ainda não verificadas.
3. Evoluir a API sintética existente, mantendo comparação explícita dos extremos e partições por município, bairro e classe, com cobertura e qualidade publicadas.

## Decisão

Adotar a opção 3, conforme [desenho](../design/2026-10-21-dev03-design.md), [plano](../plans/2026-10-21-dev03-plan.md) e [contrato Receita 1.1.0](../contracts/revenue-dev03.md). A pessoa usuária autorizou dois implementadores GPT-6 Luna/high e esta sessão como revisora dos padrões e dos requisitos.

Receita usa valor faturado e energia faturada. Preço médio observado é sua razão, distinto do reajuste tarifário homologado. A decomposição aritmética mantém preço, volume e interação explícitos; usa precisão decimal, ROUND_HALF_UP e ajuste de arredondamento separado. Ausência não vira zero sem cobertura completa declarada pela fonte.

Adotar limiar demonstrativo de cinco UCs distintas com fatura por extremo para exibir percentual. Valores absolutos conhecidos continuam visíveis com aviso de base pequena. O limiar é política de apresentação provisória, sem pretensão estatística ou regulatória.

Revisão de 21/10/2026, autorizada pela solicitação de corrigir os achados confirmados: separar disponibilidade financeira e energética. Valor faturado completo sustenta delta/percentual elegível e reconciliação em BRL mesmo com energia incompleta; delta em kWh depende apenas da comparação energética. Preço observado e decomposição exigem as bases comparáveis pertinentes, conforme o contrato. A estrutura JSON 1.1.0 é preservada; trata-se de corrigir o bloqueio indevido de uma grandeza pela ausência de outra, sem homologar definições Gold.

Receitas e variações absolutas dos recortes devem somar o total do mesmo universo. Efeitos de preço/volume recalculados separadamente em cada grupo não são aditivos entre níveis quando o mix muda; a interface deve explicar esse limite. Grupos não comparáveis e diferenças não atribuídas ficam explícitos.

Na revisão do retorno pelos recortes em 21/10/2026, adotar remoção explícita dos refinamentos descendentes: Município remove bairro/classe refinados; Bairro remove classe refinada; Total remove todos os refinamentos. Filtros base, inclusive classe e alimentador, período e agrupamento permanecem. Esta regra substitui a interpretação anterior do retorno intermediário, reduzindo restrições inesperadas sem apagar escolhas base da pessoa usuária.

## Consequências e verificação

- A jornada Receita evolui para 1.1.0; demais endpoints preservam 1.0.0. O frontend valida JSON em execução e usa filtros base/refinamentos na URL.
- Fonte sintética explícita permanece atrás do repositório analítico, sem migração ou carga Gold nesta etapa.
- Controle independente: R$ 80.000 → R$ 76.500 e 100.000 → 90.000 kWh; delta −R$ 3.500, volume −R$ 8.000, preço +R$ 5.000 e interação −R$ 500.
- Aceite exige HTTP, interação de usuário e navegador com API real, incluindo retorno ao total, limites e casos de cobertura. Design ou teste isolado não conclui requisitos.
- Rever janelas anuais do PRD §7.2, população, métrica, método, mix, fonte tarifária e limiar quando o dicionário Gold estiver disponível. Atualizar dicionário/contrato/consumidores e reconciliar Gold → API → portal antes de concluir WEB-02, WEB-07 ou ENT-01.
