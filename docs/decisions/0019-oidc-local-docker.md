# ADR-0019 — OIDC local em Docker para a integração Gold

Data: 29/10/2026. Estado: execução autorizada pela pessoa usuária ao escolher OIDC local em Docker. Requisitos relacionados: WEB-01 a WEB-07 e preparação de WEB-10, sem alteração dos critérios de aceite.

## Decisão

Usar Keycloak em Docker como provedor local, com publicação restrita a `127.0.0.1`, realm `grid360`, cliente público `grid360-web` e audiência da API `grid360-api`. O frontend usa Authorization Code com PKCE S256 e envia o access token individual à API. Tokens ficam em memória; o estado temporário necessário ao retorno do redirecionamento pode usar sessionStorage. Credenciais geradas para as identidades artificiais ficam apenas na área local ignorada pelo Git.

Leitura e escrita usam client scopes OIDC vinculados a papéis administrativos no Keycloak, com `Full Scope Allowed` desativado. A identidade somente leitura não pode obter escrita apenas solicitando um scope: o provedor omite scopes para os quais a identidade não tem o papel associado. A API verifica o claim padrão `scope`. Troca de identidade e saída cancelam consultas, descartam caches remotos e reiniciam a identidade da publicação Gold. Renovação da mesma sessão preserva a intenção de criação de ordem.

Para o provedor de desenvolvimento, permitir HTTP somente mediante `OIDC_ALLOW_LOCAL_HTTP=true`, com `APP_ENV=development`, e somente em URLs cujo hostname seja literalmente `localhost` ou `127.0.0.1`, sem credenciais, query ou fragmento. Essa exceção explícita complementa a exigência HTTPS da ADR-0012 para o ambiente local. Produção mantém HTTPS obrigatório e recusa a opção local. Assinatura, emissor, audiência, expiração e scopes continuam validados.

## Limites e comprovação

O provedor local não define a implantação de produção, autorização territorial ou revogação imediata. A carga Gold e os históricos operacionais permanecem sob os contratos existentes. O script da demo sintética continua sendo uma execução distinta, sem login.

Testes de contrato e verificações HTTP comprovam apenas os comportamentos efetivamente executados. A validação visual das jornadas exige navegador disponível; falha de ferramenta deve permanecer registrada nas evidências, sem aceite integral por inferência.

Fontes técnicas consultadas: [Keycloak em Docker](https://www.keycloak.org/getting-started/getting-started-docker), imagem 26.8.1, [importação de realm](https://www.keycloak.org/server/containers) e [UserManager do oidc-client-ts](https://authts.github.io/oidc-client-ts/classes/UserManager.html).
