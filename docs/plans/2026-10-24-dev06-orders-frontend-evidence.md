# DEV-06 — frontend de Ordens: evidências de 24/10/2026

## Referência e revisão

- WEB-05 permanece `Em validação`. Implementação por **dois subagentes GPT-6 Luna/high**, separados entre página/lista e painéis/transporte; revisão e integração pelo agente principal.
- Figma `oTjmpIBgbA7OOYb9ZmMG9K`, seção `05 · Ordens` (`249:12417`). Contextos completos e screenshots: lista `16:640`/`16:1894`, mobile `195:8099`/`198:8416`, ações `16:710`/`16:1964` e `195:8186`, erro `211:4904`, confirmação `211:4967`. Feedback confirmado no componente `211:4899`.
- A abertura segue `Abrir ações`/`Ações da ordem`. Após esclarecimento da pessoa usuária, não foi acrescentada barra/modal de filtros à camada 05; os parâmetros da URL/API continuam suportados. Os painéis reutilizam a estrutura de modal padronizada do portal. Conteúdo/IDs e estados são reais da API demonstrativa; textos de simulação não foram copiados como alegações de comportamento.
- Reutilizados layout, tokens, fontes, Button/Modal e ícones Lucide existentes; variantes aditivas para ações neutras/perigo e dimensões dos painéis. Nenhuma dependência instalada ou backend funcional alterado. A alteração alheia de `frontend/package-lock.json` foi preservada.

## Gates

- Suíte frontend global: `npm.cmd test -- --reporter=dot` → **166 aprovados em 21 arquivos**.
- Após os refinamentos visuais finais: recorte de página, ações, fundamentos e transporte → **33 aprovados em 4 arquivos**.
- Lint sem avisos, fronteiras em **103 arquivos**, build TypeScript/Vite e format:check aprovados. Nova rodada de build/formatação após os refinamentos finais.
- Sintaxe PowerShell validada pelo parser e execução real do novo `scripts/start-orders-demo.ps1` com Alembic e SQLite em arquivo.

## Jornada com API real

Demo exclusiva em `127.0.0.1:8010`, frontend `localhost:5180`, preservando os processos existentes em 8000/5173. Banco `work/dev06-demo/orders.sqlite`; desenvolvimento/fonte sintética/modo demo explícitos, sem login e sem alteração de `.env`.

1. Fila → UC-1004 → criar: **201**, ordem 1 com snapshot. Resultado vazio mostrou validação e focou o campo. Registro de resultado: **200**, painel fechado e feedback confirmado; recarga preservou o texto.
2. Ordem 1 passou PENDENTE → EM_ANDAMENTO → CONCLUIDA por respostas **200**. Após recarga, campos ficaram desabilitados, sem cancelar/reabrir.
3. Fila → UC-1002 → criar: **201**, ordem 2. `Manter ordem` retornou ao painel; confirmação de cancelamento: **200**, estado CANCELADA preservado na recarga.
4. Fundamentos UC-1002 mostraram estimativa ausente sem convertê-la em zero e competências `jan/2025 a fev/2025`. Escape devolveu o foco ao acionador.
5. Nova intenção para UC-1004 após encerramento criou a ordem 3 PENDENTE, disponível para exploração manual.
6. API/frontend criados nesta tarefa foram encerrados e reiniciados pelo mesmo script. O banco manteve as três ordens: 1 CONCLUIDA com resultado, 2 CANCELADA e 3 PENDENTE. Nenhum processo da instância anterior em 8000/5173 foi encerrado.

## Visual e acessibilidade

- Claro/escuro em 320, 390, 768 e 1440 px, sem overflow horizontal da página. Capturas `work/dev06-orders-{width}-{theme}.png` após estabilizar as transições.
- Painéis de ações/confirmação conferidos a 320/390 px nos dois temas, sem overflow horizontal interno. Escape, retorno de foco e descarte de rascunho ao fechar/reabrir funcionaram. Capturas em `work/dev06-orders-{actions,confirm}-{width}-{theme}.png`.
- A emulação por viewport não substitui zoom nativo ou auditoria com leitor de tela. Dados dinâmicos e estrutura de modal compartilhada não permitem alegar reprodução pixel a pixel de todas as telas Figma.

## Acesso local e limites

```powershell
.\scripts\start-orders-demo.ps1 -BackendPort 8010 -FrontendPort 5180
```

Abrir **http://localhost:5180/ordens**, sem login. A instância foi deixada ativa para conferência da pessoa usuária. As ordens de demonstração ficam apenas no banco ignorado em `work/`.

Gold, homologação da regra e auditoria durável continuam pendentes; esta entrega não conclui WEB-05. Sem nova consulta ao Trello: checklist fornecido na conversa, acesso ao quadro já indisponível nas tentativas anteriores.
