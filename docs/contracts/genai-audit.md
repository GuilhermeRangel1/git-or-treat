# GENAI-08 — trilha durável e privacidade

## Política desta entrega

A pessoa usuária aprovou em 31/10/2026 **30 dias** de retenção para a auditoria técnica. O case e o PRD não estipulam um prazo; este é um critério operacional adotado pelo projeto. O prazo começa no recebimento confirmado pelo Backend, em UTC. A consulta administrativa oculta imediatamente registros vencidos. O lifespan do Backend habilitado para Gold ou ingresso de auditoria executa expurgo na inicialização e a cada hora; portanto, a remoção física pode levar até uma hora adicional enquanto o serviço estiver ativo. Se o serviço estiver parado, expurga ao reiniciar. Falha gera aviso fixo e exige intervenção operacional; não altera a data de expiração.

A tabela `public.genai_audit_events` é operacional. A migração `genai08000001` cria índices de correlação/data e expiração e revoga privilégios de `PUBLIC`. Nenhuma concessão é adicionada ao leitor Gold. A prova PostgreSQL verifica recusa de leitura, inserção e remoção pelo login analítico. Não usar a credencial do leitor para auditar nem conceder o token de auditoria a pessoas usuárias do portal.

## Caminho executado

Portal → Backend `app.main:app` → auditoria inicial confirmada → planejar GenAI → gate/consulta Gold → auditoria do resultado → sintetizar GenAI → confirmação durável → revalidação de escopo/publicação → resposta pública.

O Backend grava eventos pelo `AuditStore` com a conexão operacional. O adaptador `BackendEventSink`, composto por `create_app`, envia os eventos do `EventTrace` para `POST /api/v1/internal/genai-audit-events`. Esta rota aceita somente escrita por token dedicado; não chama a rota de perguntas nem executa SQL analítico. A confirmação 201 só ocorre depois do commit. Não existe GET público ou interno de leitura por esse token. A correlação no cabeçalho deve coincidir com o evento.

As credenciais são configuradas privadamente por `GENAI_AUDIT_WRITE_TOKEN` no Backend e `GENAI_AUDIT_URL`/`GENAI_AUDIT_WRITE_TOKEN` no serviço GenAI. Configuração parcial ou ambígua é recusada. O adaptador não segue redirecionamentos, usa timeout de 2 segundos e exige confirmação com referência opaca. Habilitar essa configuração torna a auditoria obrigatória também na composição GenAI. Tokens de sessão e de planejamento/síntese não substituem o token de auditoria.

O núcleo continua sem driver, HTTP ou imports do Backend. As requisições de auditoria são uma comunicação técnica interna adicional, sem callback para a API pública de perguntas. Cada gravação SQL tem timeout de 2 segundos e de lock de 500 ms. O coordenador conserva um único prazo de 35 segundos desde a auditoria inicial até a revalidação final; confirmar a trilha não renova o orçamento.

## Conteúdo permitido e limites de reprodução

Eventos têm schema fechado: estágio/código/estado, correlação, duração, contagens, versão de contrato/catálogo/prompt e fingerprints. Eventos do Backend vinculam também pessoa opaca, lote, origem e métrica admitidos no servidor. Pergunta, histórico, linhas, valores de filtros, SQL, prompts completos, segredos e textos de exceção não são persistidos. `genai-grounding-v1` identifica as instruções efetivamente utilizadas pelos provedores; alteração de instruções exige nova versão. Hashes e IDs não são anonimização e a trilha permanece restrita.

`audit_reference` da resposta Gold é o UUID opaco de um evento persistido do Backend; a consulta administrativa por essa referência retorna a trilha correlacionada dos dois serviços dentro da retenção. Uma referência não concede acesso. O processo administrativo precisa de acesso autorizado ao ambiente operacional e ao banco; não há nova permissão concedida a sessões do portal.

**Limite atual:** a trilha é confirmada e vinculada à execução, mas não retém o plano completo nem valores dos parâmetros, template SQL ou resultado agregado. Ela permite investigar estágios e localizar plano/catálogo/lote; ainda não reexecuta sozinha a consulta. A reprodução independente com artefato autorizado de controle permanece aberta e não é substituída pelo fingerprint. Não há reconciliação com lote Gold real nem aprovação de política de preservação excepcional além dos 30 dias.

## Operação administrativa

Executar no ambiente privado do Backend, com `DATABASE_URL` operacional já configurada; não colocar credencial na linha de comando:

```sh
python scripts/genai_audit.py --reference <audit_reference>
python scripts/genai_audit.py --purge
```

O primeiro comando retorna somente eventos ainda válidos; referência desconhecida/expirada retorna lista vazia. O segundo é idempotente e remove somente registros com `expires_at <= agora`. Falhas imprimem mensagem fixa, sem DSN ou detalhes SQL. Monitorar o aviso do expurgo e verificar sua execução antes de habilitar tráfego real. Backups e cópias externas precisam de política própria antes da implantação; o comando não remove backups.

## Evidência de integração

`backend/tests/test_genai_session_postgres.py` usa PostgreSQL 16 descartável, migrações reais, leitor analítico restrito, rota pública Backend e processos GenAI separados. O ingresso durável é outro processo `uvicorn app.main:app` por TCP, usando o mesmo banco operacional. O teste confirma eventos dos dois serviços, referência pública persistida e ausência do valor de filtro nos eventos. Token de auditoria inválido impede consulta métrica e resposta com evidência.

`backend/tests/test_genai_audit.py` cobre persistência após nova instância, consulta por referência, expiração exata em 30 dias, expurgo idempotente, autenticação do ingresso e rejeição de campos livres/aninhados. `ai-agent/tests/test_durable_audit.py` cobre confirmação inválida, indisponibilidade e bloqueio antes da fonte/modelo. As suítes existentes cobrem minimização, injeção, saída inválida e fundamentação. A evidência contém somente dados sintéticos; não conclui IA-03/IA-06 ou GENAI-08 integralmente.
