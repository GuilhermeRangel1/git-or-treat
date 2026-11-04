# Histórico de conversas por usuário

Cartão Trello: [Histórico de conversas](https://trello.com/c/iuZWdUTZ/21-hist%C3%B3rico-de-conversas-por-usu%C3%A1rio). Branch `feat/genai-historico-conversas`, criada da `develop` em `10135a7`. Implementação e revisão técnica concluídas nesta branch; integração à develop pendente de PR e merge.

## Política aprovada

Em 02/11/2026, a pessoa usuária aprovou conversas privadas da identidade autenticada, retenção de 30 dias após a última interação, exclusão imediata do conteúdo quando a conversa é apagada e auditoria técnica separada, sem texto das mensagens. A aprovação vale para o histórico; a política de retenção anterior da auditoria não autorizava persistir conversas.

- Proprietário é `AuthUser.id`, obtido da sessão no Backend em cada operação. O cliente não informa o proprietário nem permissões. Perfil administrativo não concede acesso às conversas de outra pessoa.
- Abertura, listagem e renomeação não renovam a retenção. A conversa expirada fica inacessível imediatamente e o Backend remove seus registros no ciclo de expurgo horário. Apagar remove conversa e mensagens na mesma transação.
- A auditoria continua no serviço existente e recebe apenas metadados definidos no contrato técnico; pergunta, resposta e título não entram no evento. A evidência de código não substitui revisão da política operacional.

## Contrato implementado

O armazenamento fica no PostgreSQL operacional do Backend, separado da Gold e do banco GenAI. `ai_conversations` guarda proprietário, título neutro, revisão e datas; `ai_conversation_exchanges` guarda IDs estáveis, sequência, versão do formato, hashes da requisição/escopo, estado, pergunta e resposta pública. Tokens de continuidade não são persistidos. Índices e restrições cobrem propriedade/listagem, expiração, criação idempotente, unicidade por tentativa e ordenação.

A migração `genaihistory01` é filha de `genai12000001`. O script `backend/scripts/provision_backend_app.sql` concede CRUD operacional das duas tabelas ao papel do Backend e não muda privilégios do leitor Gold. O leitor não recebe acesso às tabelas do histórico.

Rotas sob `/api/v1/ai/conversations` exigem sessão individual e `ai:ask`: criar, listar, abrir, renomear, excluir e enviar pergunta. Essa permissão acompanha a matriz WEB-10 e permite o histórico privado aos cinco perfis, independentemente do acesso a ordens. Todas as consultas de armazenamento filtram proprietário e expiração. Renomear exige revisão; envio e criação usam IDs de requisição. Uma reserva pendente tem lease; repetição da tentativa concluída devolve a resposta salva, e tentativa atrasada não substitui uma recuperação mais nova nem ressuscita conversa excluída.

O formato público tipado limita lista a 50 conversas e detalhe a 200 trocas. JSON incompatível, resposta inválida ou escopo diferente é apresentado como indisponível, sem expor conteúdo. Contexto só é reconstruído de mensagens concluídas, validadas e do mesmo escopo. A resposta histórica é identificada como salva; atualizar exige nova consulta à publicação atual.

O Assistente tem acesso a `Conversas` para listar, abrir, renomear e excluir com confirmação. Criação ocorre no primeiro envio; rascunhos ficam apenas em memória. A tela explica a retenção, separa respostas históricas das atuais e descarta resposta atrasada ao trocar identidade ou desmontar a conversa. No modo sem sessão, mantém a conversa temporária existente.

## Evidências executadas em 02/11/2026

- Backend focado: `tests/test_ai_history_http.py`, `tests/test_ai_history_store.py`, `tests/test_ai_conversations_contract.py`, `tests/test_genai_continuation.py` e `tests/test_database.py`: **35 passaram**. Regressão Backend completa: **997 passaram, 117 ignorados**; a execução usou fonte sintética e origens de teste aplicadas apenas em memória, preservando o `.env` Gold. Um aviso preexistente de `Starlette/httpx` permaneceu.
- Frontend completo: `npm test -- --run`: **425 passaram, 1 ignorado**. `npm run build` passou. `npm run lint` terminou sem erros e apontou somente o aviso preexistente em `AuthProvider.tsx:108`.
- Migração PostgreSQL em banco descartável: upgrade desde base até `genaihistory01` e downgrade até base passaram; banco removido. Uma prova concorrente no PostgreSQL passou para criação idempotente, reserva única, replay sem nova resposta, exclusão e rejeição de resposta atrasada.
- API local com Gold v2 e Gemini: duas respostas agregadas de Receita (Olinda, junho e maio de 2026) passaram; continuação preservou município e métrica. Repetição do mesmo ID retornou a mesma referência, segunda identidade recebeu 404 ao tentar abrir conversa alheia, renomeação/exclusão passaram. As duas respostas foram reconciliadas por consulta SQL independente, somente leitura, contra a mesma publicação.
- Chromium real, sem interceptação: envio e restauração após refresh, histórico marcado como antigo, retenção explicada, renomeação, exclusão, layout em 390/1440 px e sem overflow passaram. O teste frontend de sessão cobre troca de identidade com resposta imediata e atrasada; a API cobre revogação durante a chamada.
- Contas temporárias, sessões e conversas foram removidas. Verificação posterior retornou zero contas/sessões/conversas temporárias; banco descartável removido. Artefatos de teste e credenciais ficaram em `work/followup-validation` (ignorado pelo Git); tokens de continuidade foram removidos das evidências privadas.
- `git diff --check` passou. `ruff` não estava instalado no container de validação; os módulos foram importados/exercitados pela suíte Backend.

## Limites e estado de entrega

A prova de migração completa foi feita em banco PostgreSQL descartável com marcador Alembic consistente. A cópia Gold local existente já tinha revisão `20261102_cadastro`, divergente da cadeia desta branch; não foi carimbada nem alterada para simular um upgrade. A API integrada foi testada na cópia local de validação, onde o papel `v_energy_app` é superusuário, então ela não prova privilégio efetivo mínimo desse papel. A consulta efetiva confirmou que `venergy_genai_reader` não tem `SELECT` nas tabelas do histórico; o provisionamento versionado do Backend declara os grants restritos necessários.

Implementação, testes locais e revisão técnica do consumidor/Backend concluídos por Codex; a pessoa usuária autorizou o encerramento com essa revisão. Cartão concluído nesta entrega local; integração à develop pendente de PR e merge. O adicional não cria nem altera estado de IA-01 a IA-07 no PRD.

### Revisão técnica final — 02/11/2026

Revisão automatizada independente dos eixos de requisitos e padrões encontrou dois defeitos, corrigidos antes da entrega: pergunta persistida inválida agora torna apenas a troca indisponível; abrir uma tentativa interrompida não vincula perguntas novas ao ID antigo. Retry conhecido em memória preserva o envio original; após refresh, nova pergunta usa novo ID e respeita o lease da execução anterior.

Verificações após as correções: `docker exec followup-validation-backend-1 python -m pytest -q tests/test_ai_history_store.py tests/test_ai_history_http.py tests/test_ai_conversations_contract.py`: 25 passaram; testes frontend de sessão/histórico: 11 passaram; build passou; lint sem erros, com aviso preexistente; `git diff --check` passou. As suítes completas acima precedem estas duas correções. A pessoa usuária autorizou aceitar a revisão técnica de Codex como revisão do consumidor para esta entrega. Os dois achados foram corrigidos e revalidados; cartão concluído em 10/10. Isso não declara uma revisão humana externa nem integração à develop.
