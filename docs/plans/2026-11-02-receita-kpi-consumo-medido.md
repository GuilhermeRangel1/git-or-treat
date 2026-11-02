# Receita: substituir o KPI de energia faturada por consumo medido

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans para executar este plano por tarefa. Delegação somente conforme autorização vigente da pessoa usuária.

**Goal:** mostrar consumo medido observado no lugar do cartão de energia faturada indisponível na página Receita.

**Architecture:** acrescentar `measured_energy_kwh` aos snapshots comparativos da API e consumir o campo no cartão existente. Reutilizar agregações e cobertura já existentes; manter a análise preço × volume nas suas bases comparáveis.

**Tech Stack:** FastAPI, Pydantic, SQLAlchemy, PostgreSQL/Gold v2, React, TypeScript, Vitest e pytest.

**Spec:** decisão aprovada nesta conversa; [PRD](../PRD.md), WEB-01/02/07 e ENT-01; [dicionário Gold](../dicionario_gold.md); PDF privado `Case_Final_V_Energy_Grid_360.pdf`, seções 5.2 (p. 8) e 5.4 (p. 9).

## Decisões e limites

- Nome do cartão: **Consumo medido**. Unidade: **kWh**, com formatação pt-BR e duas casas decimais.
- Manter a posição do cartão e o comportamento comparativo atual: valor do mês final, “Antes” com o mês inicial, identificação da competência final. Não apresentar a soma do intervalo como se fosse o valor mensal.
- Gold v2: usar `consumo_total_kwh` no agregado territorial; com filtro de alimentador, usar a projeção mensal `consumo_kwh`, como a consulta existente. Incluir consumo observado mesmo sem fatura.
- Valor faturado continua usando `receita_total_reais`. Preço observado e decomposição continuam usando receita e consumo da base comparável; não dividir receita total por consumo total.
- Consumo medido não representa energia faturada. Remover o cartão vazio não comprova a queda de energia faturada mencionada na abertura do PDF; essa limitação permanece no diagnóstico obrigatório ENT-01.
- Preservar os campos públicos de energia faturada com sua semântica atual, inclusive `null` na Gold; não renomear esses campos para transportar consumo.
- Usar as skills `backend-coding-standards` e `frontend-coding-standards`; na execução React, aplicar também as recomendações pertinentes de `vercel-react-best-practices`.
- Escopo restrito a Receita. Sem migração, recarga Gold, alteração de banco, nova dependência ou mudança nos cartões de Panorama/UC 360.
- Este documento é planejamento. Não altera o status de conclusão de requisitos; implementação, commit e push dependem da próxima solicitação.

## Pontos de revisão

1. Zero observado deve aparecer como `0,00 kWh`; ausência permanece “Indisponível”.
2. Consumo com faturamento ausente deve continuar visível; cobertura financeira não pode bloquear a medida física.
3. Consumo parcial mostra valores conhecidos com qualificação acessível, sem afirmar fechamento/completude.
4. Município, bairro, classe e alimentador devem produzir o mesmo consumo no cartão e na série para cada competência.
5. Valores longos e estados mistos de disponibilidade devem caber no cartão, nos dois temas e em largura móvel.

## Tarefa 1 — Contrato e snapshots de consumo medido

**Arquivos:**
- `backend/app/schemas/analytics.py`: modelo `RevenueSnapshot`.
- `backend/app/services/gold_revenue.py`: `snapshot()` e `comparison()`.
- `backend/app/services/revenue_analytics.py`: `_comparison_summary()`.
- `backend/app/repositories/gold.py`: referência da agregação existente em `revenue_groups()`; alterar apenas se a reconciliação demonstrar necessidade.
- Testes: `backend/tests/test_gold_revenue_v2_real.py`, `backend/tests/test_gold_revenue_coverage.py` e `backend/tests/test_revenue_dev03.py`.

**Interface produzida:** `data.comparison.initial.measured_energy_kwh` e `data.comparison.final.measured_energy_kwh`, números finitos ou `null`; mesma estrutura nos snapshots dos recortes.

- [ ] Adicionar casos de contrato para consumo inicial/final conhecido, zero, ausência e disponibilidade independente do faturamento.
- [ ] Acrescentar `measured_energy_kwh: float | None = None` ao schema, preservando compatibilidade de produtores existentes durante a alteração.
- [ ] Na Gold, somar os valores não nulos de `row['energy']` da competência em `snapshot()`; lista sem valores conhecidos resulta em `null`. Manter qualificação de cobertura parcial.
- [ ] Preencher `measured_energy_change_kwh` da Gold pela diferença final menos inicial quando ambos forem conhecidos; caso contrário, `null`. Não adicionar outro cartão nem percentual.
- [ ] No modo sintético, preencher os snapshots com os valores medidos dos extremos já usados em `_comparison_summary()`. Não reutilizar energia faturada como consumo medido.
- [ ] Confirmar que a série mensal e o snapshot da mesma competência coincidem, inclusive com filtro de alimentador e leituras sem faturas.
- [ ] Executar em `backend/`: `.venv/Scripts/python.exe -m pytest tests/test_gold_revenue_v2_real.py tests/test_gold_revenue_coverage.py tests/test_revenue_dev03.py`. Usar os ambientes descartáveis exigidos pelos testes; não apontar `TEST_POSTGRES_URL` para o banco local de uso.

## Tarefa 2 — Decoder e cartão de Receita

**Arquivos:**
- `frontend/src/features/receita/contract.ts`: tipo `RevenueSnapshot` e decoder `snapshot()`.
- `frontend/src/features/receita/RevenueSummary.tsx`: segundo `MetricCard`.
- `frontend/src/features/receita/ReceitaPage.test.tsx` e `signed-values.test.tsx`: cenários/fixtures afetados.

**Interface consumida:** os dois novos campos da tarefa 1; manter `coverage.measured_energy_kwh` como origem da qualificação da medida.

- [ ] Adicionar `measured_energy_kwh: number | null` ao tipo. Validar número finito ou `null` no decoder; normalizar campo ausente para `null` para tolerar resposta de backend anterior durante atualização.
- [ ] Trocar o rótulo “Energia faturada” por “Consumo medido” e ligar valor/“Antes” aos snapshots medidos final/inicial.
- [ ] Manter competência, formatação, estrutura de quatro cartões, fontes e comportamento responsivo existentes.
- [ ] Se a cobertura de consumo for parcial, identificar “Consumo observado”/“Dados parciais” em texto curto acessível junto ao cartão. Não usar o status financeiro do snapshot para inferir a cobertura física.
- [ ] Ajustar apenas textos da página que se refiram ao cartão substituído. Preservar a explicação essencial sobre preço observado, base comparável e indisponibilidade de energia faturada nos detalhes pertinentes.
- [ ] Cobrir no frontend: medido diferente do faturado, zero, ausente, inicial ausente/final conhecido, campo novo ausente, valor muito longo e retorno do filtro sem valor de recorte anterior.
- [ ] Executar em `frontend/`: `npm.cmd test -- src/features/receita/ReceitaPage.test.tsx src/features/receita/signed-values.test.tsx`; `npm.cmd run lint`; `npm.cmd run check:boundaries`; `npm.cmd run build`. Conferir formatação dos arquivos alterados com Prettier.

## Tarefa 3 — Rastreabilidade, reconciliação real e aceite

**Arquivos:** `docs/contracts/revenue-dev03.md`, `docs/services/backend.md`, `docs/services/frontend.md` e `docs/PRD.md`.

- [ ] Atualizar contrato e guias para distinguir o KPI físico medido, o valor faturado total e a base comparável usada por preço × volume.
- [ ] Resolver no texto vigente do PRD a orientação anterior de manter obrigatoriamente o cartão de energia faturada. Registrar a decisão aprovada, sem apagar o histórico e sem declarar equivalência entre as medidas.
- [ ] Registrar que a substituição mantém a análise física/financeira de WEB-02, mas não comprova a premissa inicial de queda da energia faturada do PDF. Manter essa ressalva para ENT-01; não marcar requisitos como concluídos somente pela troca.
- [ ] Com sessão individual e Gold v2 ativa, conferir `GET /api/v1/revenue` e a tela. Reconciliar snapshots com a série e com agregações SQL somente leitura dos mesmos meses/filtros, incluindo um caso com alimentador.
- [ ] Inspecionar o cartão em desktop/móvel, claro/escuro; validar carregamento, erro, vazio, disponibilidade parcial e navegação por filtros. Nenhum dado sensível deve ser copiado para relatório ou captura versionada.
- [ ] Registrar no progresso do PRD os arquivos, comandos realmente executados, resultados e limites da evidência; sincronizar o cartão do requisito no tracker se conectado e aplicável.

## Critério de entrega

O segundo cartão de Receita mostra **Consumo medido** dos meses comparados, reconciliado com Gold v2 e com a série mensal sob os mesmos filtros. Ausência, zero e parcialidade continuam distintos. Valor faturado, preço observado e decomposição preservam suas bases próprias. Contrato, documentação e verificações acompanham a mudança, sem presumir disponibilidade de energia faturada ou aceite integral do diagnóstico do case.
