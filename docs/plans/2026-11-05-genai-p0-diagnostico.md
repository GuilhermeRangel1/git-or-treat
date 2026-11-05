# P0 — diagnóstico inicial do planejamento GenAI

Data: 05/11/2026. Preparação para IA-01/02/03; nenhum aceite Gold concluído.
Referência executada nesta branch limpa: `origin/main` / `2c2c024`, com a fixture e as mudanças locais do avaliador. Perfil Gold v2, fonte gold.local; sem provedor, SQL ou publicação real.

## Amostra e resultado

40 casos: 32 controles conhecidos de `gold_language_eval.json` e oito casos autorais de demanda, em `ai-agent/tests/fixtures/gold_p0_diagnostic.json`. Resultado: 36 corresponderam às expectativas verificadas e quatro divergiram. Os controles passaram em 32/32; os casos novos, em 4/8. Isso não é taxa geral de acerto nem avaliação cega. Parte dos oráculos verifica apenas o status, portanto um esclarecimento de motivo errado pode passar; essa limitação exige revisão antes de promover o benchmark como gate.

Relatório estruturado: `ai-agent/reports/genai-p0-planning-baseline.json`. O conjunto reservado existente não foi executado. Os casos novos agora são dados de desenvolvimento. A cobertura artificial é janeiro a março de 2025; os dois casos de últimos 12 meses avaliam esclarecimento, sem provar distribuição anual ou desambiguação temporal.

## Primeiras divergências observadas

| Casos | Resultado e primeira divergência | Próxima investigação |
| --- | --- | --- |
| P0-35/36 | Interpretação/política funcional: pede escolher variação ou total mesmo quando o pedido solicita maior faturamento/top cinco no intervalo. Há também uma lacuna posterior de capacidade: o validador restringe ranking a um mês. | Interpretar intenção de total e expor indisponibilidade da operação corretamente; representar consolidação antes de ordenar. |
| P0-37 | Interpretação/planejamento: aceita a pergunta de maior mês como série comum, sem ordenação e com limite 100. Sucesso estrutural com perda da intenção. | Representar ranking por competência e exigir equivalência semântica além de plano válido. |
| P0-38 | Interpretação: pedido de distribuição entre classes recebe mensagem de geografia desconhecida. Há lacuna posterior de consolidação/participação. | Rastrear o segmento identificado como local, sem corrigir só pela frase do exemplo. |

São três famílias demonstradas nesta amostra, não as três causas mais frequentes entre usuários reais. Dois casos de ranking por intervalo, um de ranking temporal e um de distribuição não sustentam uma priorização por frequência real. Não classificar essas quatro lacunas como falhas de segurança.

## Reprodução

No diretório `ai-agent`, com dependências instaladas, executar:

```powershell
$env:GENAI_MODEL_PROVIDER='unavailable'
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'
python -c "import json; from tests.test_genai_regression import build_gold_language_report; print(json.dumps(build_gold_language_report('gold_p0_diagnostic_v1.0.json', include_checks=True), ensure_ascii=False, indent=2))"
```

Execução observada: 40 casos, 36 conformes e quatro divergentes; sem erros do avaliador. Uma inspeção auxiliar das respostas falhou ao ler `response=null`; foi corrigida e os casos restantes inspecionados. Não afeta o relatório da execução completa. No Windows desta sessão, o ASGI exigiu execução fora do sandbox por bloqueio de sockets locais.

## P0 ainda aberto

Faltam perguntas reais sanitizadas, acompanhamento com contexto, casos de autorização específicos deste conjunto, oráculos de intenção/motivo mais fortes, referência numérica independente, classificação por frequência real e avaliação reservada. SQL, dados, síntese, portal, custo e latência ponta a ponta não foram medidos. A etapa seguinte é corrigir a força dos oráculos e completar essas categorias antes de escolher uma expansão ampla do contrato. Os campos semânticos esperados usados nos casos novos não são uma decisão de formato do contrato HTTP.


## Rodada 1.1 — motivos de esclarecimento e conversas

A fixture corrente `gold_p0_diagnostic.json` contém 46 casos. A versão inicial foi preservada em `gold_p0_diagnostic_v1.0.json` para reproduzir a primeira rodada. O runner admite contexto de até três turnos no mesmo caminho `_plan`, e os 20 esclarecimentos esperados agora verificam termos relacionados ao motivo na mensagem principal, excluindo o exemplo sugerido. Essa checagem lexical é mais forte que status isolado, mas não substitui anotação semântica humana e pode precisar aceitar formulações equivalentes.

Resultado: 40/46 conformes, seis divergências, zero erros do avaliador. Os seis casos novos de conversa passaram (3 troca de competência, 2 troca curta de métrica e 1 pergunta completa nova), conferindo métrica, filtros e limites temporais. Prova do núcleo HTTP interno com contexto artificial, sem provar token de continuidade, sessão Backend ou isolamento entre usuários.

Dois falsos sucessos da avaliação inicial foram revelados, sem mudança do produto:

- `GUARD-14`: data inválida `13/2025` recebe mensagem de geografia desconhecida. Primeira falha: interpretação do calendário/entidade.
- `P0-34`: pergunta longa de distribuição anual recebe mensagem de valor desconhecido de classe. Primeira falha: interpretação do agrupamento/entidade, anterior à resolução de cobertura ou expansão da capacidade. A resposta não permite concluir como o sistema trataria o conflito temporal depois de reconhecer a intenção.

Os quatro casos anteriores continuam divergentes. Portanto 36/40 e 40/46 não medem melhora do chatbot: o conjunto e a força dos oráculos mudaram. Sob o oráculo novo, 34 dos 40 casos iniciais correspondem ao esperado, e os seis adicionais passaram.

Relatório: `ai-agent/reports/genai-p0-planning-baseline-v1.1.json`. Reprodução: usar o comando anterior com `gold_p0_diagnostic.json`. Configuração e referência de produção permanecem as mesmas da rodada inicial.

Verificações: `python -m pytest tests/test_gold_language_evaluation.py -q -p no:cacheprovider --tb=short`, no diretório `ai-agent` com as mesmas variáveis, passou em 3 testes (4,74 s); a execução direta dos 46 casos terminou sem erro. `git diff --check` passou. A inspeção das quatro respostas sintéticas confirmou a classificação das falhas, sem SQL ou provedor.

Próxima prioridade do P0: anotar métricas de falha por etapa e ampliar a prova de cobertura para 12 meses artificiais, separando explicitamente perda de intenção e operação ainda não representável. Ainda não há evidência de frequência real nem benchmark numérico ponta a ponta. P0 continua aberto.


## Reprodução após reiniciar da main limpa

A rodada 1.1 foi reexecutada em 05/11/2026 em `feat/genai-p0-impacto`, partindo de `origin/main` / `2c2c024`, sem cherry-pick dos commits da comparação municipal. O resultado permaneceu 40/46, com os mesmos seis casos divergentes. Relatório reproduzível nesta branch: `ai-agent/reports/genai-p0-planning-baseline-v1.1.json`. A regressão `python -m pytest tests/test_gold_language_evaluation.py -q -p no:cacheprovider --tb=short` passou em 3 testes; a execução da amostra limpa foi bem-sucedida sem erro do runner.
