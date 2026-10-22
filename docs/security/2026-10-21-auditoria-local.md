# Teste de segurança local — 21/10/2026

Base: `dev02`, commit `5616f59`. Escopo: portal React/Vite e API FastAPI locais, com dados sintéticos. O registro abaixo preserva a auditoria inicial; as correções posteriores estão descritas nesta atualização.

## Atualização após as correções — 21/10/2026

- SEC-01: ordens exigem credenciais de serviço separadas por leitura/escrita. Sem credencial, 401; leitor escrevendo, 403; configuração ausente com Bearer apresentado, 503. Tokens não foram criados no ambiente real nem colocados no frontend. As rotas ficam fechadas até configuração privada. É contenção de serviço, não implementação de login humano, cargos ou posse por usuário.
- SEC-02: IDs positivos limitados a bigint antes do acesso ao banco; os dois IDs excessivos da auditoria agora são rejeitados com 422 quando autenticados.
- SEC-03: middleware limita bytes e profundidade do JSON, rejeita codificações inválidas, NUL e Unicode malformado. Profundidade/tamanho excessivos: 413. Na revisão da correção, NaN/Infinity e overflow numérico também reproduziram 500 e receberam regressão; agora são 400. Formatos inesperados de corpo recebem 415. Valores de string que contêm colchetes continuam válidos.
- SEC-04: estados finais não reabrem; transições inválidas e alterações finais são 409; concluir exige resultado. Atualização condicional por status evita sobrescrever uma mudança concorrente. Política conservadora, critérios de cargo e trilha durável continuam pendentes em WEB-05/WEB-10.
- SEC-05: campos vazios/excessivos e prioridades desconhecidas são rejeitados antes da gravação. Limites verificados também em PostgreSQL 18 descartável, com usuário sem superusuário, preservando o banco de desenvolvimento.
- Endurecimento adicional: hosts fora da allowlist retornam 400; respostas da API incluem CSP restritiva, nosniff, frame denial, referrer policy e permissions policy. Swagger/ReDoc permanecem disponíveis.
- Dependências: pip atualizado para 26.2.2 no container local e no Dockerfile. Nova execução de pip-audit: **zero avisos conhecidos em 36 pacotes**. O rebuild exato do Dockerfile não pôde ser confirmado: o registro dhi.io respondeu 401 na resolução da base. É necessário autenticar com docker login dhi.io e repetir docker compose build backend; a alteração no container atual não sobrevive a uma recriação a partir da imagem antiga.
- Validação final: **132 testes backend aprovados**, incluindo migrações e segurança em PostgreSQL descartável; compileall aprovado. Mantido um aviso de depreciação Starlette/httpx. Nova bateria adversarial: 40 verificações sem desvio de status esperado e 40 leituras reais, concorrência quatro, todas 200 (máximo observado 5,11 ms).
- Logging de transição foi verificado sem token/payload; o Alembic foi ajustado para não desativar os loggers existentes. Esses eventos não constituem trilha imutável ou identificação humana.
- Fonte: [ADR-0007](../decisions/0007-contencao-seguranca-ordens-e-entradas.md), testes backend de segurança, teste PostgreSQL e evidências locais ignoradas em work/security-fixes/. Os achados são considerados contidos nos caminhos testados; requisito funcional de ordens não foi concluído. Nenhum commit/push foi feito nesta correção.

## Resultado da auditoria inicial

Foram provocados erros HTTP 500 em dois tipos de entrada: JSON com profundidade excessiva e IDs de ordem fora do intervalo do banco. A aplicação não caiu como processo: a leitura do Panorama continuou respondendo depois. Há também falhas de controle de acesso e integridade nas ordens operacionais que devem ser resolvidas antes de usar dados reais.

O ensaio executou 39 verificações HTTP e uma bateria separada de 40 leituras concorrentes, limitada a quatro conexões. O roteiro foi repetido para confirmar os resultados. Todas as criações/alterações ocorreram em SQLite em memória, em processo isolado; não foram criadas ou alteradas ordens no PostgreSQL. Os resultados não demonstram o comportamento específico de gravações no PostgreSQL.

## Achados confirmados

### SEC-01 — P1 — ordens podem ser lidas, criadas e alteradas sem autenticação

- Evidência: sem cookies ou Authorization, `POST /api/v1/inspections/orders` devolveu 201, `GET /api/v1/inspections/orders` devolveu 200 e `PATCH /api/v1/inspections/orders/{id}` devolveu 200.
- Reprodução isolada: criar com `{"uc_id":"AUDIT-SYNTHETIC","reason":"Disposable security probe"}` e alterar a ordem retornada com `{"notes":"Updated without identity"}`. Não executar esta reprodução contra banco compartilhado.
- Causa: as dependências das rotas apenas obtêm sessão do banco; não verificam identidade nem escopo. A definição OpenAPI não declara esquemas de autenticação.
- Código: `backend/app/api/v1/endpoints/inspections.py:48`, `:62`, `:72`.
- Impacto: qualquer cliente com acesso de rede à API pode manipular ordens. CORS não substitui autorização. A exposição pública à Internet não foi verificada; o Compose publica portas da máquina.
- Correção proposta: autenticar antes das operações, exigir permissão de leitura/escrita e verificar acesso à ordem; testar negação por identidade/escopo. O detalhamento de cargos de WEB-10 continua separado da proteção mínima das escritas.

### SEC-02 — P2 — IDs maiores que bigint geram erro interno

- Evidência: `PATCH /api/v1/inspections/orders/9223372036854775808` com `{"status":"PENDENTE"}` devolveu 500; a execução diagnóstica identificou `OverflowError`. Um ID de cem dígitos reproduziu o erro.
- Esperado: rejeição 422 antes da consulta ou política 404 coerente, sem exceção interna.
- Código: `backend/app/api/v1/endpoints/inspections.py:72`; `backend/app/services/inspections.py:36`.
- Correção proposta: validar ID positivo com limite compatível com a coluna antes de consultar; acrescentar regressão para os limites. O erro foi confirmado com SQLite, não com PostgreSQL.

### SEC-03 — P2 — JSON profundamente aninhado gera erro interno

- Evidência: `POST /api/v1/ai/query` com Content-Type application/json e corpo composto por 1.500 pares de colchetes em volta de `0` devolveu 500; diagnóstico isolado: `RecursionError`.
- O payload tem aproximadamente 3 KB; um limite de tamanho isolado não substitui a restrição de profundidade/estrutura.
- Não foi comprovada queda do processo nem negação de serviço sustentada. A API respondeu normalmente depois.
- Correção proposta: rejeitar JSON que exceda limites de parsing com 400/413/422, conforme contrato definido; limitar profundidade e tamanho, revisar a estrutura dos filtros e testar preservação da disponibilidade. Não capturar genericamente toda exceção como entrada inválida.

### SEC-04 — P2 — ciclo de ordens não aplica política de transições

- Evidência: a mesma ordem passou para `CANCELADA` e voltou a `PENDENTE`, ambas as chamadas com 200. A alteração foi aceita sem identidade e sem registro de evento de transição.
- Código: `backend/app/services/inspections.py:36` atribui diretamente o status recebido.
- O guia backend ainda mantém o mapa de transições em aberto. O teste comprova ausência de controle, mas não determina qual deve ser a política de reabertura do negócio.
- Correção proposta: aprovar estados/transições e permissões, impor a política no servidor e registrar auditoria. WEB-05 continua pendente.

### SEC-05 — P2 — campos de ordens aceitam valores vazios e tamanhos incompatíveis

- Evidência: `{"uc_id":"","reason":"","priority":"not-a-valid-priority"}` devolveu 201 no banco descartável. Outro pedido com UC de 51 caracteres, motivo de 256, prioridade de 21 e notas de 100.000 caracteres também devolveu 201.
- Código: `backend/app/schemas/inspections.py:9` e `:16` não limitam tamanho/conteúdo. O modelo usa String(50), String(255) e String(20), mas SQLite não impõe esses comprimentos como PostgreSQL.
- Impacto confirmado: entradas vazias, prioridade arbitrária e corpo grande atravessam os schemas. Erro de gravação por comprimento em PostgreSQL é um risco inferido, não foi executado contra o banco real.
- Correção proposta: limitar strings no schema de entrada, remover espaços, recusar campos obrigatórios vazios e definir valores válidos de prioridade e limites dos textos livres. Testar também com PostgreSQL descartável.

## Dependências

- `docker compose exec -T frontend npm audit --json`: zero avisos conhecidos em 206 dependências avaliadas, incluindo desenvolvimento.
- `pip-audit` instalado em venv temporário `/tmp/grid360-security-audit`, sem alterar as bibliotecas da aplicação: 36 pacotes avaliados; avisos apenas para `pip 25.0.1`.
- O scanner retornou 12 entradas, mas elas representam seis IDs únicos, não 12 vulnerabilidades distintas: `PYSEC-2026-1795`, `PYSEC-2026-1796`, `PYSEC-2026-196`, `PYSEC-2026-2875`, `PYSEC-2026-2876` e `PYSEC-2026-3721`. O conjunto de correções apontado pelo scanner chega a pip 26.2.
- Esses avisos tratam de instalação/extração de pacotes; não foi demonstrada exploração HTTP da aplicação por eles. O caso CVE-2025-8869 depende do fallback sem PEP 706: o container usa Python 3.12, versão contemplada pela mitigação descrita no aviso. A aplicabilidade de cada aviso deve ser considerada, sem contar automaticamente todos como ataques exploráveis neste ambiente.
- Fontes consultadas: [CVE-2026-13346](https://github.com/advisories/GHSA-qwm4-qh6w-59xr) e [CVE-2025-8869 / PEP 706](https://github.com/advisories/GHSA-4xh5-x5gv-qwph).
- A versão instalada do pip deve ser atualizada por rebuild controlado e reavaliada; nenhuma atualização foi aplicada nesta auditoria. Imagem de sistema operacional e dependências do serviço GenAI separado não foram auditadas.

## Proteções observadas

- Filtros com padrões de SQL injection, HTML com handler de evento, caminho relativo, byte nulo, competências impossíveis e strings de 20.000 caracteres: HTTP 422 no Panorama.
- Busca UC rejeitou página negativa, page_size de um milhão, ordenação com comando SQL, inteiro de cinco mil dígitos e pesquisa excessivamente longa: HTTP 422.
- Intervalo invertido: 422; DELETE em endpoint somente leitura: 405; JSON truncado: 422.
- Tabela operacional fora da allowlist de `/ai/query`: 403. O endpoint continua placeholder; isso não prova execução SQL real somente leitura.
- Preflight CORS com origem externa não autorizada: 400, tanto isoladamente quanto no servidor real.
- Não houve vazamento de traceback, classe SQLAlchemy ou URL PostgreSQL nos corpos examinados. Esta verificação procurou esses padrões específicos; não equivale a um scanner de todos os possíveis segredos.
- 40 GETs reais no Panorama, concorrência quatro: 40 respostas 200, maior latência observada de 6,18 ms na segunda execução. A leitura de controle após a bateria também respondeu 200. Não é um teste de capacidade máxima ou prova de resistência a DoS.
- Testes React confirmaram que o filtro com `<img src=x onerror=alert(1)>` fica como texto, não cria imagem nem chama alert; HTTP 500 exibe erro recuperável, preservando filtros e botão de nova tentativa.

## Observações de implantação

O Host arbitrário foi aceito com 200 e não foram encontrados CSP, X-Content-Type-Options, X-Frame-Options, Referrer-Policy ou Permissions-Policy na resposta direta da API. São lacunas de endurecimento a avaliar no ingresso de produção, não provas isoladas de exploração. A implantação avaliada é um servidor de desenvolvimento Vite com reload, não uma publicação de produção.

Não existe limitação de taxa visível na aplicação; a bateria pequena não acionou bloqueio. Uma política de limite deve ser decidida para os endpoints expostos antes de uma implantação com dados reais. Não foi realizado teste destrutivo de saturação.

## Reproduzir e consultar evidência

O roteiro local e os resultados sanitizados estão em `work/security-audit/` (pasta ignorada pelo Git): `probe.py`, `results.json` e `pip-audit.json`. O roteiro força SQLite em memória antes de importar a aplicação; as escritas não usam o PostgreSQL.

```powershell
docker compose cp work/security-audit/probe.py backend:/tmp/grid360-security-probe.py
docker compose exec -T backend python /tmp/grid360-security-probe.py
docker compose exec -T frontend npm test -- src/features/panorama/PanoramaSecurity.test.tsx
docker compose exec -T frontend npm audit --json
```

Na coleta inicial, apenas os testes React foram acrescentados ao código versionável em `frontend/src/features/panorama/PanoramaSecurity.test.tsx`; naquele momento não houve correção de produção, commit ou push. Os testes React aprovados verificam as proteções da UI; não significam que os achados backend foram corrigidos.

## Limites e prioridade

Prioridade inicial: controlar acesso às ordens; eliminar 500s de entrada inválida; definir e impor transições e validações; atualizar ferramenta de instalação; revisar controles de implantação. A ordem entre as correções P2 pode ser ajustada pela equipe.

O ensaio não usou dados reais, contas reais, Gemini, SQL livre, escrita no PostgreSQL, varredura externa ou carga destrutiva. A inspeção visual em navegador não foi concluída porque a webview não abriu nesta passada; a verificação de XSS executou componentes React reais em JSDOM com transporte HTTP simulado. Gold, identidade em produção, PostgreSQL, permissões de infraestrutura e a cadeia completa do agente continuam fora da evidência.
