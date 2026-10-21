---
name: backend-coding-standards
description: Use ao criar, revisar ou refatorar endpoints FastAPI, schemas Pydantic, serviços Python, repositórios, injeção de dependências ou testes do backend; também ao avaliar limites de camadas, transações e concorrência.
---

# Padrões de backend — Python e FastAPI

Priorize responsabilidades claras, contratos verificáveis e operações consistentes. Esta skill é orientação auxiliar: a solicitação atual, os `AGENTS.md`, o PRD e as decisões aprovadas prevalecem.

## Antes de alterar

Leia [as regras do backend](../../../backend/AGENTS.md), [o guia do serviço](../../../docs/services/backend.md) e o requisito afetado no [PRD](../../../docs/PRD.md). Confira dependências, código e CI existentes. Consulte Context7 para APIs de bibliotecas quando disponível.

## Referência por tarefa

| Tarefa | Ler |
| --- | --- |
| Organizar camadas, contratos e erros | [Arquitetura e camadas](references/architecture-and-layers.md) |
| Compor dependências e escolher sync/async | [Injeção e ciclo de vida](references/dependency-injection.md) |
| Dividir serviços e evitar abstrações prematuras | [Evolução dos serviços](references/domain-and-service-scaling.md) |
| Tipar e tornar regras legíveis | [Python e qualidade](references/python-idioms-and-quality.md) |
| Definir verificações e ferramentas | [Ferramentas](references/linters-and-tooling.md) |
| Verificar transações, contratos e integração | [Testes e consistência](references/testing.md) |

## Critérios de revisão

- Router traduz HTTP; serviço executa o caso de uso; persistência tem fronteira explícita. Preserve o arranjo atual ao fazer mudanças pequenas.
- Injete colaboradores explicitamente. Funções e classes são opções; a escolha deve reduzir acoplamento ou facilitar testes.
- Escolha `def`/`async def` conforme as operações executadas. Uma função síncrona chamada dentro de uma coroutine continua bloqueante.
- Defina quem confirma a transação e como falhas são revertidas. Repositórios colaboradores não devem confirmar partes de uma operação atômica.
- Mantenha contratos públicos tipados e erros HTTP livres de SQL, segredos e rastros internos.
- Preserve origem, unidade, período, filtros e ausência dos dados; mantenha Gold e operações separados.
- Dimensão de arquivo e complexidade são sinais de revisão, não motivo isolado para criar camadas ou classes.

Ao entregar, informe comportamento alterado, comandos executados e limites da evidência. Refatoração, mocks e fixtures não concluem critérios funcionais do PRD.

## Origem

Adaptação em português das [skills de msb7-jpg](https://github.com/msb7-jpg/visagio-atividade-v-energy-360/tree/d90fe16c26e3b6cc2cdcea4e5f2c116ded73ceb5/.agents/skills/backend-coding-standards), revisão `d90fe16c26e3b6cc2cdcea4e5f2c116ded73ceb5`, consultada em 20/10/2026. A organização temática foi aproveitada; os exemplos e as regras foram ajustados ao projeto. Veja [origem e diferenças](../../../docs/agents/tooling.md#skills-de-padrões-de-backend-e-frontend).
