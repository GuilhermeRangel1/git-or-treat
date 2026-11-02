# Ajuda contextual de indicadores

Cartão: [FAQ contextual de indicadores e dados](https://trello.com/c/gnODdgCZ). Adicional de explicação que apoia IA-03/IA-05 e WEB-01/02/03/06, sem mudar seus estados oficiais. Entrega executável no portal, com definições do catálogo Gold v2; revisão final de compreensão aprovada pela pessoa usuária em 02/11/2026 nesta entrega local.

## Conteúdo e origem

`frontend/scripts/generate-indicator-faq.mjs` seleciona perguntas, palavras de busca e telas. Cada verbete declara IDs lógicos, público interno, responsável por definição/publicação, início e fim de validade e estado. As respostas são extraídas literalmente de `backend/app/catalogs/gold_v2.json` (`definition`/`label`), sem copiar mapeamentos físicos, grants ou fórmulas SQL. O dicionário de Dados continua a referência para aprofundamento. Nenhum texto é enviado a um modelo.

São nove perguntas: receita faturada/pagamento, consumo medido/energia faturada, preço observado/tarifa, ticket médio, DEC/FEC, ocorrências distintas, chamados mensais/acumulados, decomposição/causalidade e GD/queda. As limitações existentes nas definições são preservadas. Explicar uma métrica não afirma que existe cobertura quantitativa para qualquer recorte.

O artefato `frontend/src/shared/help/indicatorFaq.generated.json` contém somente definições conceituais e metadados. A versão é derivada do conteúdo; `catalogVersion` identifica o catálogo de origem. Datas de vigência são inclusivas em UTC. IDs duplicados são considerados conflito e ocultados; verbetes retirados, futuros, expirados ou fora da tela não aparecem. Todos os conceitos desta entrega destinam-se ao mesmo público interno autenticado; não contêm dados pessoais nem resultados por usuário.

## Caminho e experiência

Catálogo versionado → gerador → pacote estático do portal → `IndicatorHelp` → modal compartilhado. `AssistentePage`, `PanoramaPage`, `ReceitaPage`, `OperacaoPage` e `UC360Page` compõem o mesmo componente com o contexto da tela. O botão é “Entenda os indicadores” no desktop e “Ajuda” no celular, com o mesmo nome acessível.

A busca é uma pesquisa de conceitos dentro da ajuda. Termos que correspondem a vários verbetes oferecem escolhas; ausência informa o limite e sugere procurar um indicador. Pedidos com valores, períodos ou recortes reconhecidos orientam à consulta no Assistente/telas. O envio no compositor continua chamando `/api/v1/ai/questions`, com a autorização, SQL e evidência existentes. A ajuda não intercepta a mensagem nem substitui a resposta quantitativa por um conceito.

Texto é apresentado por nós React, sem HTML/Markdown executável. A ajuda mantém a identificação “Explicação do indicador”, fonte interna e versão, sem links para GitHub; não usa envelopes de evidência, número observado ou resposta gerada. Funciona sem provedor e com APIs indisponíveis, sem cache remoto nem persistência. Uma nova versão do pacote substitui as definições; não existe fallback para uma definição de versão anterior.

Modal e detalhes usam os componentes e tokens locais, títulos/labels nativos, busca associada ao label, expansão por teclado, Escape e retorno ao acionador. O Escape da busca é tratado explicitamente porque o campo search pode consumir o primeiro Escape no Chromium. Abrir/fechar a ajuda preserva o rascunho da conversa.

A seção “Perguntas prontas para usar no Assistente” reúne 18 exemplos adicionais organizados em Receita e preços (8), Consumo e geração distribuída (6), Comparações entre períodos (3) e Atendimento (1). Nenhuma pergunta repete o texto das sugestões da tela inicial. A seleção deriva dos cenários positivos FAT-01 a 06, FAT-09/10/11, CON-02/04/05/06/07/08 e ATE-04 da matriz Gold v2; comparações adicionais reutilizam essas capacidades de período/recorte. Não inclui exemplos mensais de atendimento/DEC/FEC bloqueados por cobertura. Não foi realizada nova rodada Gemini com as 18 frases nesta entrega. Copiar não envia mensagem nem altera o rascunho. Se a área de transferência falhar, o texto é selecionado e a interface orienta a cópia manual. Datas/municípios podem ser editados no compositor; os exemplos não prometem disponibilidade ou permissão para qualquer recorte. Não representam a entrega do cartão de sugestões dinâmicas contextualizadas.

## Manutenção e compatibilidade

1. Dados/negócio mantém as definições e o dicionário; Frontend/GenAI mantém seleção, perguntas e publicação. Uma nova interpretação exige revisão da fonte antes da atualização.
2. Após mudar o catálogo ou a seleção, executar `npm run generate:faq` em `frontend/` e revisar o diff das definições, vigência, fonte e telas. Remover um tópico da seleção retira a ajuda correspondente. Mudança de significado deve atualizar a fonte e gerar uma nova versão.
3. `npm run check:faq` compara o artefato com o catálogo atual; faz parte do CI Frontend. Fonte removida ou conteúdo divergente falha a verificação, em vez de publicar ajuda desatualizada. Não editar o JSON gerado diretamente.
4. Executar os testes comportamentais do FAQ e páginas consumidoras, os gates do frontend e `npm run test:faq-browser`. Não há mudança de API/persistência; rollback reverte o pacote de frontend e a seleção correspondente.
5. Busca semântica futura deverá consumir as mesmas definições aprovadas, com identidade e versão; não criar outra coleção divergente.

## Evidência local — 02/11/2026

- `npm test -- src/shared/help/IndicatorHelp.test.tsx src/features/assistente/AssistentePage.test.tsx src/features/panorama/PanoramaPage.test.tsx src/features/receita/ReceitaPage.test.tsx src/features/operacao/OperacaoPage.test.tsx src/features/uc360/UC360Page.test.tsx --reporter=dot`: 103 passaram na rodada final. Inclui cópia exata e seleção manual após falha do clipboard, ausência de links externos, ajuda sem fetch/provedor, fonte/versão, busca ambígua, fora do FAQ, pergunta quantitativa, retirada, vigência e conflito.
- `node scripts/check-indicator-faq.mjs`: cinco telas em 1440 e 390 px, temas claro/escuro, navegação por teclado, Escape/retorno de foco, ausência de overflow horizontal e rascunho preservado. Sessão artificial e APIs interceptadas com 503; comprova interface e independência do provedor, não autenticação ou consulta Gold numérica. Capturas locais sanitizadas em `work/faq-validation/`, ignoradas pelo Git.
- Conferência de catálogo, build, lint, fronteiras e formatação exercitados. Aviso preexistente em `AuthProvider.tsx`; resultados finais registrados no PRD.

## Revisão dos dez critérios

Os seis itens de implementação estão contemplados: metadados e definições canônicas, geração do catálogo, acesso contextual/decisão conceito-consulta, resposta estática independente de LLM, apresentação/fonte acessíveis e cenários negativos. Os três primeiros de robustez estão contemplados por renderização textual, validade/versão/escopo e distinção explícita de origem.

O último item foi concluído por aceite explícito da pessoa usuária em 02/11/2026, após avaliar a ajuda e solicitar a seleção final de 18 exemplos: “já tá bom pra mim, consegue fechar 1 que falta no card?”. Registra-se aceite local da experiência e dos textos derivados das definições existentes. Não se atribui revisão a Dados ou a uma pessoa não técnica identificada; a pessoa usuária aceitou encerrar o critério por sua própria avaliação. Cartão 10/10 nesta entrega local; integração por commit/PR ainda pendente.

### Ampliação dos exemplos — 02/11/2026

Após solicitação da pessoa usuária, os quatro exemplos iniciais foram substituídos pelos 18 adicionais agrupados. Rodada dirigida final: 25 testes de ajuda/Assistente passaram, incluindo unicidade, ausência de repetição das sugestões iniciais, cópia exata e seleção manual. Build, lint (aviso preexistente), formatação e jornada Chromium nas cinco telas/dois temas/duas larguras passaram novamente. As provas anteriores de 103 testes continuam históricas da primeira seleção; não se declara nova execução numérica das 18 perguntas.
