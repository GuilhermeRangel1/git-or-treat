# UC 360 Cadastro Restrito Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Exibir na UC 360 o nome de titular da projeção restrita Gold, sincronizado com a publicação analítica v2 e protegido por conexão de leitura dedicada.

**Architecture:** Estender a carga Gold v2 para aceitar o manifesto cadastral pareado e publicar suas linhas em `gold_cadastro` na mesma fronteira transacional. A API resolve o nome apenas para a UC selecionada por conexão dedicada e retorna estado de identificação; o Frontend mostra esse estado no cabeçalho existente da UC.

**Tech Stack:** FastAPI, SQLAlchemy, Alembic, PostgreSQL, Pydantic, React, TypeScript, TanStack Query.

**Spec:** `docs/superpowers/specs/2026-11-02-uc-cadastro-restrito-design.md`

## Global Constraints

- Não incluir o CSV nem valores pessoais no Git, logs, prompts, saída de diagnóstico ou resposta de IA.
- Schema `gold_cadastro` e usuário de runtime cadastral permanecem separados de `gold_v2` e `venergy_gold_reader`.
- A identidade cadastral precisa coincidir nos manifestos em run, linhagem, instante Gold e IDs cruzados; timestamp das linhas deve ser válido e uniforme, mas pode divergir dos manifestos.
- Somente a rota UC autenticada com `ucs:read` consulta o nome; buscas continuam sem nomes.
- Ausência na origem, conflito e indisponibilidade de pacote/conexão são estados diferentes.
- `customer_reference` permanece nulo; nome algum segue para a GenAI.

## Review Focus

- Manifesto cadastral de outro run ou `analytic_export_id`: rejeitar a carga antes de trocar publicação.
- Identificador UC repetido, chave nula, status desconhecido ou schema/CSV divergente: rejeitar e preservar o cadastro publicado.
- Pacote cadastral ausente ou conexão restrita indisponível: API informa indisponibilidade, sem interpretar como ausência de titular.
- Perfil sem `ucs:read`: recebe 403 antes de abrir a conexão cadastral.
- Busca, histórico e fluxo GenAI: não recebem nomes cadastrais.

## Mapa de arquivos

- `backend/alembic/versions/`: migração que cria schema, tabela e grants mínimos para o papel dedicado.
- `backend/app/models/gold_cadastro.py`: tabela física cadastral sem registro no catálogo de tabelas analíticas/GenAI.
- `backend/app/core/config.py` e `backend/app/repositories/`: configuração e ciclo de vida da conexão dedicada.
- `backend/app/services/gold_import_cadastro.py` e `backend/app/services/gold_import_v2.py`: validação de pacote pareado e publicação transacional.
- `backend/scripts/load_gold.py` e `backend/app/core/config.py`: entrada explícita do diretório e do DSN do leitor cadastral.
- `backend/app/repositories/gold.py`, `backend/app/services/gold_uc.py`, `backend/app/schemas/uc360.py` e `backend/app/api/v1/endpoints/ucs.py`: busca por UC selecionada e estado público.
- `frontend/src/features/uc360/contract.ts`, `UC360Detail.tsx` e `useUC360.ts`: decodificação e apresentação dos estados.
- `backend/.env.example`, `backend/scripts/`: configuração/provisionamento do papel cadastral sem senha versionada.
- `docs/contracts/gold-cadastro-v1.md`, `docs/contracts/uc360-gold-v2.md`, `docs/contracts/platform-access.md`, guias Backend/Frontend e Registro de progresso do PRD: atualização dos contratos e limites.

## Tarefas

### Tarefa 1: Persistência e pacote cadastral pareado

- Criar a tabela `gold_cadastro.cadastro_titular_uc` com chave por publicação e UC, colunas `nome_exibicao_titular`, `situacao_identificacao` e referência de processamento, constraints para chave única/estados válidos e índice de busca por UC.
- Criar papel `venergy_gold_cadastro_reader` dedicado, `NOINHERIT`, sem privilégios administrativos e com `SELECT` somente na tabela cadastral; revogar privilégios herdados incompatíveis e documentar provisionamento de senha fora do Git.
- Criar leitor de manifesto `gold-cadastro-v1` que recusa inventário/schema inesperado, CSV inválido, chave duplicada/nula, timestamp inválido ou não uniforme/status incorreto e referências divergentes; timestamp uniforme das linhas pode diferir dos manifestos do manifesto `gold-csv-v2` pareado.
- Estender a carga v2 para receber `--cadastro-directory` e inserir cadastro dentro da transação/lock de publicação existente; falha cadastral mantém publicada a versão anterior.
- Não imprimir linhas, nomes ou valores pessoais; mensagens públicas contêm somente tipo de falha e tentativa.

### Tarefa 2: Consulta API por sessão autorizada

- Configurar `GOLD_CADASTRO_DATABASE_URL` como segredo opcional; criar engine de runtime somente leitura separada da engine analítica.
- Consultar uma linha pelo `uc_id` selecionado e pela referência cadastral vinculada à publicação v2 atual; não incluir cadastro no repositório/catálogo GenAI.
- Estender `UCProfile` com estado `available | absent | conflict | unavailable`; manter nome nulo para os três estados sem nome e `customer_reference` nulo.
- Na rota de overview existente, executar a consulta somente após autorização `ucs:read`. Busca e históricos seguem sem campos cadastrais.
- Atualizar exemplos de ambiente e contrato para ausência de configuração/pacote, timeout, publicação incompatível e acesso negado.

### Tarefa 3: Apresentação na UC 360

- Atualizar o decoder TypeScript para validar o estado novo e manter compatibilidade do envelope usado pela fonte sintética.
- Manter o nome no cabeçalho da UC selecionada; apresentar rótulos curtos e distintos para ausência na origem, conflito na origem e integração indisponível.
- Não colocar nome em busca, resultados, URL, query key, mensagens de erro ou contexto de assistente.

### Tarefa 4: Operação local e evidência

- Aplicar migrações e provisionar papel cadastral somente no banco local selecionado; configurar o DSN privado do papel.
- Importar o par Gold indicado pelo spec e conferir que o `run_id`, export IDs e publicação coincidem sem imprimir dados pessoais.
- Reiniciar API, confirmar health check e conferir a tela/rota com perfil autorizado, perfil negado e estados cadastrais distintos; registrar comandos, resultados e limites sem capturas ou linhas identificáveis.
- Atualizar contratos/serviços e o Registro de progresso. Não marcar WEB-03 ou WEB-10 como concluídos apenas por esta fatia.
