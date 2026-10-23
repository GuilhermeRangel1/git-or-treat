# ADR-0010 — Prioridade e estimativa auditáveis na fila sintética

Data: 22/10/2026. Estado: adotada para a demonstração DEV-05 solicitada; critérios reais pendentes de homologação. Requisitos: WEB-04 e recorte de WEB-07.

## Contexto

A DEV-01 expõe duas suspeitas com valores fixos. A DEV-05 exige reproduzir prioridade e estimativa a partir das evidências apresentadas, sem dados ou definições reais disponíveis. A fila deve permanecer independente da DEV-02.

## Opções

Manter valores fixos não satisfaz auditabilidade. Calcular uma regra no frontend duplicaria decisões e permitiria divergência da API. Adotar um modelo real sem evidência daria aparência de diagnóstico a hipóteses.

## Decisão

Calcular uma regra sintética versionada no serviço analítico existente. Preservar os campos públicos da fila, acrescentar direção explícita/opções de filtros e um detalhe somente leitura. Expor insumos, pesos, fórmula, horizonte e limitações. A regra e controles completos ficam em [inspection-dev05.md](../contracts/inspection-dev05.md). A prioridade soma pesos com teto de 1; a energia projeta diferença mensal positiva com horizonte explícito; ausência de referência permanece nula. A aplicação dessa regra fica restrita a fonte demonstrativa.

## Consequências

API, interface e testes compartilham um contrato auditável; o frontend só apresenta os resultados e insumos, sem recalcular a regra. A nova direção aplica-se também à energia e UC; a mudança da direção implícita anterior está registrada no contrato. O detalhe mantém o contexto da URL ao retornar à fila. Não há mudança no banco, em ordens, IA ou na Gold. WEB-04 fica em validação até a homologação e a reconciliação dos dados reais; os pesos atuais não são critérios aprovados para operação de campo.
