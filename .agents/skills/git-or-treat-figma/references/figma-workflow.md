# Execução no Figma MCP

## Escolher o arquivo e carregar as instruções

Use as ferramentas do servidor **Figma MCP** disponível na sessão. Antes de cada ferramenta que exija uma skill oficial, carregue a instrução correspondente e seus trechos relevantes; não suponha a API a partir deste resumo.

| Operação | Skill oficial |
| --- | --- |
| Criar Figma Design | figma-create-new-file |
| Inspecionar/escrever via Plugin API | figma-use |
| Criar componentes, variáveis e variantes | figma-generate-library, junto com figma-use |
| Montar telas e painéis | figma-generate-design, junto com figma-use |
| Adicionar animação no arquivo | figma-use-motion, junto com figma-use |

Se uma skill não estiver instalada, procure seu recurso no servidor Figma. Se ferramentas, autenticação ou acesso necessário faltarem, entregue os artefatos preparatórios e declare a construção bloqueada com causa concreta. Não apresente um arquivo local ou imagem como criação no Figma.

Use um arquivo existente fornecido para o trabalho ou crie **V-Energy Grid 360 — Protótipo** em Figma Design após a etapa visual acordada. Ao criar, resolva o plano pela seleção já feita ou por whoami: com um plano, use-o; com múltiplos, peça escolha; sem plano, informe o bloqueio. Reutilize o file_key retornado. Não é necessário exigir link de arquivo prévio quando a pessoa pediu criar um novo.

## Organizar quatro páginas

Leia primeiro o arquivo. Reutilize páginas por ID/nome e preserve conteúdo alheio. Em arquivo novo, renomeie/reutilize a página inicial para obter exatamente as quatro páginas acordadas no SKILL.md; não acrescente uma quinta capa. Em arquivo existente, identifique as quatro áreas do protótipo sem excluir páginas de terceiros.

As páginas de componentes são mostruários dos dois temas. Mantenha uma fonte compartilhada de componentes principais, por exemplo em uma seção da página clara, e instâncias correspondentes na escura. As páginas de fluxos usam instâncias dessa biblioteca e múltiplos frames por jornada/estado. Essa organização física não obriga componentes a terem aparência fixa clara: o tema vem de variáveis semânticas.

## Construir fundações, componentes e fluxos

1. Inspecione variáveis, estilos, componentes e bibliotecas existentes; use get_libraries antes de search_design_system. Reutilize o que for compatível e registre lacunas. Não presuma que as bibliotecas React das referências existem como kits Figma.
2. Defina tokens primitivos e aliases semânticos de cor, tipografia, espaçamento, raios e efeitos conforme a direção aprovada. Use modos **Claro** e **Escuro** nas cores semânticas e scopes adequados. Aplique o modo explicitamente aos frames de cada tema. Se o plano/API limitar modos ou páginas, exponha o limite antes de mudar a estrutura acordada.
3. Construa apenas o inventário necessário às jornadas: controles/filtros, navegação, indicadores, tabelas, gráficos, estados, ordens e IA. Especifique propriedades/variantes pertinentes, foco e estados desabilitado/carregando. Use auto-layout e instâncias; duas vitrines não significam duplicar todos os componentes por tema.
4. Monte telas em ordem de dependência: shell e filtros → conteúdo da jornada → estados alternativos → navegação e ações. Vincule a matriz de cobertura a IDs e destinos reais. Simule ações operacionais com identificação clara; não afirme persistência no backend.
5. Represente movimento com recursos nativos disponíveis ou especifique a aproximação e o comportamento futuro. Efeitos WebGL/shaders das referências não são automaticamente executáveis no protótipo. Use texto, vetores e componentes editáveis para a interface; capturas servem à revisão.

Nomes de tokens/CSS no handoff são propostas enquanto não existir contrato de frontend. Não crie mapeamentos Code Connect fictícios para componentes React ainda inexistentes; faça a integração quando houver fonte correspondente e estiver no escopo.

## Estado, segurança de execução e retomada

Para este trabalho com biblioteca compartilhada, mantenha **um responsável por escrita no Figma** e serialize mutações de componentes, variáveis e páginas. As skills oficiais podem diferir sobre paralelismo de chamadas; operações com fundações compartilhadas têm dependência e seguem a execução sequencial da skill de biblioteca. Leitura e análise independentes podem ocorrer em paralelo.

Antes de cada mutação, resolva a página e os nós existentes. Em cada chamada use o contexto de página conforme a API/skill atual; carregue fontes antes de editar texto e retorne todos os IDs criados/alterados com contagens e validações relevantes. Persistir fora do canvas um registro temporário com fileKey, páginas, componentes, variáveis, IDs, etapa e verificações pendentes permite retomar sem duplicação; não inclua credenciais ou dados reais. Os links e resultados estáveis entram na documentação de entrega.

Se houver erro com execução parcial, respeite safeToRetryWithoutCanvasRead e leia o estado quando exigido antes de repetir. Faça alterações dirigidas pelos IDs retornados. Só remova artefatos temporários desta execução identificados com precisão. Confirme estrutura e aparência conforme coverage-and-review.md antes de declarar o protótipo pronto.

## Agentes quando houver delegação autorizada

Sugestão para a construção: **1 coordenador + 3 subagentes**, reduzindo a equipe se o inventário for pequeno ou o ambiente limitar concorrência.

| Responsável | Modelo / esforço inicial | Entrega | Limite de escrita |
| --- | --- | --- | --- |
| Coordenador | 6.1 Sol High, escolhido pela pessoa usuária | Decisões consolidadas, integração, registro e arquivo Figma | Controla a fila e as mutações no Figma. |
| Requisitos e fluxos | 6.1 Sol Medium | Matriz de cobertura, jornadas, estados e dependências | Artefatos textuais em escopo designado. |
| Componentes e temas | 6.1 Sol High | Inventário, tokens, variantes e propostas fundamentadas | Propõe especificações ao responsável pelo Figma. |
| Revisão | 6.1 Sol High | Cobertura, paridade de temas, acessibilidade e defeitos visuais | Relata achados; alterações retornam ao responsável. |

Os modelos dos subagentes são recomendações ajustáveis; esta skill não altera a configuração do IDE nem garante disponibilidade na conta. Para tarefas menores e delimitadas, como inventário ou conferência de listas, considerar 6 Luna High. Confirmar modelos e esforços suportados pelo cliente antes de configurar; para chamadas de ferramenta, usar o identificador de modelo anunciado pelo ambiente. A [documentação oficial de subagentes](https://learn.chatgpt.com/docs/agent-configuration/subagents), consultada em 16/10/2026, recomenda Sol para trabalho exigente e Luna para tarefas leves. A divisão e os esforços desta tabela são recomendações específicas para este protótipo.

A quantidade é recomendação, não requisito. A simples invocação desta skill não autoriza criar agentes: siga a solicitação atual ou instrução aplicável de delegação. Não divida automaticamente um agente para cada página, pois todas compartilham decisões e componentes. Defina entrega, arquivos, dependências e critério de pronto por tarefa; use contexto mínimo e reúna resultados antes de decisões dependentes.
