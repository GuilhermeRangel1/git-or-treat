# Entrega do backend de ordens para o frontend

23/10/2026. DEV-06 / WEB-05, com autenticação das ordens preparada para identidade individual. Decisão: [ADR-0012](../decisions/0012-autenticacao-individual-das-ordens.md). Contrato funcional: [criação, consulta e idempotência](inspection-orders-dev06.md).

## Estado da entrega

O backend valida tokens individuais OIDC, aplica permissões de leitura/escrita e identifica o operador nos eventos de criação/transição. O proxy não cria credenciais nem autentica usuários. **A tela básica existente recebe 401 até a pessoa responsável pelo frontend integrar login e envio de Bearer.** Esse comportamento é esperado; não restaurar a injeção automática para contorná-lo.

Não há cadastro de usuário/senha ou endpoint de login inventado na API. Login, emissão e renovação de tokens pertencem ao provedor OIDC escolhido pela equipe. A configuração real desse provedor e o ingresso HTTPS são tarefas de implantação. Os testes usam chaves RSA efêmeras e identidades artificiais; não afirmam integração com uma conta real de SSO.

## Configuração do backend

Configurar no ambiente privado do processo, usando os valores reais do provedor:

```dotenv
APP_ENV=production
ORDERS_AUTH_MODE=oidc
OIDC_ISSUER=https://identity.example.invalid/tenant
OIDC_AUDIENCE=grid360-api
OIDC_JWKS_URL=https://identity.example.invalid/tenant/jwks
```

Os endereços acima são exemplos, não serviços utilizáveis. Remover `ORDERS_READ_TOKEN` e `ORDERS_WRITE_TOKEN` no modo OIDC. O processo recusa produção com autenticação de serviço, OIDC sem configuração completa, URLs sem HTTPS ou credenciais compartilhadas em paralelo. A audiência deve identificar esta API, não o client ID do frontend. Configurar os hosts e origens reais do ingresso sem wildcard. Não fornecer segredo do cliente ao navegador.

Contrato aceito do token de acesso:

- Assinatura RS256, RSA com pelo menos 2048 bits e `kid` da chave publicada no JWKS configurado no servidor. URLs `jku`/`x5u` do token não são usadas.
- `iss` e `aud` correspondentes à configuração; `sub` individual, não vazio; `iat` e `exp` inteiros em segundos, com duração positiva de até 3600 segundos. Validade/`nbf` verificados, tolerância de relógio de 15 segundos.
- Claim `scope` como string com permissões separadas por espaço: `orders:read` e/ou `orders:write`. Escrita inclui leitura. Perfis do provedor precisam ser mapeados a esses scopes; a API não interpreta nomes arbitrários de cargos ou claims `roles`/`scp`.
- JWKS em cache por até 300 segundos, timeout de busca de 3 segundos. `kid` desconhecido é recusado sem forçar refresh por requisição; publicar chaves novas com antecedência e manter sobreposição na rotação. Token acima de 8192 caracteres é recusado.

Não usar ID token como substituto do token de acesso desta API. Revogar usuário no provedor não invalida retroativamente um JWT já emitido antes de seu vencimento; política de sessões/revogação imediata depende do provedor/ingresso. Esta API não implementa introspecção ou lista de revogação local.

Para desenvolvimento por CLI/Swagger, `APP_ENV=development` e `ORDERS_AUTH_MODE=service` preservam as credenciais de serviço de leitura/escrita existentes, com ao menos 32 caracteres e valores distintos. **Não enviá-las ao frontend.** Sem credencial válida, as ordens continuam fechadas.

## Integração no frontend

1. Integrar o cliente oficial do provedor OIDC, com fluxo de login apropriado à aplicação (por exemplo, Authorization Code com PKCE). Um BFF pode manter a sessão no servidor e encaminhar o token individual; ele não faz parte desta entrega.
2. Enviar `Authorization: Bearer <access_token>` no transporte das rotas de ordens. O proxy Vite encaminha o header recebido e não o substitui. `ORDERS_DEV_PROXY_TOKEN` deixou de ter efeito; removê-lo da configuração antiga.
3. Consultar `GET /api/v1/inspections/access` para obter a identidade opaca e permissões. Resposta autenticada, sem cache:

```json
{
  "actor": "oidc:<identificador-opaco>",
  "auth_mode": "oidc",
  "permissions": ["orders:read", "orders:write"]
}
```

O ator é derivado pelo servidor de emissor + subject, sem expor nome/email. Não enviá-lo em payload ou header para escolher o operador. Não é um login, um segredo nem uma autorização por si só. Um token válido sem scopes de ordens recebe a lista vazia nesta rota e 403 ao tentar operar ordens.

4. Exibir ações conforme permissões; a API continua aplicando o controle independentemente de botões ocultos. Ao trocar usuário/logout, limpar credenciais e caches remotos do usuário anterior; incluir a identidade nas chaves de consulta. Não gravar credenciais de serviço, tokens ou perfis em fixtures, logs ou bundle.
5. Na criação, gerar uma chave de idempotência por intenção, preservar corpo/chave em reenvios e mostrar sucesso apenas após 200/201. Se precisar renovar o token após 401, não trocar a chave nem o conteúdo da intenção. 409 inclui dados estruturados para abrir a ordem existente.

Sem autenticação individual integrada, manter estado de acesso negado; não mostrar criação simulada ou sucesso local. A implementação visual fica com a pessoa responsável pelo frontend.

## Rotas e erros

Leitura: `/inspections/orders`, `/orders/search` e `/orders/{id}` exigem `orders:read` ou `orders:write`. Criação manual, criação em `/inspections/queue/{uc_id}/orders` e atualização exigem `orders:write`. Todas têm prefixo `/api/v1`. `/inspections/access` exige identidade válida; não consulta a fonte analítica.

- 401: Bearer ausente/inválido/expirado, assinatura, emissor, audiência ou chave não aceitos. Autenticar/renovar no provedor.
- 403: identidade válida sem permissão para a ação. Não repetir como erro transitório.
- 409: conflito operacional, com `detail` e `error: {code, message, order_id}`.
- 422: entrada inválida. Corrigir campos preservando o formulário.
- 503: identidade ou fonte necessárias indisponíveis. Manter estado de falha; nunca fazer fallback para dados/credenciais locais.

A autenticação individual protege as ordens. Os endpoints analíticos demonstrativos seguem a política da ADR-0007; liberação de Gold real e perfis de outras áreas continuam requisitos separados. Não há regra de propriedade individual por ordem aprovada no domínio: operadores com scope de leitura/escrita atuam no conjunto operacional, com identidade individual.

## Execução e verificação

Aplicar `alembic upgrade head` em banco existente para a DEV-06; esta alteração de autenticação não acrescenta migração. Instalar `backend/requirements.txt` com `PyJWT[crypto]==2.15.1`. Nunca copiar arquivos `.env` privados para o frontend.

Compose publica PostgreSQL/API/frontend somente em `127.0.0.1`. O Vite usa localhost por padrão; o bind `0.0.0.0` dentro do contêiner continua necessário e não muda a publicação local. Compartilhar o portal em rede/produção exige ingresso HTTPS e configuração deliberada; não abrir portas para contornar autenticação.

Verificações desta entrega: suíte backend com PostgreSQL descartável, testes OIDC com assinaturas reais, teste HTTP `npm run test:proxy`, frontend e gates. O teste do proxy também está no CI. Não foi configurado um provedor real nem criado um fluxo visual de login nesta entrega.
