# V-Energy Grid 360

Plataforma integrada para a distribuidora V-Energy, proposta no case final Visagio Rocket Lab 2026.2. Este repositório reúne o código da solução (pipeline de dados, backend, frontend e agente de IA), a **fonte de verdade textual** do produto e as instruções de trabalho para humanos e agentes. O estado oficial de cada requisito está na tabela do [PRD](docs/PRD.md).

> O material do case traz marcação de confidencialidade e, ao mesmo tempo, pede repositório público como entrega. Antes de publicar, o time deve confirmar com a organização o tratamento permitido dos dados e do enunciado. Não versionar o dataset bruto nem credenciais sem autorização explícita.

## Comece por aqui

1. [PRD completo](docs/PRD.md): escopo, histórias, critérios de aceite, decisões e progresso.
2. [AGENTS.md](AGENTS.md): contrato de trabalho de qualquer agente.
3. [Serviços](docs/services/README.md): responsabilidades e contratos de cada módulo.
4. [Fluxo de desenvolvimento e qualidade](docs/agents/workflow.md): como concluir e comprovar requisitos.
5. [Integrações e hooks](docs/agents/tooling.md): skills, Context7, Figma e automações de proteção.
6. [Acompanhamento no Trello](docs/agents/issue-tracker.md): cartões dos requisitos obrigatórios sincronizados com o PRD.
7. [Diagnóstico da receita](docs/revenue-diagnosis.md) e [status report](docs/status-report.md).
8. [Engenharia de Dados: Workflow, dicionário e suposições](#engenharia-de-dados-workflow-dicionário-e-suposições): print do run limpo, links e decisões da camada de dados.
9. [Protótipo visual](docs/design/grid360-prototype.md): arquivo Figma, temas, componentes, jornadas e limites da demonstração.

## Estrutura do repositório

```text
data-engineering/  pipeline Databricks e documentação local
backend/           API FastAPI e acesso às tabelas Gold
frontend/          aplicação React + TypeScript (Vite)
ai-agent/          agente Text-to-SQL e insights integrados
docs/              PRD, diagnóstico, dicionário e decisões
.agents/           skills compartilhadas e hooks/MCP do Antigravity
.claude/           hooks e adaptadores de skills para Claude Code
.codex/            hooks e MCPs para Codex
.hooks/            scripts compartilhados pelos três clientes
```

Cada pasta de serviço tem seu guia em [docs/services](docs/services/README.md). O dataset do case é disponibilizado separadamente na plataforma da atividade; o repositório não o contém.

## Engenharia de Dados: Workflow, dicionário e suposições

O pipeline Bronze → Silver → Gold roda inteiro no Databricks (PySpark, arquitetura Medalhão) e é orquestrado pelo Job `v-energy-grid-360`, com seis tarefas encadeadas: `Landing_to_Bronze`, `Bronze_perfilamento`, `Bronze_to_Silver`, `Cobertura_Declaracao`, `Silver_to_gold` e `Exportacao_Gold`. A exportação gera CSVs das tabelas Gold (contrato [`gold-csv-v2`](docs/contracts/gold-csv-v2.md)) que alimentam o backend; o cadastro com dados pessoais sai em pacote separado e restrito, nunca neste repositório.

**Execução bem-sucedida do Workflow** (run de ponta a ponta, seis tarefas `Succeeded`, sem tarefas isoladas): [registro do run](data-engineering/evidencias/workflow/run-limpo-250327107715287.md).

![Execução bem-sucedida do Workflow v-energy-grid-360](data-engineering/evidencias/workflow/workflow-run-limpo.png)

| O que | Onde |
| --- | --- |
| Dicionário de dados da Gold | [docs/dicionario_gold.md](docs/dicionario_gold.md) |
| Diagnóstico da variação de receita | [docs/revenue-diagnosis.md](docs/revenue-diagnosis.md) |
| Notebooks e YAML do Workflow | [data-engineering/](data-engineering/README.md) |
| Decisões técnicas e o porquê de cada número | [data-engineering/decisoes-tecnicas.md](data-engineering/decisoes-tecnicas.md) |
| Estratégia de agendamento (proposta, não ativada) | [data-engineering/README.md](data-engineering/README.md#estratégia-de-agendamento-proposta-não-ativada) |

**Suposições da camada de dados** (onde o case não era explícito):

- **Receita é a faturada, não a recebida.** Fatura em aberto usa o valor declarado em aberto, sem afirmar pagamento.
- **Não há kWh faturado na fonte.** A tabela de faturas traz valores, não energia. O volume do diagnóstico é o consumo medido nos pares UC/mês com fatura, e não energia faturada; a limitação consta no diagnóstico e no dicionário.
- **Preço é o preço efetivo observado** (receita ÷ consumo medido nos mesmos pares UC/mês), não a tarifa homologada.
- **Recorte geográfico e de classe vem do cadastro atual**, sem histórico de mudanças.
- **DEC e FEC** seguem a definição simplificada do case: servem para comparar alimentadores e períodos, não para comparar com limites regulatórios reais.
- **Cobertura:** consumo e faturamento têm cobertura certificada (`FECHADO`); domínios sem evidência de fechamento ficam `NAO_CERTIFICADA`, e a Gold e o portal mostram esse estado em vez de esconder a lacuna.
- **Energia recuperável por UC:** a estimativa individual só é publicada quando passa em validação temporal; sem isso o campo fica nulo e o portal mostra apenas a referência histórica, rotulada como tal.
- **Confidencialidade:** o case é confidencial e o repositório é público. Não são versionados dataset bruto, valores em R$, contagens de registros nem identificadores de UC; as evidências trazem apenas estados e percentuais.

## Executar localmente com Docker

**Pré-requisitos:** Windows com PowerShell, Docker Desktop e Compose ativos, portas 5173 e 8000 livres e pacote Gold v2 autorizado, obtido por canal privado. A pasta deve conter `manifest.json` e quinze diretórios analíticos; cadastro pareado é opcional. A primeira carga pode levar vários minutos e requer espaço para imagens e banco. Para respostas do assistente, configure chave Gemini e somente controles Gold já aprovados. Não inclua pacotes ou segredos no Git.

O [roteiro de demonstração](docs/demo-roteiro.md) reúne verificações e jornadas. Para gerar a Gold no Databricks, siga o [guia de dados](data-engineering/README.md); o Compose consome uma exportação existente.

A execução padrão inicia PostgreSQL, carga Gold v2, Backend, GenAI e portal compilado no projeto `git-or-treat`. Fonte inválida impede o início da API, sem fallback sintético. Os ambientes antigos e seus volumes são preservados.

```powershell
.\scripts\configure-docker.ps1 -GoldDirectory C:\caminho\para\data -PresentationAccounts
# Configure GENAI_GEMINI_API_KEY e somente controles já aprovados no .env local.
docker compose up --build -d
docker compose ps -a
```

O configurador gera segredos distintos no `.env` ignorado pelo Git e não sobrescreve configuração existente. O loader prepara automaticamente migrações, carga idempotente, papéis restritos e contas. A opção local `-PresentationAccounts` cria `admin`, `comercial`, `atendimento`, `perdas` e `operacao` com a senha de apresentação aprovada `senha123`. Sem a opção, senhas aleatórias ficam em `work/local-auth/credentials.txt`. Contas existentes nunca têm senha ou perfil substituídos. O cadastro opcional exige seu manifesto em `cadastro_titular_uc/`, pareado com o analítico; não é concedido à GenAI.

| Serviço | Endereço | Execução |
| --- | --- | --- |
| Portal | http://localhost:5173 | Nginx com build estático e proxy da API |
| API | http://localhost:8000/api/v1 | Sessão individual, fonte Gold v2 |
| Banco | Rede interna Docker, porta 5432 | Sem porta publicada no host |

Após a subida, aguarde o `gold-loader` terminar com código 0 e os serviços permanentes ficarem saudáveis em `docker compose ps -a`. Abra o portal e entre com uma conta provisionada. Confira http://localhost:8000/api/v1/health. Se falhar, consulte os logs abaixo, corrija pacote ou configuração e repita a subida. Se as portas estiverem ocupadas, libere-as antes de iniciar. Não compartilhe o arquivo de credenciais.

### Demonstração sintética

Para explorar fila e ordens sem Gold, siga os scripts e pré-requisitos no [guia do frontend](frontend/README.md#abrir-ordens-dev-06-com-persistência-local). Os dados são artificiais e não estão conectados à Gold; a demo de ordens usa SQLite local. `docker-compose.ci.yml` serve ao smoke descartável de CI, não substitui o roteiro integrado Gold.
O portal normal não usa polling, Node ou HMR em runtime; a API não usa reload. Para editar com HMR, use explicitamente `docker compose -f docker-compose.yml -f docker-compose.dev.yml up --build -d`; a fonte permanece Gold v2. Volte ao comando normal para retornar ao portal compilado. A falta de chave impede a geração de respostas, sem substituir a fonte por demonstração. O PostgreSQL tem teto local de 512 MiB; `POSTGRES_MEMORY_LIMIT=1g` no `.env` permite ampliá-lo para cargas maiores.

Use `docker compose logs -f gold-loader` durante a carga e `docker compose logs -f backend` para a API. `docker compose down` preserva o volume `git-or-treat_pgdata16`; não use `down -v` para corrigir inicialização. Preserve também o `.env`, pois ele contém as credenciais desse volume. A composição é HTTP local, não uma publicação pública com HTTPS. [Fluxo, limites e evidências](docs/plans/2026-11-04-docker-gold-inicializacao.md).

## Preparação dos agentes

Codex, Claude Code e Antigravity compartilham os `AGENTS.md`, as skills compatíveis em `.agents/skills/` e os scripts em `.hooks/`. Cada cliente tem configuração própria de hooks e MCPs. Consulte [o estado de validação e os passos de ativação](docs/agents/tooling.md#ativacao-e-verificacao) antes de depender das automações. O PRD continua sendo a referência dos requisitos e de seus estados.

O GitHub Actions em `.github/workflows/quality.yml` roda em pull requests, na branch `main` e manualmente. Ele executa verificações por módulo e de documentação; consulte o workflow para a lista vigente de jobs.

### Compatibilidade do volume PostgreSQL local

O Compose usa PostgreSQL 16 e volume novo `pgdata16`. Um volume anterior de PostgreSQL 18 (`pgdata`) é preservado e não deve ser montado diretamente no 16. Antes de trocar um ambiente com dados úteis, siga a [orientação de migração, preservação e carga](docs/contracts/gold-load-dev12.md#preparação-para-genai-01-schema-origem-e-publicação); não use `down -v` para resolver incompatibilidade. Após preparar o banco novo, aplique as migrações antes de usar as rotas operacionais.
