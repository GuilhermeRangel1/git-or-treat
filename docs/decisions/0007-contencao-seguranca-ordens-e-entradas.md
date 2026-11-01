# ADR-0007 — contenção das falhas locais de segurança

**Data:** 21/10/2026. **Estado:** política conservadora implementada no pedido de correção; revisão do time pendente. **IDs:** WEB-01, WEB-05, WEB-10 e WEB-11. Não conclui os critérios funcionais ou o sistema de perfis.

**Atualização em 29/10/2026:** identidade individual e modos de acesso estão definidos na [ADR-0020](0020-autenticacao-backend-por-sessao.md). Credenciais compartilhadas permanecem restritas a desenvolvimento por CLI/Swagger; a demo continua limitada a dados sintéticos. O texto abaixo registra a contenção original e seus limites naquela data.

## Contexto e alternativas

A auditoria local comprovou escritas anônimas em ordens, reabertura sem política, dados incompatíveis com o esquema e erros internos por IDs ou JSON extremo. Ainda não há provedor de identidade, usuários ou associação de cada ordem a um proprietário. Manter as rotas abertas conserva a vulnerabilidade; criar agora um login completo inventaria cadastro e regras de WEB-10. A alternativa adotada é bloquear por padrão e habilitar clientes de serviço com escopo explícito.

## Decisão

- Rotas `/inspections/orders` exigem Bearer de serviço configurado no backend. `ORDERS_READ_TOKEN` permite listar; `ORDERS_WRITE_TOKEN` permite listar, criar e atualizar todas as ordens deste serviço. São credenciais distintas, aleatórias, com ao menos 32 caracteres, comparadas em tempo constante e representadas por SecretStr. Não são contas humanas nem delimitam posse individual de ordem. Sem credencial: 401; credencial inválida: 401; leitor tentando escrever: 403; Bearer apresentado com configuração ausente: 503. Analytics sintéticos permanecem públicos no ambiente de demonstração.
- Tokens não entram no frontend, na URL, em logs ou no Git. Revogação e rotação ocorrem alterando a configuração do servidor. Integração futura do portal operacional requer sessão de usuário/BFF ou provedor de identidade; não se deve expor o token de escrita no browser. Transporte de produção exige HTTPS no ingresso.
- Política provisória: PENDENTE → EM_ANDAMENTO ou CANCELADA; EM_ANDAMENTO → CONCLUIDA ou CANCELADA; CONCLUIDA/CANCELADA são finais. Conclusão exige resultado não vazio. Alteração de uma ordem final é 409; repetição sem mudança de campos é aceita. Reabertura fica indisponível até decisão explícita do produto.
- A atualização usa condição atômica pelo ID e pelo status previamente observado, com contagem de linhas e rollback. Isso impede transição baseada em estado antigo de sobrescrever cancelamento concorrente. Não constitui controle de versão completo de todos os campos nem idempotência da criação.
- Identificador HTTP de ordem: 1 a 2^63−1. UC/motivo: strings não vazias e aparadas, até 50/255 caracteres. Prioridade: BAIXA, MEDIA ou ALTA. Notas e resultado: até 4.000 caracteres. Campos desconhecidos são rejeitados.
- Um middleware ASGI limita corpo a 65.536 bytes, contando os chunks recebidos, e JSON a 32 níveis estruturais. JSON deve usar UTF-8; bytes nulos/codificações UTF-16/UTF-32 são rejeitados antes do parser. Caracteres entre aspas não contam como estrutura. Excesso responde 413; codificação inválida, 400. Valores numéricos não finitos (incluindo overflow para infinito), Unicode inválido e NUL escapado são recusados com 400; formatos de corpo não JSON em POST/PUT/PATCH são recusados com 415. Não se mascara erro interno genérico como validação.
- Hosts permitidos são configurados por BACKEND_ALLOWED_HOSTS; padrão de desenvolvimento: localhost, 127.0.0.1, backend e testserver. Ingresso de produção precisa de lista específica. API recebe nosniff, frame denial, referrer policy, permissions policy e CSP restritiva; a CSP da API não é aplicada ao Swagger/ReDoc para preservar sua UI.
- Dockerfile atualiza pip para 26.2.2 antes de instalar requisitos. Não altera a base Hardened aprovada na ADR-0005.

## Consequências e limites

Não há mudança de esquema ou migração. Ordens e Gold continuam separadas. Os clientes antigos das rotas operacionais precisam de credencial; o Panorama permanece sem token. Eventos de transição produzem registro de logging com ID e estados, sem payload ou segredo, mas trilha durável por usuário, cargos, posse de ordem, expiração de credenciais, idempotência de criação e limites distribuídos de taxa ainda exigem implementação própria. Esses limites mantêm WEB-05 e WEB-10 pendentes.

O pedido de correção autoriza essa contenção reversível, não afirma homologação definitiva do fluxo de fiscalização. O PRD e o guia backend registram a política e suas pendências.

## Fontes e verificação

FastAPI 0.156.8 e SQLAlchemy 2.1.5 instalados no container. APIs consultadas via Context7: [HTTPBearer](https://fastapi.tiangolo.com/reference/security/), [TrustedHostMiddleware](https://fastapi.tiangolo.com/advanced/middleware/) e [Query.update/rowcount](https://docs.sqlalchemy.org/en/20/orm/queryguide/query.html#sqlalchemy.orm.Query.update). Evidência de regressões, PostgreSQL descartável e limites do rebuild no [relatório de segurança](../security/2026-10-21-auditoria-local.md).
