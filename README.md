# V-Energy Grid 360

Plataforma integrada para a distribuidora V-Energy, proposta no case final Visagio Rocket Lab 2026.2. Este repositório reúne a **fonte de verdade textual** do produto e as instruções de trabalho para humanos e agentes. Nesta etapa, ainda não há implementação da aplicação.

> O material do case traz marcação de confidencialidade e, ao mesmo tempo, pede repositório público como entrega. Antes de publicar, o time deve confirmar com a organização o tratamento permitido dos dados e do enunciado. Não versionar o dataset bruto nem credenciais sem autorização explícita.

## Comece por aqui

1. [PRD completo](docs/PRD.md): escopo, histórias, critérios de aceite, decisões e progresso.
2. [AGENTS.md](AGENTS.md): contrato de trabalho de qualquer agente.
3. [Serviços](docs/services/README.md): responsabilidades e contratos de cada módulo.
4. [Fluxo de desenvolvimento e qualidade](docs/agents/workflow.md): como concluir e comprovar requisitos.
5. [Integrações e hooks](docs/agents/tooling.md): skills, Context7, Figma e automações de proteção.
6. [Diagnóstico da receita](docs/revenue-diagnosis.md) e [status report](docs/status-report.md): estruturas a preencher com evidências reais.
7. [Protótipo visual](docs/design/grid360-prototype.md): arquivo Figma, temas, componentes, jornadas e limites da demonstração.

## Estrutura planejada

```text
data-engineering/  pipeline Databricks e documentação local
backend/           API FastAPI e acesso às tabelas Gold
frontend/          aplicação React + TypeScript (Vite)
ai-agent/          agente Text-to-SQL e insights integrados
docs/              PRD, diagnóstico, dicionário e decisões
.agents/skills/    skills externas versionadas para agentes
.claude/           hooks e adaptadores de skills para Claude Code
.codex/            hooks e MCPs para Codex
.hooks/            scripts compartilhados pelos dois clientes
```

As pastas de serviços são apenas esqueletos documentais. A solução será construída em entregas verificáveis, seguindo os IDs do PRD. O dataset mencionado no case será disponibilizado separadamente na plataforma da atividade; o repositório não o contém.

## Preparação dos agentes

Codex e Claude Code compartilham os `AGENTS.md` e os scripts em `.hooks/`. Cada cliente tem sua configuração própria de hooks e MCPs. Consulte [o estado de validação e os passos de ativação](docs/agents/tooling.md#ativacao-e-verificacao) antes de depender das automações. O PRD continua sendo a referência dos requisitos e nenhum item funcional foi concluído nesta fase.

O GitHub Actions em `.github/workflows/quality.yml` roda em pull requests, na branch `main` e manualmente. Por enquanto, valida configurações dos agentes, imports compartilhados, links locais da documentação e sintaxe dos hooks. Ele não implementa funcionalidades nem cria branches ou pull requests.
