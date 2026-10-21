# Evolução dos serviços e responsabilidades

## Sinais para investigar

Funções próximas de 30 linhas, serviços próximos de 300 linhas, muitos argumentos ou ramificações repetidas são bons gatilhos de revisão. Não são limites obrigatórios: um bloco coeso pode ser mais legível que várias funções de uma linha. Avalie quantas razões independentes existem para mudar o código.

| Sinal | Mudança que pode ajudar |
| --- | --- |
| Mesmo cálculo em vários endpoints | Extrair função de domínio com entradas e resultados tipados. |
| Consultas repetidas ou fonte substituível | Extrair repositório ou protocolo específico. |
| Serviço mistura regras independentes | Separar colaboradores por responsabilidade e manter a orquestração explícita. |
| Mesma seleção por tipo repetida em vários lugares | Considerar estratégias ou mapa de funções, com tratamento do tipo desconhecido. |
| Subdomínio tem modelo e ciclo próprios | Avaliar módulo próprio, limites de importação e contrato entre domínios. |

## Evitar abstração antecipada

Comece pela menor estrutura que represente o caso de uso. Uma função que recebe `db` ou um repositório é injeção válida. Use classe quando o conjunto de operações compartilha estado ou colaboradores; use `Protocol` quando houver uma fronteira real a substituir ou testar.

Evite criar `BaseService`, repositório CRUD genérico, event bus ou quatro níveis de fábrica sem necessidade concreta. Uma interface estreita costuma expressar melhor o domínio que uma abstração universal. Módulos `shared`/`utils` precisam de um propósito reconhecível, não devem acumular regras de domínios diferentes.

Mantenha importações previsíveis. `app/db/base.py` deve continuar neutro em relação à engine; Alembic precisa conseguir carregar metadados sem conexão acidental. Evite I/O e registro de comportamento escondidos em `__init__.py`. Preserve imports públicos compatíveis quando forem consumidos.

## Refatorar com evidência

Antes da extração, identifique o comportamento a preservar: contrato HTTP, ordenação, ausência, persistência ou cálculo. Depois, verifique o caminho que usa a nova composição. Não combine troca de arquitetura, migração assíncrona, alteração de fórmula e mudança de contrato na mesma refatoração sem necessidade.

Uma chamada externa, uma gravação e uma notificação não formam uma transação distribuída automaticamente. Ao coordená-las, defina falha parcial, repetição e reconciliação; use outbox ou outra estratégia somente se esse caso de uso exigir.
