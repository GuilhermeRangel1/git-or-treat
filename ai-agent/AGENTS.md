# Regras do agente de IA

Leia `../docs/services/ai-agent.md` e os IDs IA de `../docs/PRD.md`.

Para estender o núcleo, trocar a fonte, alterar interpretação, segurança ou geração, siga [genai-gold](../.agents/skills/genai-gold/SKILL.md). Identifique o consumidor e a composição de produção da mudança; preparação isolada deve ser declarada como tal.

- Consulte somente tabelas Gold autorizadas, com credencial somente leitura, limite e timeout.
- Valide a consulta gerada antes de executá-la.
- Toda resposta numérica deve expor período, filtros, unidade, fonte e fundamento reproduzível.
- Quando faltar evidência, declare a limitação e não invente valores.
- Teste sinônimos, perguntas de acompanhamento, recusa, prompt injection e reconciliação numérica.
