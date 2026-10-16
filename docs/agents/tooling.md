# Ferramentas de agentes, skills e hooks

## Skills versionadas

Skills externas foram copiadas para `.agents/skills/` em 16/10/2026, a partir dos repositórios públicos oficiais. São instruções de trabalho, não código da aplicação nem prova de implementação. A pasta é controlada pelo Git; uma atualização deve rever diffs e compatibilidade antes de substituir arquivos.

| Origem | Revisão observada | Skills instaladas | Uso no projeto |
| --- | --- | --- | --- |
| [mattpocock/skills](https://github.com/mattpocock/skills) | `49dd158d1076134a641b33efb035946536778336` | `grill-with-docs`, `grilling`, `grill-me`, `to-spec`, `to-tickets`, `writing-for-agents`, `research`, `domain-modeling`, `code-review`, `tdd`, `handoff`, `setup-matt-pocock-skills` | Refinar decisões, especificar fatias, criar tickets, revisar e fazer handoff |
| [vercel-labs/agent-skills](https://github.com/vercel-labs/agent-skills/tree/main/skills/react-best-practices) | `063bee94c3f4df8453406c830b0a7df0f2860278` | `vercel-react-best-practices` | Performance e padrões de componentes React; adaptar ao Vite do case |
| [supabase/agent-skills](https://github.com/supabase/agent-skills/tree/main/skills/supabase-postgres-best-practices) | `c9be0e931b7930f7d02126d04774d904c381e7d7` | `supabase-postgres-best-practices` | Projeto e consulta PostgreSQL, se Postgres for o banco local escolhido |

`grill-with-docs` chama `grilling` e `domain-modeling`, ambos incluídos. As skills de tickets têm rastreador inicial em [issue-tracker.md](issue-tracker.md) e contexto em [domain.md](domain.md). O PRD segue canônico. Não ativar toda skill em toda tarefa: selecione a que atende o trabalho.

As instruções completas ficam em `.agents/skills/` e são descobertas pelo Codex. `.claude/skills/` contém adaptadores com nome e descrição compatíveis que direcionam Claude Code às mesmas instruções e recursos de apoio; altere o conteúdo canônico em `.agents/skills/`, não replique a skill inteira no adaptador.

### Skill própria de prototipação

[git-or-treat-figma](../../.agents/skills/git-or-treat-figma/SKILL.md), criada em 16/10/2026, orienta preparação, discussão visual, construção e revisão do protótipo V-Energy Grid 360. Pode ser invocada como `$git-or-treat-figma`; há adaptador em `.claude/skills/git-or-treat-figma/`. A descoberta em cada IDE depende de seu cliente carregar as skills do workspace.

A skill liga as jornadas do PRD a frames e estados, preserva componentes/tokens compartilhados entre modos claro e escuro e exige construção editável pelo Figma MCP. Seus guias separam [referências visuais](../../.agents/skills/git-or-treat-figma/references/visual-references.md), [execução Figma e divisão entre agentes](../../.agents/skills/git-or-treat-figma/references/figma-workflow.md) e [cobertura/revisão](../../.agents/skills/git-or-treat-figma/references/coverage-and-review.md). A organização das quatro páginas está no [PRD §9.3](../PRD.md#93-experiência-e-acessibilidade); o [registro do protótipo](../design/grid360-prototype.md) documenta a paleta aprovada, o arquivo criado pelo MCP e as verificações da etapa. A criação da skill não instala as bibliotecas das referências nem comprova autenticação do Figma.

## MCP Context7 e Figma

`.mcp.json` configura Claude Code; `.codex/config.toml` registra os mesmos serviços para Codex. Ambos preparam Context7 via `@upstash/context7-mcp` e Figma remoto em `https://mcp.figma.com/mcp`. Context7 consulta documentação atual de bibliotecas; use-o para APIs/configuração sem substituir as decisões do projeto. A configuração não contém chave. A primeira execução pode precisar baixar o pacote. Figma requer autenticação da pessoa usuária; a entrada versionada não significa sessão conectada ou acesso a arquivo. O [arquivo próprio do protótipo](https://www.figma.com/design/oTjmpIBgbA7OOYb9ZmMG9K) foi criado em uma sessão autenticada do Figma MCP em 16/10/2026; cada cliente ainda precisa autenticar sua própria sessão.

No **Codex**, `.codex/config.toml` é configuração de projeto e só é carregada quando o repositório é confiável. Confirme os servidores com `codex mcp list`; autorize Trello com `codex mcp login trello` quando o status OAuth estiver pendente. No Claude Code, confira os servidores do projeto com `/mcp` e conclua a autorização OAuth do Trello no navegador. A configuração local do Context7 chama `npx` e pode baixar o pacote na primeira execução. A autorização é independente por cliente e por usuário.

Fontes: [Context7](https://github.com/upstash/context7/tree/master/packages/mcp), [boas práticas do Context7](https://context7.com/docs/tips), [configuração oficial do Figma MCP](https://developers.figma.com/docs/figma-mcp-server/remote-server-installation/), [conexão oficial do Trello MCP](https://support.atlassian.com/trello/docs/connect-trello-to-ai-assistants-with-trello-mcp/).

## Hooks compartilhados

Os três scripts compartilhados ficam em `.hooks/`. `.claude/settings.json` os registra no Claude Code; `.codex/hooks.json` registra os mesmos scripts no Codex. Como não foi indicada uma URL de origem para esses três nomes, eles são implementações locais em Python 3, sem dependências extras.

O Codex carrega hooks do projeto apenas quando a camada `.codex/` é confiável. Ele solicita revisão e confiança para a definição de hooks antes de executá-los; use `/hooks` para revisar. O Claude Code precisa confiar no workspace para usar os hooks configurados. Em ambos, os ganchos são guardrails locais, não substituem revisão nem scanner de CI.

`AGENTS.md` é a orientação comum. Os `AGENTS.md` de `frontend/`, `backend/`, `data-engineering/`, `ai-agent/` e `docs/` detalham as respectivas áreas. O `CLAUDE.md` da raiz importa as instruções comuns; cada pasta tem um `CLAUDE.md` que importa seu `AGENTS.md`. Isso permite ao Claude carregar a regra local ao acessar arquivos daquela pasta. O Codex lê diretamente os `AGENTS.md`.

| Hook | Evento | Efeito |
| --- | --- | --- |
| `secret-leak-prevention` | `PreToolUse` em leitura/escrita/comandos | Bloqueia acesso direto a arquivos sensíveis e alterações/comandos com padrões de credenciais de alta confiança. Não registra o valor detectado. Não substitui scanner de Git/CI ou revisão. |
| `format-frontend` | `PostToolUse` após `Write`/`Edit`/`apply_patch` | Formata os arquivos alterados sob `frontend/` com Prettier local. A etapa de implementação deve instalar e configurar Prettier. |
| `quality-gate` | `Stop` | Verifica se cada ID `Concluído` tem uma entrada datada no registro do PRD e executa scripts existentes de lint/tipos/testes/build nos módulos com código alterado; se falhar, devolve feedback ao agente. A suficiência da evidência exige revisão humana. |

Os scripts são exceção à etapa “somente documental”, autorizada explicitamente para tornar os três hooks operantes. Nenhum código de produto foi criado. Antes de usar qualquer agente, confirme Python; ao editar frontend, instale Node.js e Prettier local em `frontend/`. No Codex, abra `/hooks` e revise a definição antes de confiar. Referências: [Claude Code Hooks](https://code.claude.com/docs/en/hooks) e [Hooks do Codex](https://learn.chatgpt.com/docs/hooks).

## Ativação e verificação

**Verificado neste ambiente em 16/10/2026:** `codex mcp list` reconheceu `context7`, `figma` e `trello` como habilitados; Python, Node.js e `npx` estão no PATH. O Trello aparece com autenticação desconhecida. A tentativa de `codex mcp login trello` não concluiu porque este ambiente não conseguiu acessar o endpoint para descoberta OAuth. Os JSONs de configuração e a sintaxe dos scripts foram validados; os hooks foram exercitados com eventos simulados. Isso confirma descoberta e comportamento local básico, não a execução de uma sessão completa dos dois clientes.

**Ainda depende de uma sessão real:** no Codex, confiar no projeto e revisar os hooks em `/hooks`; no Claude Code, abrir o projeto e conferir em `/context` se o `CLAUDE.md` da raiz e o da pasta acessada foram carregados, depois verificar os hooks com `/hooks`. O comando `claude` não está disponível neste ambiente, portanto os hooks, imports e MCPs do Claude Code ainda não foram testados de ponta a ponta. A sessão de Figma MCP usada na prototipação foi autenticada e realizou leitura/escrita no arquivo documentado; isso não comprova autenticação nas outras IDEs. O Context7 depende do download do pacote e de rede na primeira execução. Essas etapas pertencem ao ambiente de cada participante e não são resolvidas por arquivos versionados.

Ao iniciar implementação do frontend, instalar Prettier em `frontend/` antes do primeiro `Write`/`Edit`; o hook de formatação sinaliza falha enquanto ele estiver ausente. Ao adicionar `package.json` ou testes Python, definir scripts/comandos de verificação no módulo. O quality gate executa apenas comandos que existirem e só detecta arquivos alterados no estado Git local. Registre no PRD os testes de negócio e a reconciliação; o hook não os substitui.

## Limites práticos

- Hooks não vigiam commits feitos fora de uma sessão dos agentes. O time deve ter revisão e scanner de segredos na futura CI, se publicar o repositório.
- O hook de segredos não é um parser de shell: comandos como `grep CHAVE .env` ou `python -c "open('.env')"` não são bloqueados por ele. A regra `permissions.deny` em `.claude/settings.json` cobre a leitura direta de `.env` pela ferramenta Read; revisão e scanner de segredos continuam necessários.
- Quality gate executa comandos que existirem nos manifests; a ausência de script relevante deve ser resolvida na implementação. Checagem automática não prova a correção de números de negócio.
- Figma depende da conexão da conta e de um link/frame específico; Context7 depende de acesso à rede e à documentação da biblioteca.

## GitHub Actions

O workflow `.github/workflows/quality.yml` roda em pull requests, em pushes para `main` e sob solicitação manual. Com permissões de leitura, ele valida JSON/TOML, os imports `CLAUDE.md` → `AGENTS.md`, links locais nos documentos do projeto e a sintaxe Python dos hooks compartilhados. As ações externas estão fixadas em SHAs completos.

Quando os módulos receberem código e manifests de dependências, ampliar o CI com os comandos reais de lint, tipos, testes e build de cada módulo. Não declarar checks obrigatórios nas regras da branch antes de o workflow ter uma execução bem-sucedida no GitHub; a exigência de PR e os checks obrigatórios são configurações de proteção da branch, não criadas pelo arquivo do workflow. O CI não cria funcionalidades, branches nem PRs.

## Roteiro de verificação no Claude Code

Para quem usa Claude Code, conferir em uma sessão real (a raiz do repositório aberta) e registrar o resultado no grupo:

1. **Versão e pré-requisitos.** `claude --version` deve ser 2.1.295 ou superior (necessário para `onFailure` nos hooks). O comando `python --version` precisa responder: os hooks chamam `python`, não `python3`. Em macOS e em alguns Linux só existe `python3`; como o hook de segredos usa `onFailure: "block"`, sem `python` todas as chamadas de Read, Write, Edit e Bash ficam bloqueadas. Crie um alias/symlink `python` ou ajuste o comando localmente.
2. **Hooks.** `/hooks` deve listar `PreToolUse` (segredos), `PostToolUse` (formatação) e `Stop` (quality gate).
3. **Instruções.** `/context` deve mostrar o `CLAUDE.md` da raiz e o `AGENTS.md`; ao pedir a leitura de um arquivo em `backend/`, o `CLAUDE.md` da pasta também deve ser carregado.
4. **Skills.** Digitar `/` deve listar as 14 skills de `.claude/skills/`; testar `/grill-me`, que só roda quando chamada.
5. **MCP.** `/mcp`: aprovar `context7` e `figma`; autenticar o Figma. Testar o Context7 pedindo a documentação de uma biblioteca.
6. **Segredos.** Com um `.env` falso (ignorado pelo Git): ler `.env` deve ser bloqueado, ler `.env.example` deve funcionar e escrever uma chave falsa como `AKIAIOSFODNN7EXAMPLE` deve ser bloqueado.
7. **Quality gate.** Marcar um requisito como `Concluído` no PRD sem entrada no Registro de progresso: o Claude deve ser impedido de encerrar o turno. Desfazer a alteração depois.

O hook de formatação devolve aviso enquanto o Prettier não estiver instalado em `frontend/`; isso é esperado até o frontend existir.
