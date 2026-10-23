# DEV-05 — fila de inspeção e evidências sintéticas

Data: 22/10/2026. Requisito WEB-04, dependência DEV-01. Implementação em `dev05`, criada da base `origin/develop` em `54534a7` e posteriormente atualizada com `origin/develop` em `8bd219d`, que já contém DEV-02. A entrega demonstrativa não conclui a reconciliação Gold de WEB-04. Decisão: [ADR-0008](../decisions/0008-fila-de-inspecao-sintetica.md).

## Contrato HTTP e navegação

Na revisão de 22/10/2026 inspirada no Panorama da DEV-02, as rotas ficaram responsáveis apenas pela entrada HTTP e delegação. O serviço compõe `QueueResponse` e `SuspicionResponse` tipadas, incluindo ordenação/paginação, opções e proveniência. A fonte continua no repositório analítico da DEV-01; não se introduz uma cópia da base ou dependência da branch DEV-02.

`GET /api/v1/inspections/queue` mantém o envelope analítico `1.0.0` e os campos da DEV-01. Aceita `municipio`, `bairro`, `classe`, `alimentador`, `page` (a partir de 1), `page_size` (1–100), `order_by` (`priority`, `potential_recoverable_energy_kwh`, `uc_id`) e `direction` (`asc`, `desc`, padrão `desc`). O padrão permanece prioridade decrescente. Filtros desconhecidos/contraditórios e ordenação/paginação inválidas recebem 422 no envelope analítico. A nova direção explícita passa a valer para todos os campos; no contrato inicial DEV-01, energia/UC tinham direção ascendente implícita.

`data.items` contém UC, território, classe, alimentador, prioridade de 0 a 1, motivo, indicadores e energia potencial em kWh (número ou `null`). `data.filter_options` acrescenta opções de município/bairro/classe/alimentador do cadastro completo, inclusive quando o recorte fica vazio. `pagination` fica na raiz; página além do total retorna lista vazia mantendo a contagem real. Fila sem suspeitas retorna `status: empty`, nunca uma conclusão de ausência de perdas.

Na revisão de 22/10/2026, cada item acrescentou `signals` com ID, rótulo e peso calculados pela mesma regra do detalhe. `data.summary` acrescenta `total_units`, `highest_priority`, `estimated_units` e `unavailable_estimate_units`. O resumo considera todo o recorte filtrado antes da paginação e não muda ao avançar páginas ou alterar apenas a ordenação. Em fila vazia, as contagens são zero e a maior pontuação é `null`; zero de energia conhecido entra na contagem de estimativas disponíveis. **A apresentação anterior desse resumo em três cartões foi substituída pela revisão visual de 23/10/2026 abaixo; os campos HTTP permanecem disponíveis, sem exigir cartões na interface.**

**Histórico supersedido (22/10/2026):** a rodada anterior descrevia filtros expansíveis, barras de prioridade, três cartões de resumo, detalhe em cartões e tabela mobile horizontal. Essa composição não é a orientação visual vigente.

### Apresentação DEV-05 alinhada ao Figma — 23/10/2026

Referências do arquivo Figma `oTjmpIBgbA7OOYb9ZmMG9K`, seção `249:12375`: fila desktop claro `15:773`, detalhe desktop claro `16:579`, fila mobile claro `195:7869`, detalhe mobile claro `195:8041` e fila/detalhe desktop escuros `16:1738`/`16:1833`. Os contextos MCP completos para fila desktop, detalhe desktop e fila mobile foram obtidos em 23/10/2026; detalhe mobile e frames escuros foram conferidos visualmente no navegador após limite do MCP. Não se afirma contexto MCP nem metadados de design para os frames escuros. A fonte registra estrutura e estilo, não valida dados do protótipo.

- **Fila desktop:** uma superfície de tabela com cinco colunas — UC/prioridade, motivo da suspeita, indicador usado, energia estimada e ação — e link sublinhado `Ver evidência →`. A prioridade continua numérica de 0 a 1; sinais e estimativas vêm da API. Não usar classes “alta/média”, nem os números ilustrativos do Figma. Não renderizar os três cartões de resumo da composição anterior. A ação `Investigar <UC>` aponta para o primeiro candidato visível; ordenação/desempate e paginação permanecem operacionais.
- **Fila mobile:** cada UC aparece como registro empilhado, com identificação, motivo/indicador, energia e ação. Não usar tabela horizontal nem rolagem horizontal para acessar campos. Aviso e link de fundamentos continuam legíveis no fluxo vertical.
- **Filtros:** a barra resumida abre diálogo modal com a organização e os controles de Receita (`ReceitaPage.tsx` e `RevenueFiltersForm.tsx`): largura de 720 px, raio 16 px, cabeçalho com descrição e botão fechar de 40 px, formulário contornado com raio 12 px/padding 16 px e grade responsiva de uma, duas ou três colunas. Campos têm fundo canvas e altura 44 px. `Ajustar filtros` usa fundo canvas, borda control e texto semibold; `Aplicar filtros` usa fundo brand, texto accent-goiaba-text e altura 44 px. Valores editados ficam em rascunho local até aplicar; cancelar/fechar descarta o rascunho, Escape fecha e o foco retorna ao acionador. Preservar município, bairro, classe, alimentador, ordenação/direção e tamanho de página. Após aplicar um alimentador, o resumo mostra uma segunda linha `Alimentador: <valor>` abaixo de Território; limpar filtros remove essa linha, o parâmetro da URL e o filtro enviado à API. Cenário `?alimentador=AL-03` confirmado em navegador a 390 e 1440 px; após limpar, a URL fica `/inspecoes?page=1`, a linha desaparece e as duas UCs voltam à fila. A janela exibida é janeiro–fevereiro de 2025; comparação fica `Não aplicada`, sem controle de comparação anual ou período inexistente.
- **Detalhe:** painel `O que motivou a investigação` apresenta janela recebida da API, motivo, energia estimada e orientação para verificar cadastro, medição e geração distribuída. O aviso `Limite da evidência` mantém explícitas as limitações. `Ver fundamentos` abre diálogo acessível com metadados, proveniência e limites; no detalhe também expõe sinais e pesos, regra e teto de prioridade, ordenação/desempate, referência/observação/horizonte/fórmula da energia e o contexto de `ConsumptionComparison`. Valores permanecem numéricos e atribuídos à API; o protótipo não fornece critério de negócio.
- **Ações de ordem:** exibir `Criar ordem` desabilitada, com explicação acessível de que criação pertence à WEB-05 e ainda não está disponível nesta entrega; `Voltar à fila` preserva o recorte e a página. Não simular persistência.
- **Temas:** claro e escuro seguem os tokens locais e mantêm a mesma hierarquia e ações. Testes e fluxos do modal/filtros foram verificados; fila e detalhe foram capturados em ambos os temas, sem overflow nas larguras conferidas. Estilos computados de Receita e Inspeções foram iguais nos tokens/medidas acordados; modal mobile e foco/Escape foram verificados em ambos os temas. Reflow 720×512 passou sem overflow; não houve teste de zoom nativo a 200%. Não se afirma fidelidade pixel a pixel.

`GET /api/v1/inspections/queue/{uc_id}` retorna `data` com os campos da fila e `rule_version`, `signals` (ID, rótulo e peso), `estimate_evidence` (referência mensal hipotética, observação, horizonte e motivo de indisponibilidade) e `limitations`. UC sem suspeita retorna 404 no envelope de erro, mesmo quando existe no cadastro. Ambas as rotas são somente leitura; fonte indisponível retorna 503 e não aciona fallback. A regra demonstrativa recusa repositório com `is_demo: false` até existir uma regra real homologada.

No portal, `/inspecoes` mantém filtros, direção, ordenação e página na URL. O parâmetro `uc` abre detalhe, inclusive por link direto. “Voltar à fila” preserva o recorte e a página anteriores. Aplicar filtros/ordenação/tamanho reinicia na página 1. Parâmetros repetidos ou inválidos na URL são recusados antes da requisição e podem ser limpos. TanStack Query inclui o recorte nas chaves e propaga cancelamento ao transporte. Durante atualização, a última consulta é identificada; falha no refetch mantém os dados anteriores com aviso explícito.

## Regra demonstrativa `dev05-v1`

Os sinais são exemplos artificiais selecionados na fixture; não há detecção automática sobre Gold nem classificação de fraude. Cada sinal distinto contribui uma vez:

- `reading_gap`, lacuna de leitura: peso 0,60.
- `meter_removed`, medidor retirado: peso 0,32.
- `consumption_variation`, variação de consumo: peso 0,41.
- `distributed_generation`, contexto de geração distribuída: peso 0,20, apenas para demonstrar a composição; GD não comprova irregularidade.

A prioridade é `min(1, soma dos pesos)`, arredondada a duas casas decimais. O número não é uma probabilidade. A fila não elimina candidatos por um limiar de pontuação.

A estimativa é `round(max(0, referência mensal − observação mensal) × horizonte em meses, 2)`, em kWh. Os cálculos usam os valores anteriores à apresentação localizada. Referência ou observação ausentes produzem `null` e justificativa; ausência não vira zero. Uma diferença negativa produz zero conhecido. O horizonte é uma projeção explícita, não soma do consumo da janela. Não há conversão financeira, garantia de recuperação ou imputação de leitura ausente.

Ordenação usa o campo e a direção solicitados. Empates seguem maior energia disponível e depois número da UC em ordem lexicográfica crescente. Nulos ficam depois de todos os números, incluindo zero, em ambas as direções. Ordenar e desempatar ocorre antes de paginar, garantindo páginas estáveis para o mesmo snapshot.

## Controles independentes

- UC-1004: lacuna 0,60 + medidor retirado 0,32 = **0,92**. Referência hipotética 90 kWh/mês; observação de janeiro/2025 de 45 kWh; horizonte 1 mês: `(90 − 45) × 1 = 45 kWh`. Fevereiro tem leitura ausente e não é imputado. A referência 90 é um cenário novo da DEV-05, não uma média histórica calculada ou campo Gold.
- UC-1002: variação 0,41 + contexto GD 0,20 = **0,61**. Observação de fevereiro/2025 de 82 kWh, referência comparável ajustada para GD ausente: **estimativa indisponível**.
- Sem filtros: duas suspeitas, UC-1004 antes de UC-1002 no padrão. Com `page_size=1`, página 2 contém UC-1002. Município Olinda: fila vazia. Os cadastros e leituras da base sintética DEV-03 são preservados; apenas os insumos da suspeita são estendidos por esta regra versionada.

## Reprodução local

No diretório `backend`, com o ambiente Python e dependências instalados:

```powershell
$env:ANALYTICS_SOURCE = 'synthetic'
$env:DATABASE_URL = 'sqlite:///:memory:'
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

No diretório `frontend`:

```powershell
$env:VITE_API_URL = 'http://127.0.0.1:8000'
npm.cmd run dev -- --host 127.0.0.1 --port 5173 --strictPort
```

Abrir `/inspecoes`, conferir os controles, escolher uma UC por página, avançar, abrir UC-1002 e voltar. Filtrar Olinda e conferir fila vazia; limpar filtros e abrir UC-1004 para reproduzir soma e projeção. Alternar os dois temas e conferir viewport estreito, teclado e rolagem da tabela. Para simular erro, interromper a API e usar “Tentar novamente”; dados cacheados devem ser identificados como antigos quando houver falha de atualização.

Os testes HTTP em `backend/tests/test_inspection_queue_dev05.py` usam o serviço real e o repositório sintético. Os testes de interface em `frontend/src/features/inspecoes/InspecoesPage.test.tsx` verificam a jornada com transporte controlado; não substituem a conferência com API real.

## Adaptação futura

### Clareza do detalhe — 22/10/2026

O detalhe apresenta referência hipotética e consumo observado em barras com escala comum em kWh/mês, acompanhadas de valores textuais e do período descrito em `estimate_evidence.reference`. Ausência não recebe barra nem vira zero; zero conhecido continua explícito. A soma dos pesos recebidos e a pontuação da API aparecem juntas, com teto 1, explicação da ordenação padrão e desempate. Não se calcula posição numérica sem o recorte completo, nem se altera regra, contrato HTTP ou estimativa. React 19.2.8 consultado via Context7; sem dependências adicionais.

Com a Gold disponível, homologar critérios de entrada na fila, sinais, referência comparável, sazonalidade, GD, medidores, cobertura temporal, horizonte, unidade, pesos e desempate com perdas/engenharia. Versionar a nova regra, substituir a referência hipotética e reconciliar amostras independentes antes de habilitar dados reais. Ordens e resultados de campo continuam no escopo DEV-06/WEB-05.

Context7 foi tentado em 22/10/2026 e retornou falha de conexão. A integração reutiliza React Router 7 e TanStack Query 5 existentes, sem novas dependências; cancelamento foi conferido na [documentação oficial TanStack Query v5](https://tanstack.com/query/latest/docs/framework/react/guides/query-cancellation).
