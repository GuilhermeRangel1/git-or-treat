# Entendimento e recuperação das perguntas do Assistente

Data: 03/11/2026. Cartão: [Melhorar entendimento e qualidade](https://trello.com/c/yQ45h0tk).
Branch `feat/genai-entendimento-perguntas`, worktree `work/genai-entendimento`, base
`origin/develop` `29c2eb2`. Estado do adicional: **Concluído na entrega técnica local**,
com os 48 critérios revisados (incluindo decisões condicionais), ainda sem commit/PR.
Atende à evolução de IA-01/IA-02/IA-03/IA-07; preserva os estados oficiais desses requisitos.

## Resultado e limites

O Assistente reconhece flexões de faturamento/consumo, classes no plural, linguagem
informal, meses abreviados/numéricos e rankings com quantidade. Uma resposta curta
pode completar a escolha do indicador e depois o ano, sem exigir a pergunta inteira.
Correções explícitas substituem somente o campo informado. Uma pergunta completa
inicia outra investigação, inclusive depois de restaurar uma conversa.

Não adiciona fórmula, fonte, operação SQL, privilégio, retenção ou memória longa.
Continua usando `gold-csv-v2`, schema `gold_v2`, catálogo físico `gold-catalog-v2` e
os envelopes HTTP v1. Pagamento não vira faturamento; solar não vira GD sem
confirmação; entidade desconhecida, exclusão ou operação não representável não
desaparecem para produzir um total geral. Falta de cobertura continua sendo bloqueio.
Esta entrega não promete compreender qualquer frase ou homologar os dados.

## Caminho e contratos

Portal → sessão/escopo Backend → planejamento do núcleo → aprovação do plano →
SQL restrito Backend → síntese fundamentada → auditoria → resposta/histórico existentes.

- O perfil contém o vocabulário, as alternativas de ambiguidades e a confirmação
  inequívoca. A correção de digitação é uma sugestão limitada ao catálogo, nunca uma
  troca automática de entidade. Ajuda conceitual direciona à FAQ existente.
- `AnalysisIntent.ranking_limit` representa top N de 1 a 100. O limite configurado
  continua valendo; plural sem quantidade usa esse teto. Comparação agrupada mantém
  sua semântica anterior: o teto de linhas não vira um pedido explícito de Top 100.
- `IntentInterpretation.clarification_reason` identifica lacunas sem comparar a
  redação da resposta. Cobertura temporal indisponível tem exceção tipada, inclusive
  quando só o segundo mês da comparação está ausente.
- `QuestionPlanResponse.pending_question` é opcional, interno e omitido quando
  ausente. Só existe com `needs_clarification`. É um rascunho lexical cumulativo,
  não um plano aprovado. Campos que não possam ser representados integralmente
  impedem sua materialização. Não entra na resposta pública como campo novo.
- O Backend assina o rascunho com `kind=pending`, mantendo sessão, conversa, escopo,
  catálogo, publicação, digest da resposta e expiração. Tokens executados continuam
  omitindo `kind`, preservando o formato anterior. Ambos são replanejados e
  autorizados novamente. Conteúdo da pergunta ou do histórico não concede acesso.
- O histórico reutiliza a coluna `anchor`; salva o rascunho, não o token. Restauração
  emite uma referência nova na sessão atual. A política de 30 dias e a exclusão
  continuam iguais. O portal acompanha referências de esclarecimentos sucessivos.

Arquivos principais: `ai-agent/app/agent/{interpreter,planner,language_recovery,ranking}.py`,
`backend/app/services/genai_{continuation,coordination}.py`, schemas dos dois serviços,
rotas de chat/histórico e `frontend/src/features/assistente/AssistentePage.tsx`.

## Avaliação independente e melhoria medida

O harness existente ganhou `--gold-language`; confere o plano completo esperado:
métrica/unidade, dimensões, filtros/operadores/valores, janela, comparação, grupo,
ordem e limite. O próprio teste do avaliador injeta a perda de um filtro e confirma
que status `planned` não basta para passar.

| Conjunto e etapa | Resultado | Interpretação |
| --- | --- | --- |
| Sondagem inicial de 16 entradas | 8 planos / 8 esclarecimentos | Inclui ambiguidades adequadas; não é taxa de erro. |
| 32 expectativas autorais, develop original `29c2eb2` | 22/32 corretas | Mesmo contrato, cobertura e escopo artificiais. |
| Mesmo conjunto, primeira implementação | 30/32 | Detectou recebimento confundido e local adicional desconhecido. |
| Após corrigir esses dois casos | 32/32 | Agora regressão; deixou de ser avaliação intocada. |
| 16 formulações separadas, primeira execução | 15/16 | Falha em “energia foi utilizada”. |
| Após corrigir a voz passiva aprovada | 16/16 | Também virou regressão; não é estimativa de linguagem irrestrita. |

As 48 expectativas versionadas cobrem faturamento, consumo, atendimento e
continuidade, com cobertura artificial; atendimento/continuidade nesta avaliação
não certificam a cobertura do lote real. Os contrastes incluem pago/faturado,
solar/GD, exclusão/inclusão, energia/dinheiro, entidade desconhecida e ausência de
filtro obrigatório. Não há descarte de filtro ou correção automática de entidade
nos resultados aprovados. Testes de conversa verificam separadamente recuperação,
troca de assunto, comparação, assinatura e restauração.

### Alternativa de interpretação por modelo

Experimento isolado, sem integrar um segundo planejador: seis casos artificiais
`REV-02`, `ENE-03`, `RANK-03`, `GUARD-04`, `GUARD-07`, `GUARD-10`, do conjunto de
32, foram enviados em uma chamada ao Gemini configurado localmente. Catálogo mínimo
com receita/consumo, unidades, Recife/Olinda, classe/GD e janeiro–março/2025; sem SQL,
dados pessoais, linhas, publicação real ou credenciais no conteúdo.

Gemini `gemini-3.5-flash-lite`: **6/6**, contra **6/6** do planejador corrigido.
Uma chamada concluída em **2,8 s**, **2.130 tokens de entrada / 1.088 de saída**.
JSON validado localmente com Pydantic; nenhuma proposta foi executada. Três tentativas
anteriores com schema enviado no parâmetro de geração retornaram HTTP 400
`INVALID_ARGUMENT`; não contam como sucesso. Remover esse parâmetro no experimento,
enviar o schema no conteúdo e validar a resposta localmente permitiu a comparação.
Isso não demonstra suporte desse schema no constrained decoding do provedor.

Decisão desta fatia: manter interpretação determinística, que resolveu os defeitos
medidos sem uma chamada adicional em produção. Não houve ganho incremental nessa
amostra pequena que justificasse o custo e a nova superfície de validação. Os
critérios condicionais de adaptação semântica não exigem implantar uma porta sem
benefício demonstrado. Reavaliar com falhas novas reais, expectativas independentes,
medição de benefício e aprovação integral dos planos; esse experimento não prova
superioridade geral de nenhuma abordagem.

## Integração real, portal e reconciliação

Composição privada isolada `understanding-validation`, Backend 8014, portal 5183.
`python scripts/check_genai_runtime.py`: configuração, banco, leitor, publicação,
catálogo, auditoria e GenAI prontos; geração configurada. `.env` locais ignorados
foram referenciados, sem segredos versionados. Não houve ampliação de privilégios.

Foram reconciliadas **19 respostas concluídas** pela API/portal, com o provedor real
configurado, sem interceptação de rede ou modelo falso: sete da matriz de API,
três de escolhas/confirmações, seis de três tentativas de navegador, duas de
esclarecimentos encadeados no navegador e uma de troca de período indisponível.
A jornada final de dois esclarecimentos e duas respostas foi repetida e reconciliada
novamente após a revisão. Resposta concluída não significa uma nova chamada ao
Gemini: o caminho pode reutilizar seleção fundamentada/cache. A chamada do experimento
semântico acima foi diretamente observada no SDK, com uso de tokens disponível.

Conferências independentes, na mesma publicação, em transação `READ ONLY`, prazo de
5 s: somas de `receita_total_reais`/`consumo_total_kwh` em
`gold_v2.diagnostico_receita`; top três por município com/sem classe; contagem GD em
`variacao_consumo_uc`; períodos, unidades, filtros, diferenças e percentuais.
Controles usam SQL separado do compilador e precisão decimal, arredondamento
half-even de duas casas quando aplicável. Referências foram encontradas na auditoria.
Os números e as referências individuais ficam apenas nos relatórios privados.

Jornadas verificadas:

1. Forma canônica / voz passiva → mesmo recorte; top três → somente residencial.
2. Duas métricas → “o segundo”; pagamento → confirmação de faturado; solar → GD.
3. “A grana que entrou em Recife caiu de maio para junho?” → “faturado” → recarregar
   e abrir a conversa → “2026” → comparação correta; pergunta completa de consumo
   em Olinda inicia outro recorte.
4. Janeiro/2020 indisponível → fevereiro/2020 indisponível → restaurar histórico →
   junho/2026: preserva receita, classe residencial e Recife; não inventa cobertura.

Chromium headless local, teclado e larguras 390/1440 px, sem overflow horizontal.
As duas primeiras tentativas de restauração falharam por pressupor reabertura
automática/título derivado da pergunta; corrigido o roteiro para abrir pela lista.
Uma repetição posterior não encontrou o formulário durante a partida dos serviços;
prontidão/login conferidos e jornada repetida com sucesso. Contas, sessões e
conversas temporárias foram removidas ao fim de cada roteiro.

Amostra cronometrada da API: sete respostas, p50 **18,250 s**, p95 pelo método
nearest-rank **21,579 s**; três esclarecimentos, p50 **2,765 s**, p95 **2,766 s**.
Não é SLO ou benchmark concorrente. Tokens/custo das sínteses/cache não foram
contabilizados por resposta; não inferir esse consumo dos números do experimento.
O papel operacional da cópia de validação não comprova privilégio mínimo: a prova
numérica do observador não substitui o leitor Gold dedicado nem os testes de acesso.

## Revisão dos 48 critérios

| Critérios | Evidência / decisão |
| --- | --- |
| R01–04 | Baseline, planos completos, lacunas tipadas e contratos até o executor. |
| R05–10 | Perfil, voz passiva/plurais, normalização, confirmação de digitação, FAQ e orientação de domínio. |
| R11–17 | Catálogo existente e regressões de homônimo/hierarquia, negação, operador, restrição desconhecida e unidade. |
| R18–24 | Datas/ADR-0018, comparação versus intervalo, ranking limitado e pedidos múltiplos com esclarecimento. Sem nova operação implícita. |
| R25–31 | Razões estáveis, escolhas curtas, rascunho cumulativo, exemplos fiéis, sessão/histórico e jornada restaurada real. |
| R32 | Comparação isolada 6/6 versus 6/6; sem benefício incremental observado para uma etapa semântica adicional. |
| R33–35 | Integração semântica condicional não adotada. Experimento validado e minimizado; produção conserva precedência e validação existentes, sem proposta remota executável. |
| R36 | Sem nova chamada no fluxo de produção; prazos/cache e regressões de falha preservados. |
| R37–40 | Mensagens de negócio e exemplos; contagem inteira sem `.0`; consumidor/histórico preservados, Panorama sem nova linguagem livre. |
| R41–44 | Dois conjuntos separados na primeira medição; expectativas completas, contrastes, resultados por família e latências delimitadas. |
| R45–47 | Regressão, API/Chromium reais, SQL/auditoria independentes; redução 22→32 no conjunto inicial, bloqueios de fonte preservados. |
| R48 | Este registro, contratos/guias/PRD e sincronização Trello; revisão técnica dos eixos de padrões e requisitos. |

As duas revisões encontraram perdas no encadeamento e no ranking de comparação,
corrigidas e cobertas por testes antes da entrega. Não restam achados concretos
dessas revisões. Aceite técnico local do cartão não homologa domínios sem cobertura,
não encerra automaticamente IA-01/02/03 e não equivale a merge na develop.

## Reprodução e verificações

Em subprocesso Linux sem variáveis privadas de runtime nos testes:

```text
# ai-agent/
python -m pytest -q --tb=short
python -m tests.test_genai_regression --gold-language --output /tmp/language.json
python -m tests.test_genai_regression --gold-language --language-holdout --output /tmp/language-separate.json
# backend/
python -m pytest -q tests/test_genai_*.py tests/test_ai_history_*.py tests/test_ai_conversations_contract.py --tb=short
# frontend/
npm test
npm run build
npm run lint
npm run check:boundaries
npx prettier --check src/features/assistente/AssistentePage.tsx src/features/assistente/AssistentePage.test.tsx
```

Resultados finais: GenAI **4.276 passaram / 4 skips**; Backend dirigido **332 passaram /
29 skips**, aviso preexistente Starlette/httpx; frontend **428 passaram / 1 skip**.
Build, fronteiras (197 arquivos), formatação dos dois arquivos e Ruff dos Python
alterados passaram. Lint frontend: zero erros e aviso preexistente em `AuthProvider.tsx:108`.
Skips não são aprovações de integração; são os testes opcionais definidos pela suíte.
No Windows os testes HTTP/threads ficaram presos; interrompidos e executados em Linux.

Para repetir o aceite real: preparar a composição Gold autorizada, conferir prontidão,
autenticar uma conta temporária somente leitura e percorrer as quatro jornadas acima.
Conferir cada filtro/período antes de comparar os agregados SQL da mesma publicação;
verificar auditoria, remover conta/sessões/conversas. Não publicar dados de teste.
Os roteiros e capturas privados desta execução estão em `work/validation`, ignorado.

## Implantação e rollback

Publicar **Backend → GenAI → portal**: o Backend antigo rejeita o campo interno
novo por `extra=forbid`. Ausência de `pending_question` continua aceita e omitida.
Rollback: portal → GenAI → Backend; tokens pendentes existentes podem receber 409
e exigir reinício da conversa no Backend antigo. Tokens de consulta executada
mantêm a forma anterior. Nenhuma migração, carga Gold ou retenção deve ser revertida.


## Ajuste após teste da pessoa usuária — esclarecimento do ano

A sequência “A grana que entrou em Recife caiu de maio para junho?” → “Sim”
pedia o período inteiro e sugeria outra pergunta. Meses sem ano eram capturados
pela regra genérica de detalhe temporal antes de alcançar a lacuna de ano.
A correção identifica esses meses sem autorizá-los como uma janela válida e usa
`missing_year`: “De qual ano você quer comparar maio e junho? Se forem anos
diferentes, informe o ano de cada mês.” Não oferece exemplo com outra competência.
A confirmação mantém indicador e Recife no rascunho; o ano respondido ainda passa
pelo planejamento e pela validação de cobertura. Exemplos dos outros esclarecimentos
passam a usar o rascunho cumulativo, quando disponível, em vez do texto isolado “Sim”.

Regressão dirigida após a correção: 168 testes passaram; Ruff dos cinco arquivos
Python alterados e git diff --check passaram. Prova final de portal/SQL e regressão
completa registradas abaixo após a execução. A implementação continua sem commit/push.


Chromium real após o ajuste: pergunta ambígua → Sim → pedido específico do ano →
refresh/restauração → 2026 → comparação maio/junho de receita faturada em Recife;
nova pergunta completa de consumo em Olinda inicia outro recorte. Dois esclarecimentos
e duas respostas passaram, sem overflow em 390/1440 px. Ambas as respostas, os dois
extremos da comparação, a diferença e o percentual foram reconciliados por SQL
independente na mesma publicação; quatro eventos de auditoria confirmados. Conta
provisória removida. Ambiente de validação recarregado, portal em localhost:5183.

Regressão completa posterior ao ajuste: **4.277 passaram / 4 skips** no núcleo.
