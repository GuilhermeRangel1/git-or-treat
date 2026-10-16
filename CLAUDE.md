# Claude Code

@AGENTS.md

Este arquivo adapta a configuração do Claude Code. As instruções comuns aos agentes ficam em `AGENTS.md`; cada pasta de serviço e `docs/` tem um `CLAUDE.md` curto que importa seu `AGENTS.md` local quando Claude trabalha naquela área.

As diferenças específicas do Claude Code ficam em `.claude/settings.json` e nos arquivos de `.claude/`. Os scripts de hooks são compartilhados em `.hooks/` e têm também uma configuração Codex em `.codex/hooks.json`.

As skills canônicas ficam em `.agents/skills/` para o Codex. `.claude/skills/` contém adaptadores pequenos que apontam para as mesmas instruções canônicas, para que o Claude Code também possa descobri-las sem manter cópias completas.
