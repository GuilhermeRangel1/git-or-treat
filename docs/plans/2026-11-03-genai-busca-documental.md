# Busca documental autorizada — evidência local de 03/11/2026

Cartão [Busca semântica em documentação autorizada](https://trello.com/c/gctQzTDV).
Branch `feat/genai-busca-semantica-documentacao`, base develop `36166bd`.
Integração executável e aceite técnico local; dez critérios contemplados.
Sem commit/push/PR nesta rodada. IA-01 a IA-08 preservam seus estados oficiais.
Contrato e atualização: [busca documental](../contracts/genai-documentation-search.md).

## Corpus e consumidor

São as mesmas nove definições conceituais aprovadas no FAQ, conferidas literalmente
contra o catálogo Gold v2; proprietário, público e vigência vêm desse artefato.
Versão inicial `30a032e4e4f5`. Nenhuma tabela de negócio, amostra identificável ou
documentação arbitrária foi indexada. A aprovação anterior do FAQ é a aprovação
do corpus inicial; não autoriza novas fontes automaticamente.

Caminho provado: navegador → Backend com sessão individual → coordenação Gold v2 →
planejamento interno autenticado → núcleo/documentação → referência/texto literal →
validação independente no Backend → auditoria → resposta e fundamento no portal.
Banco e leitor Gold continuam pertencendo ao Backend. Explicações conceituais
não passam pelo executor SQL quantitativo nem pelo gerador de números.

Porta `DocumentationSource` e adaptador `IndicatorDocumentation` oferecem trechos
somente após perfil, fonte, operação, métricas, público e vigência. `DocumentSelector`
é a porta da seleção opcional Gemini; o núcleo não importa o adaptador concreto.
O modelo só escolhe um ID autorizado ou `null` e informa suficiência; texto final é extraído literalmente.

## Comparação de recuperação e suporte

Roteiro versionado: `ai-agent/tests/manual_documentation_search.py`. Onze perguntas
artificiais e expectativas por ID foram definidas antes da rodada final. Dez
pertencem a conceitos do corpus; uma é sobre previsão do tempo e deve abster-se.
A pessoa usuária autorizou explicitamente enviar essas perguntas e somente as
nove definições ao Gemini, sem linhas Gold, dados pessoais ou segredos.

Baseline lexical (palavras normalizadas, melhor escore positivo sem empate):
**2/10 conceitos corretos**, mais a abstinência correta fora do domínio, **3/11**
no conjunto. A pergunta sobre efeito de preço e quantidade escolhia incorretamente
preço médio no baseline; falta de palavras iguais ocultava paráfrases válidas.

Uma tentativa com embeddings apresentou escores próximos entre conceitos e
ausências excessivas. A seleção estruturada sobre o corpus filtrado foi escolhida
após essa comparação. Rodadas intermediárias tiveram timeout/HTTP 504 do provedor,
abstinência desnecessária e um desvio lexical. Não foram contadas como aprovação;
o atalho lexical foi restringido e o prazo limitado a 20 s.

A avaliação foi refinada para separar recuperação e suficiência. Na rodada final
versionada: **nove respostas com ID esperado e texto integralmente suportado**, um
esclarecimento sobre a pergunta ampla de geração própria/queda e uma ausência de
evidência fora do domínio. Foram **11/11 resultados seguros esperados**, com
**10/11 correspondências exatas de recuperação**, incluindo a ausência fora do
domínio. O esclarecimento **não** é contado como recuperação correta ou resposta
fundamentada concluída. Baseline: 3/11 correspondências exatas.

A expectativa inicial exigia recuperar GD na pergunta ampla “o que significa ter
geração própria e reduzir o consumo?”. Conferir o corpus mostrou que ele descreve
cadastro/indicador de queda e não comprova geração própria. O roteiro registra
explicitamente que esse caso pode esclarecer; não foram alteradas as definições
para inventar cobertura. Uma rodada anterior falhou no critério inicial e permanece
registrada como falha. Relevância e suficiência passaram a ser campos separados,
com regressão que impede transformar trecho parcial em resposta concluída.

As nove respostas preservaram as ressalvas de pagamento, simplificação de DEC/FEC
e causalidade. Tempos dessa rodada: 0,826–8,184 s, sem caracterizar SLO. Esse conjunto
foi usado na calibração: o resultado não é avaliação cega nem precisão geral sobre
português livre. Falhas anteriores do provedor (504/timeout) continuam documentadas;
não foram contadas como ausência de definição ou escondidas por retry automático.

Reprodução privada, após configurar a chave em ambiente ignorado e autorizar o envio:

```text
cd ai-agent
# Definir GENAI_RUN_DOCUMENTATION_LIVE=1 somente para a rodada autorizada.
python -m tests.manual_documentation_search
```

O roteiro imprime seleção/esperado, suporte literal, tempo, baseline e resumo;
retorna código diferente de zero se houver falha. Telemetria registra contadores
disponíveis do provedor; ausência de uso não é presumida como zero. Não foi
estimado preço monetário nem prometida economia ou latência geral.

## API, PostgreSQL e portal reais

Usados processos temporários da branch nas portas internas 18116/18117 e frontend
5174, mantendo o portal principal 5173. Configurações privadas herdadas dos
containers, sem copiar `.env` para o Git. Sessão temporária de leitura no banco
local, sem ampliar grants Gold.

As **nove perguntas canônicas**, pela API pública com sessão real e publicação
Gold v2 local, retornaram **HTTP 200/answered**, texto literal correspondente e
referência de auditoria. A prova reconcilia definições, não valores de negócio;
não homologa cobertura mensal dos domínios.

Chromium instalado no Windows, sem interceptação de APIs: pergunta DEC/FEC,
resposta pela API real, fundamento aberto pelo teclado, citação com título/seção/
versão; temas claro/escuro em **1440 e 390 px**, sem overflow horizontal ou erro
JavaScript. Capturas foram inspecionadas, inclusive mobile, e permanecem em
`work/documentation-validation/`, ignorado. O primeiro Chromium do container não
estava instalado; foi usado o navegador já instalado no host.

## Verificações de código e controles

Executadas em cópias Linux temporárias, com variáveis privadas retiradas dos testes:

```text
# ai-agent
python -m pytest -q --tb=short
python -m pytest -q tests/test_documentation_source.py tests/test_documentation_flow.py tests/test_document_selector.py tests/test_internal_envelopes.py tests/test_external_source_composition.py --tb=short
python -m ruff check app tests
python -m compileall -q app tests

# Backend
python -m pytest -q tests/test_genai_documentation.py tests/test_ai_history_store.py tests/test_ai_history_http.py tests/test_ai_conversations_contract.py tests/test_genai_planning_metadata.py tests/test_genai_internal_contract.py tests/test_genai_flow.py tests/test_genai_invalidation.py --tb=short

# Frontend
npx vitest run src/features/assistente/AssistentePage.test.tsx --reporter=dot
npm run build
npm run lint
npm run check:boundaries
npx prettier --check src/features/assistente/AssistentePage.tsx src/features/assistente/AssistentePage.test.tsx

# Raiz
python scripts/generate-genai-documentation.py --check
node frontend/scripts/generate-indicator-faq.mjs --check
git diff --check
```

Suíte completa GenAI final: **4.318 passaram, 4 skips de ambiente** (44,32 s), após separar relevância e suficiência. Rodada dirigida após os últimos ajustes:
**120 passaram**; após separar relevância/suficiência, **107 passaram** nos módulos documentais e envelopes. Backend: **176 passaram**, com aviso Starlette/httpx preexistente.
Página: **23 passaram**; build/tipos, fronteiras, formatação e lint passaram,
com aviso preexistente de `AuthProvider`. Coleta inicial da suíte falhou por falta
de scripts/contratos e PYTHONPATH na cópia temporária; corrigida a estrutura sem
alterar o código para mascarar falhas. O novo estado interno também exigiu atualizar
a fixture dos testes de envelopes para incluir referência documental.

Revisão independente em dois eixos identificou quatro defeitos corrigidos:
descarte de parte da pergunta pelo atalho lexical, referência sobrevivendo ao erro
final de auditoria, I/O síncrono no loop do Backend e exceção na camada concreta.
As regressões cobrem os defeitos e a rechecagem não apontou bloqueio material.
Não se atribui revisão humana ou homologação de Dados a essa revisão por agentes.

## Revisão dos dez critérios

| Critério | Evidência da entrega local |
| --- | --- |
| 1. Fontes/aprovação/vigência/permissões | Corpus do FAQ aprovado; gerador confere catálogo v2; proprietário/público/vigência preservados. |
| 2. IDs e comparação | IDs estáveis, seção e versão por conteúdo; 3/11 correspondências lexicais → 10/11 semânticas; nove respostas, um esclarecimento e uma ausência corretos. |
| 3. Porta/adaptador composto | `create_app`/`compose_core` injetam fonte e seletor; filtros antes do provedor; HTTP real provado. |
| 4. Resposta/citação e quantitativos | Extração literal, referência interna e validação independente; nove definições públicas auditadas; recortes seguem Gold. |
| 5. Atualização/remoção/derivados | Sem índice/cache persistido; hash e vigência relidos; retirada invalida detalhe e replay do histórico. |
| 6. Recuperação e resposta separadas | Paráfrases com IDs independentes; texto/citação literais; ausência, conflito, versão, retirada e duas identidades testadas. |
| 7. Injeção indireta | Conteúdo e metadados passam pelo gate; seletor sem ferramentas; saída extra/ID forjado/incompleta recusados; texto renderizado sem HTML executável. |
| 8. Escopo na recuperação/cache/citação | Fonte filtra por escopo; Backend reautoriza após validar; histórico exige digest atual e definição vigente. |
| 9. Limites e falhas | Fonte/modelo usam controlador; uma seleção, 20 s, 24 trechos/limites de bytes; falhas explícitas, sem fallback externo. |
| 10. Métricas/reprodução/rollback | Roteiro opt-in, comparação e suporte separados, comandos, versões, prova API/portal e flag de desativação documentados. |

Limites: nove conceitos aprovados, acesso interno de leitura, sem pesquisa livre
na internet ou em arquivos arbitrários. Novos documentos precisam de revisão e
nova geração/implantação. Continuidade de conversas longas permanece no PR #113;
este trabalho não incorpora nem duplica seus commits.


## Ampliação solicitada — 03/11/2026

A busca agora publica 16 verbetes: nove comparativos do FAQ e sete individuais,
com cobertura conceitual dos 14 indicadores do catálogo Gold v2. Os novos textos
são extraídos literalmente de `definition`/`label` do catálogo: consumo médio
por UC, satisfação mensal e acumulada, DEC, FEC, chamados por abertura e chamados
acumulados. Não expõe mapeamentos físicos ou dados operacionais. Cada definição
individual requer apenas sua própria métrica autorizada; verbetes comparativos
continuam exigindo todas as métricas que explicam.

O gerador preserva o FAQ original e recalcula a versão do corpus ampliado; a
versão documental passa a ser independente da versão do pacote FAQ. As duas
cópias de runtime continuam idênticas. Remover uma métrica do catálogo retira o
verbete individual na próxima geração; mudanças de versão invalidam referências
históricas anteriores conforme o contrato existente.

Expressões “me explica”, “pode me explicar” e “o que quer dizer” entram no caminho
conceitual. Datas e localidades explícitas continuam no caminho quantitativo.

Verificações desta ampliação: 114 testes GenAI dirigidos passaram (incluindo os
sete textos literais sem modelo, permissão individual e roteamento), sete testes
Backend passaram; Ruff, geração --check e diff passaram. A primeira execução
identificou IDs com pontos incompatíveis com o envelope; corrigidos para IDs com
hífens e repetidos os testes. A rodada Gemini e a jornada de navegador descritas
acima pertencem ao corpus anterior de nove verbetes; não foram repetidas nesta
ampliação. Os resultados comparativos 3/11 e 10/11 não medem o corpus ampliado.
Sem novas chamadas externas, commit ou push nesta rodada.


### Revisão do PR #114 — ciclo de vida documental

A revisão de padrões identificou herança indevida da vigência do primeiro FAQ
para as definições individuais. Corrigido com seleção explícita dos sete IDs e
metadados próprios: retirar receita não retira DEC/FEC ou satisfação, e adicionar
uma métrica ao catálogo não a publica automaticamente na busca. Corpus
regenerado nos dois serviços. 115 testes GenAI dirigidos passaram; Ruff, gerador
--check e diff passaram. Falha inicial na cópia Linux foi ausência do diretório
temporário scripts, corrigida sem alterar a regressão. Sem novas chamadas externas.
