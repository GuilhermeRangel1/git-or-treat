# Integração e rodada ampliada do PR #117 — 03/11/2026

## Alterações locais

Base `origin/develop` a6406fc integrada por merge, sem squash ou cherry-pick. Resolvidos os cinco conflitos: calendário combina agrupamentos e listas de locais; síntese conserva comparações compactas e resumos de grupos/gráficos; testes usam os percentuais sem espaço da apresentação vigente. Preservadas formatação pt-BR, mensagens, correção ortográfica e telemetria da branch.

Corrigidos exemplo solar com preposição duplicada e título iniciado por UCs. Dois testes HTTP conferem exemplo replanejável e síntese GD com sigla, contagem e período nos metadados. Não se presume origem solar.

## Verificações executadas

- GenAI Linux isolado: `python -m pytest -q` — 4.432 passaram, 4 skips. `python -m ruff check .`: passou após quebrar uma linha do novo teste.
- Backend Linux com PostgreSQL 16 descartável e as cinco URLs de teste: `python -m pytest -q` — 1.211 passaram, 14 skips, aviso preexistente Starlette/httpx.
- Revisão independente da resolução: sem bug concreto identificado. `git diff --check` e ausência de entradas não resolvidas: passaram.
- Rodada com API autenticada, Gold v2 e Gemini reais na composição integrada paralela: 33 solicitações (28 iniciais + 5 rechecagens). 14 respostas numéricas reconciliadas com SQL independente somente leitura; 15 esclarecimentos; 2 recusas de segurança; 2 falhas transitórias no início, imediatamente após reativação do banco/ingresso de auditoria. As duas perguntas transitórias foram repetidas após disponibilidade e responderam com números reconciliados. A causa exata das falhas iniciais não foi instrumentada: não são classificadas como sucesso.
- Rankings em três formulações conferiram município e menor receita. Série apresentou linha; ranking, barras horizontais; comparação, barras. GD conferido por cálculo de queda sobre médias e requisitos de seis meses em cada janela, sem usar o flag de queda como resposta esperada. Confirmação solar → sim consultou GD mantendo Olinda. Troca completa de assunto não herdou filtros indevidos.
- Configuração da branch manteve Gemini e chave somente em arquivo local ignorado. Nenhuma linha bruta, dado pessoal ou credencial integra esta evidência. Contas e sessões temporárias removidas.

## Diagnóstico histórico antes das correções abaixo

- “Quanto Recife faturou…” e “receita de Recife” ainda pedem desambiguação entre município e bairro; “receita em Recife” respondeu corretamente.
- Após pedir base para “Como a receita em Recife variou em março de 2025?”, responder “Compare fevereiro de 2025 e março de 2025” ainda perdeu o indicador. A ocorrência foi confirmada com geografia explícita; permanece pendente.
- jun/26 e ano isolado recebem esclarecimento de período, não interpretação automática completa.
- Esta amostra foi usada para diagnóstico, sem estimativa de precisão geral. Não houve nova medição estatística de latência, navegador ou homologação de cobertura de Dados. CI remoto depende de publicação. Estados oficiais IA preservados.

## Correção posterior da continuação

A comparação pendente agora reconhece a resposta com dois períodos e conserva indicador e filtros, substituindo o mês isolado anterior. Não herda contexto quando a nova pergunta declara outra métrica. Três regressões HTTP cobrem duas formulações de resposta e troca completa de assunto. GenAI final: 4.435 passaram, 4 skips; lint aprovado.

Rechecagem Gold/Gemini real: “Como a receita em Recife variou em março de 2025?” → esclarecimento → “Compare fevereiro de 2025 e março de 2025” → resposta numérica reconciliada com SQL independente, com gráfico de barras e conta removida. A resposta final levou cerca de 44 s nesta execução; não se declara melhoria de latência. A primeira tentativa de conexão ocorreu antes da disponibilidade dos serviços e foi repetida após verificar saúde. A pendência de perda do indicador acima fica resolvida nesta formulação; desambiguação de “de Recife” continua sendo limitação.

## Ampliação final de linguagem — integração executável e prova Gold local

- Local introduzido por `de/do/da` segue a preferência municipal já existente para `em`. Qualificador explícito de bairro prevalece. Nome isolado compartilhado, como “Quanto Recife faturou”, continua pedindo escolha, agora com alternativas concretas; responder “município” preserva indicador e período. A limitação histórica de “receita de Recife” está superada para essa construção.
- `03/25`, `mar/25`, `março/25` e `jun/26` são expandidos somente quando a cobertura autorizada contém um único ano compatível. Sem cobertura ou com dois séculos possíveis, pede esclarecimento. Datas com dia não viram meses. Ano isolado continua exigindo informação apropriada; não há inferência pelo relógio.
- “1º trimestre de 2025” e trimestre por extenso viram os três meses completos do calendário, sujeitos aos gates existentes. O contrato conserva observações mensais, não promete total trimestral. `comparando` reconhece comparação de dois meses, inclusive ano compartilhado.
- “E no mês anterior?” conserva métrica e filtros de um antecedente com um único mês explícito, inclusive abreviado. Intervalo ou comparação anterior não escolhem silenciosamente um extremo. A continuação da comparação com base pendente permanece coberta pelas regressões anteriores.
- Ranking de receita por bairro usa `consumo_receita_bairro` e as capacidades já aprovadas, sem novas permissões. Rankings de município, bairro e classe conservam agrupamento, direção e limite: não são substituídos pelo total.

### Verificações desta ampliação

- `python -m pytest -q --tb=short` no contêiner Linux com checkout integrado: **4.475 passaram, 4 skips**. `python -m ruff check .`: passou. A regressão posterior apertou a conferência do ID exato de agrupamento; `python -m pytest -q tests/test_gold_language_variants.py --tb=short`: **36 passaram**; `python -m ruff check app tests` e `git diff --check`: passaram.
- 18 solicitações adicionais pela API autenticada com Gold v2/Gemini reais: **13 respostas numéricas**, **4 esclarecimentos**, **1 recusa de escrita**; referências de auditoria presentes em todas. Respostas numéricas conferidas com SQL independente somente leitura: locais/preposições, notações curtas, menor município, maior bairro/classe, mês anterior residencial, comparação após esclarecimento, escolha de dimensão e trimestre.
- O roteiro inicialmente esperava uma soma trimestral, mas o contrato devolve a série mensal. Os três valores mensais retornados coincidiram com o SQL independente; corrigida a expectativa do roteiro, sem mudar o resultado da aplicação. Não se declara que a resposta contém um total trimestral. Houve uma sondagem de saúde antes da disponibilidade do processo reiniciado; a rodada em si completou sem erro de API.
- Contas/sessões temporárias removidas. Configuração privada e resultados detalhados permanecem em caminhos ignorados. A referência de publicação das respostas foi comparada à publicação capturada pelo leitor restrito na conferência SQL: mesma referência, sem divergências. Nenhum privilégio ou cobertura de Dados foi ampliado. A composição paralela usa os mesmos gates e o mesmo leitor do Backend.
- Revisões estáticas independentes: **Standards: 0 achados acionáveis; Spec: 0 achados materiais**, nos arquivos de interpretação/calendário/perfil. Não substituem testes ou CI remoto.

### Limites atuais

Esta rodada cobre os casos enumerados; não mede precisão geral nem afirma entendimento de qualquer frase. Nome sem qualificador pode continuar exigindo escolha. Fontes sem cobertura certificada, operadores ausentes, datas diárias e ambiguidade real mantêm seus bloqueios. Não houve nova validação visual ou medição estatística de latência. A complementação parte do merge `ff6e7aa`, já publicado na branch do PR #117; CI remoto e integração final à develop permanecem verificações separadas.

## Consolidação sobre o merge remoto

Na preparação dos commits, a atualização do remoto revelou que Laura já havia publicado `ff6e7aa`, integrando a mesma develop. Esse commit foi aproveitado, sem criar outro merge ou duplicar commits. Preservados os ajustes remotos de calendário, percentual e reconciliação de moeda negativa; as correções desta revisão ficam em um único commit complementar, com 12 arquivos de GenAI e documentação, sem alterações adicionais de Backend ou frontend.

Revalidação do conteúdo combinado em contêiner Linux descartável: `python -m pytest -q --tb=short` — **4.478 passaram, 4 skips**, em 55,87 s; `python -m ruff check .` e `python -m compileall -q app` passaram. Não houve nova chamada externa nesta conferência. A amostra Gold/Gemini e seus limites são os registrados acima. Os registros anteriores de ausência de commit descrevem as etapas locais anteriores à consolidação.
