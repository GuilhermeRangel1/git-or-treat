# Operação DEV-08 — plano de implementação

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** entregar consolidado demonstrativo no backend e a jornada de Operação do layer 06 no portal.
**Architecture:** ampliar o serviço de Operação e seus schemas sem alterar banco ou contratos existentes; feature React própria consome respostas validadas, mantém recortes na URL e reutiliza o layout/tokens atuais.
**Tech Stack:** FastAPI/Pydantic; React 19/TypeScript/Vite, Tailwind 4, TanStack Query 5, React Router 7, Vitest/Testing Library.
**Spec:** [desenho aprovado](2026-10-26-dev08-operacao-design.md).

## Restrições globais

- Execução por subagentes GPT-6 Luna/high; revisão de requisitos e qualidade pelo agente principal, conforme pedido explícito da pessoa usuária.
- Trabalhar na dev08 atual, preservando alterações staged/unstaged preexistentes; sem commit, push, novas dependências, mudança de fórmula legada ou alteração de banco.
- Dados sintéticos identificados; nenhuma conclusão Gold/regulatória; somente período/alimentador como filtros de negócio.
- Contratos existentes 1.0.0/1.1.0 preservados. Somente summary publica 1.2.0.
- Layout persistente e tokens existentes; nenhuma importação entre features. Lucide/Brand/Button/Modal existentes correspondem aos componentes do protótipo.

## Pontos de revisão

- Consolidado com pesos distintos e arredondamento final não pode usar média nem indicadores arredondados por alimentador.
- Qualquer exclusão precisa aparecer na base, estado e fundamentos; nenhuma elegibilidade implica valores nulos.
- Filtro inválido na URL não dispara consulta nem mostra outro recorte; fontes indisponíveis não acionam fixtures silenciosas.
- Abrir/voltar do detalhe e paginar preserva filtros; respostas atrasadas não trocam o alimentador atual.
- Claro/escuro, 320/390/768/1440 px, zoom, teclado e diálogos mantêm controles acessíveis e ausência distinta de zero.

## Tarefa 1 — consolidado HTTP

Arquivos: modificar `backend/app/schemas/operations.py`, `backend/app/services/operations.py`, `backend/app/api/v1/endpoints/operations.py`; criar `backend/tests/test_operations_summary.py`; atualizar `docs/contracts/operations-dev08.md` e `docs/services/backend.md`.

Interface produzida: `GET /api/v1/operations/summary`, filtros `periodo` OU `competencia_inicio`/`competencia_fim`, `alimentador` opcional, janela máxima 120 meses; response `OperationSummaryResponse`:

```text
data.summary: {
  period: AnalyticsPeriod, observed_period: AnalyticsPeriod | null,
  dec_hours_per_uc: number | null, fec_interruptions_per_uc: number | null,
  duration_hours_sum: number | null, interruption_count: integer | null,
  denominator_uc_count: integer | null,
  served_uc_count: integer, included_uc_count: integer,
  included_feeder_ids: string[], excluded_feeder_ids: string[],
  status: available | partial | unavailable | empty,
  limitations: string[], text_alternative: string
}
data.definition: ContinuityDefinition com fórmulas consolidadas e regra de inclusão explícitas
metadata: AnalyticsMetadata, contract_version=1.2.0, status igual ao resumo
```

- [x] Escrever e executar testes HTTP da amostra literal: 6 h / 4 UCs = DEC 1,5; 3 registros / 4 UCs = FEC 0,75; AL-03 excluído, estado parcial. AL-01 sozinho = 1,5/1; AL-03 sozinho = indisponível.
- [x] Cobrir pesos distintos (base 2+3, 6 h e 3 registros → DEC 1,2/FEC 0,6), dados originais antes de arredondar, ausência de elegíveis, fonte vazia, zero conhecido, janela parcial/externa/desconhecida, denominadores inválidos, filtros inválidos/repetidos, fonte indisponível e OpenAPI.
- [x] Implementar `build_operation_summary(repository, start, end, filters) -> OperationSummaryResponse` no serviço; reutilizar elegibilidade e eventos observados existentes. Numeradores e denominador ficam nulos sem elegíveis; populações e IDs continuam explícitos.
- [x] Executar `venv/Scripts/python.exe -m pytest -q -p no:cacheprovider tests/test_operations_summary.py tests/test_operations_dev08.py tests/test_analytics_operations.py` e revisar o diff antes da próxima tarefa.

## Tarefa 2 — contrato, URL e consultas do portal

Arquivos novos em `frontend/src/features/operacao/`: `contract.ts`, `operations-state.ts`, `useOperations.ts`, testes colocados junto desses módulos.

Interfaces produzidas: tipos e decoders `decodeOperationSummary`, `decodeOperationRanking`, `decodeOperationDetail`; `parseOperationParams(params)` retorna filtros válidos, métrica (`dec`/`fec`), detalhe, página/tamanho e erros; helpers de URL mantêm filtros na transição; hooks para summary/ranking/detail usam `AbortSignal` e chaves completas. Nome das propriedades de JSON permanece conforme tarefa 1 e contrato existente.

- [x] Testes rejeitam números não finitos, versões incompatíveis, arrays/campos obrigatórios ausentes e indicadores nulos com estado disponível; aceitam zero e indisponibilidade legítimos.
- [x] Testes de URL cobrem datas inválidas/intervalo invertido/mais de 120 meses, parâmetros repetidos, alias `periodo`, página/tamanho/métrica inválidos e abrir/voltar preservando período, alimentador e ordenação. Defaults janeiro–fevereiro/2025, métrica DEC, página 1, tamanho 20.
- [x] Implementar os módulos sem dependências novas, usando `shared/api/client.ts`. Consultas de visão geral são independentes; detalhe não depende da execução do ranking.
- [x] Executar testes direcionados e conferir tipos/build antes de iniciar a composição da tela.

## Tarefa 3 — página e detalhe do layer 06

Arquivos: substituir `OperacaoPage.tsx`; criar componentes coesos para `OperationFilters`, `OperationSummary`, `OperationRanking`, `OperationDetail`, `OperationSeries` e fundamentos; CSS local apenas se necessário; testes de jornada/estado junto à feature. A entrada de rota existente `/operacao` já fornece cabeçalho/sidebar.

- [x] Consultar contexto Figma com screenshot: visão geral `16:735`/`16:1989`, mobile `195:8292`, detalhe `16:909`, dados `212:5016`; respeitar a skill design-to-code e reutilizar componentes/tokens locais.
- [x] Criar testes de jornada com respostas canônicas do contrato: cards parciais corretos, ordenar por FEC, aplicar/cancelar filtros, URL/voltar/recarga, investigar AL-01 e AL-03, tabela textual, paginação e fundamentos. Cobrir loading, HTTP503, JSON inválido, vazio, parcial, indisponível e zero.
- [x] Compor os quatro cards e ranking desktop/registros mobile; exclusões continuam investigáveis. Não recalcular métricas no cliente.
- [x] Implementar formulário modal com rascunho e validação; detalhe navegável por query, gráficos de barras mensais DEC/FEC com baseline zero e lacunas preservadas, tabela de dados acessível e ocorrências paginadas. Usar strings da API para fundamento; não copiar números/bimestres do Figma.
- [x] Executar testes da feature; agente principal revisa requisitos, código e aparência no navegador com API real. Corrigir achados pelo mesmo executor.

## Fechamento pelo agente principal

- [x] Registrar ADR-0015 e sincronizar definição/aprovação no PRD, contrato e guias. Registrar progresso sem concluir aceite Gold.
- [x] Backend: suíte completa e compileall. Frontend: testes, fronteiras, formatação, lint e build/tipos. Não repetir gates aprovados sem mudança ou motivo.
- [x] Jornada real: amostra AL-01/AL-02, consolidado parcial, filtros, ranking FEC, AL-03 indisponível com dados preservados, URL/retorno, teclado/modais. Conferir claro/escuro e larguras/zoom, guardar capturas locais ignoradas em work/.
- [x] Tentar sincronizar WEB-06/WEB-07 no Trello e registrar eventual falta de acesso. Entregar resultado, comandos e limitações observadas.

## Registro de execução

- Desenho e método aprovados em 26/10/2026. Ruling: seguir diretamente com as tarefas técnicas — a pessoa usuária já aprovou explicitamente a proposta e a execução por Luna/high; não introduzir outro ciclo de autorização para o mesmo escopo.
- Tarefa 1: concluída pelo executor GPT-6 Luna/high e revisada pelo principal nos eixos requisitos/qualidade. Recorte de 99 testes aprovado; amostra conferida também por HTTP real através do proxy Vite → FastAPI. O principal pediu e revisou controles discriminantes de pesos e arredondamento. Sem commit; alterações locais preservadas.
- Tarefa 2: concluída pelo executor GPT-6 Luna/high e revisada pelo principal. 24 testes em três arquivos e build/tipos aprovados. A revisão corrigiu aceitação de denominadores negativos indisponíveis e páginas vazias válidas, rejeição de filtros desconhecidos e vinculação das séries ao alimentador/período; preservação separada do filtro da lista e do alimentador aberto. Sem commit.
- Tarefa 3: concluída pelo executor GPT-6 Luna/high e revisada pelo principal. 15 testes de jornada, contexto visual Figma e conferência real API → portal aprovados; revisão corrigiu preservação de ocorrências na indisponibilidade, separação dos universos global/alimentador, fundamentos completos, validação com rascunho, cores/tipografia, gráficos e reflow. O título da rota passou à feature via `contentHeading`, seguindo o padrão existente; o teste global de navegação foi atualizado para as duas novas consultas. Sem commit.
- Fechamento: backend 400 aprovados/4 ignorados, frontend 259 aprovados/32 arquivos, fronteiras137, formatação/lint/build e compilação aprovados. Verificações direcionadas repetidas após os ajustes finais; geometria/capturas em ambos os temas. Ampliação CSS200% conferida; zoom nativo não comprovado. Trello sem acesso ao quadro, sincronização pendente. Evidência completa no Registro de progresso do PRD; WEB-06 Em validação, WEB-07 Pendente, aceite Gold aberto.
