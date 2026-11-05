---
name: genai-evaluation
description: Crie baselines e avalie regressões de interpretação, planos, evidências e respostas do Assistente ou dos insights GenAI neste repositório.
---

# Avaliação do GenAI

Parta dos critérios IA do [PRD](../../../docs/PRD.md) e da matriz de fronteiras da [genai-gold](../genai-gold/SKILL.md). Localize os runners, fixtures e relatórios existentes em `ai-agent/tests`, `ai-agent/scripts` e `backend/scripts` antes de acrescentar infraestrutura.

## Montar a amostra

Comece pelas perguntas reais que falharam, usando versões sem dados identificáveis. Acrescente paráfrases, ambiguidades, acompanhamentos, conceitos e operações analíticas suportadas ou ainda ausentes. Reserve perguntas inéditas para avaliar generalização separadamente dos exemplos usados no desenvolvimento.

Para cada caso, registre intenção esperada, métrica e unidade, período, filtros, operação, requisitos de cobertura e resultado aceitável. Diferencie esclarecimento necessário, capacidade ausente e falta de dados. Números esperados precisam de consulta ou cálculo de referência independente da implementação avaliada.

## Comparar versões

Fixe commit, configuração relevante, provedor/modelo, versões de prompt e catálogo e referência da publicação Gold. Compare a mesma amostra sob condições equivalentes. Registre indisponibilidade e timeout como resultados, com denominadores explícitos para casos elegíveis e casos executados.

Classifique a primeira divergência entre interpretação, capacidade, dados/execução e síntese. Meça conforme a mudança avaliada, incluindo correção da intenção e dos números, sucesso em perguntas legítimas suportadas, recusas indevidas, esclarecimentos adequados, fundamentação, utilidade, latência p50/p95 e consumo do modelo quando disponível.

Valide isolamento de sessão e bloqueio de execução não autorizada nas mudanças que afetem essas fronteiras. Use banco descartável para testes que criem ou alterem estado. Execuções reais de provedor consomem orçamento e seguem a autorização da tarefa.

## Avaliar propostas semânticas

Em shadow mode, observe a proposta sem encaminhá-la ao executor. Compare-a com a intenção de referência, inclusive quando o caminho determinístico teve sucesso aparente. Distinga plano estruturalmente válido de plano semanticamente correto. A promoção para fallback executável exige evidência das duas propriedades nas perguntas relevantes.

## Relatar

Registre comandos e resultados observados, amostra elegível/executada, comparação com o baseline e falhas por etapa. Mantenha logs sanitizados, com IDs e códigos em lugar de perguntas privadas, registros Gold ou credenciais. Declare o alcance da prova, distinguindo fixtures, integração e avaliação com Gold v2. Preserve o estado pendente dos aceites sem evidência suficiente.
