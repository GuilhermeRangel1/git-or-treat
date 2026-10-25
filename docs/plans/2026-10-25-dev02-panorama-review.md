# DEV-02 — revisão final do Panorama

Data: 25/10/2026. Base fixa: `4cd8c367083e12ceca21161b87588ee1473b9779`, origem da branch `refactor/panorama-prototipo`. Revisão da árvore de trabalho, incluindo os novos componentes ainda não commitados; `git diff 4cd8c36 -- frontend/src docs`. Não havia commits posteriores à base no início da revisão. Lockfile e imagens locais da pessoa usuária excluídos do escopo.

## Checklist e aceite da DEV-02

| Item fornecido pela pessoa usuária | Resultado | Evidência |
| --- | --- | --- |
| Período, comparação e recortes pertinentes | Atendido | Competência mensal, mês anterior, mesmo mês do ano anterior, sem comparação, município e classe. Modal padronizado com rascunho e aplicação explícita. |
| URL, recarga e voltar/avançar | Atendido | Aplicação atômica pelo hook; teste do histórico e percurso real com Recife/Residencial, troca da comparação, dois retornos, avanço e recarga. |
| KPIs e série com unidade, definição, atualização e comparação | Atendido | Quatro KPIs principais; oito métricas com unidade, comparação e definição/fórmula nos fundamentos; atualização e fonte no topo; série mensal de receita faturada em R$ mil com alternativa tabular e valores exatos em R$. |
| Faturado/pago e consumido/faturado distintos | Atendido | Grandezas e fórmulas diferentes, com rótulos próprios; receita paga acessível nos fundamentos, consumo e energia faturada em cartões separados. |
| Carregamento, erro, vazio, incompleto e base zero | Atendido | Testes de carregamento/contrato, erro inicial com retry, atualização falha mantendo dados identificados, Rural vazio, maio parcial e base zero sem percentual inventado. Ausência no ano anterior difere de comparação desativada. |
| Componentes compartilhados conforme surgem | Atendido | Reuso de Button/Modal e filtros/hook existentes. Componentes exclusivos de métricas, série, fundamentos e atualização ficam na feature. Exceção de ownership de `shared/analytics` e `shared/filters` preservada conforme arquitetura. |

O aceite específico da DEV-02 usa a base **sintética**: mudanças de filtro alteram a consulta e os números exibidos, que conferem com os controles canônicos. Isso não conclui a reconciliação Gold de WEB-01 nem a validação de todas as jornadas de WEB-07.

## Standards

Revisão independente GPT-6 Luna/high com `frontend-coding-standards`, arquitetura local, padrões React e heurísticas da skill `code-review`.

- P3, heurística de código duplicado: formatação da atualização repetida em PanoramaPage e PanoramaStatus. **Corrigido** por `panorama-format.ts`; revisor confirmou encerramento, sem novo bloqueador.
- Nenhuma violação documentada acionável identificada. Checagens de lint/fronteiras/formatação complementam a revisão, sem substituí-la.

## Spec

Revisão independente GPT-6 Luna/high, usando o checklist DEV-02 fornecido na conversa e as decisões visuais aprovadas.

- P3: base anterior zero aparecia como “Sem comparação” no cartão principal. **Corrigido**: “N/D · Base anterior zero”; ausência de registros comparativos e opção sem comparação têm mensagens distintas. `PanoramaMetricCard.test.tsx` cobre esses três casos e um valor positivo de centavos em período parcial. Revisor confirmou encerramento, sem novo bloqueador.
- Oito métricas no total, sendo quatro em destaque e quatro adicionais nos fundamentos, correspondem ao contrato existente. Comparações auditáveis não precisam permanecer todas abertas no layout aprovado.

## Reconciliação numérica e jornada

A conferência independente lê as 21 linhas de `backend/app/synthetic/panorama_fixtures.py`, soma grandezas e pondera DEC/FEC pela base de UCs. Aplica o arredondamento de duas casas do contrato e compara com `GET /api/v1/panorama` pelo proxy em localhost:5173. O artefato local ignorado `work/panorama-control-review.mjs` foi executado por `node work/panorama-control-review.mjs`: oito recortes, oito métricas por recorte, comparações e pontos mensais conferidos, sem divergências.

| Recorte | Faturado (R$) | Pago (R$) | Registros | Pontos mensais |
| --- | ---: | ---: | ---: | ---: |
| Abril/2024, total | 76.500 | 74.200 | 9 | 2 |
| Abril/2024, Recife | 38.000 | 37.100 | 3 | 2 |
| Abril/2024, Olinda/Residencial | 12.500 | 12.100 | 1 | 2 |
| Abril/2024, Jaboatão/Industrial | 2.000 | 1.500 | 1 | 2 |
| Maio/2024, total parcial | 31.000 | 17.500 | 3 | 3 |
| Abril/2024, Rural | Sem fatos | Sem fatos | 0 | 2 |

Também foram conferidas as opções `ano_anterior` e `nenhuma`: não há registros de 2023 na fixture canônica, então a API retorna comparação ausente no primeiro caso e a tela a identifica sem fabricar histórico. O helper antigo `calculateSyntheticPanorama` contém cenários históricos adicionais e não é o oráculo desta reconciliação; a tela usa a resposta validada da API, sem fallback para esse helper.

Para reproduzir o controle principal com a stack sintética ativa:

```powershell
Invoke-RestMethod 'http://localhost:5173/api/v1/panorama?competencia=2024-04&comparacao=anterior&municipio=todos&classe=todas' | ConvertTo-Json -Depth 8
```

Comparar com a fixture canônica e seus testes em `backend/tests/test_panorama.py`: faturado 76.500, pago 74.200, energia consumida/faturada 90.000 kWh, 1.248 UCs, preço médio 0,85 R$/kWh, DEC 1,32 h/UC e FEC 0,87 interrupções/UC. O mesmo percurso Recife/Residencial exibe R$ 21 mil, é restaurado por voltar/avançar e permanece após recarregar. Base zero é exercitada por resposta controlada no teste do componente, pois não ocorre nos recortes canônicos disponíveis.

## Verificações e limites

- `npm.cmd test -- --reporter=dot --maxWorkers=2`: **160 aprovados em 21 arquivos**.
- `npm.cmd run lint`, `npm.cmd run check:boundaries` (105 arquivos), `npm.cmd run format:check`, `npm.cmd run build` e `git diff --check`: aprovados.
- API real e navegador: filtros/URL/histórico, recarga, cancelamento/rascunho, Escape/foco, tabela e fundamentos conferidos. Testes também cobrem falhas, vazio, parcial e indisponibilidade da IA.
- Temas e reflow já conferidos em 320/390/768/1440 px na implementação; remoção do ornamento e alinhamento idêntico da barra/botão de Panorama e Receita medidos no navegador. Nenhuma alteração de produto em backend ou IA.
- Serviço IA local indisponível (503), com dados observados, aviso e retry existentes preservados. Gold e provedor real continuam fora do aceite sintético. Trello sem acesso ao quadro oficial: sincronização pendente.

Resultado final: **Standards: um P3 encerrado, nenhum aberto. Spec: um P3 encerrado, nenhum aberto.** Checklist DEV-02 atendido no escopo sintético.

## Commits da entrega

- `27a0bd5`: filtros padronizados, aplicação atômica e integração com a página.
- `eb25798`: composição do Panorama, indicadores, série, fundamentos e ajustes da revisão.
- A documentação e este relatório são registrados em commit próprio, conforme solicitação de particionar a entrega.
