# Arquitetura, contratos e limites de camadas

## Aplicar ao projeto existente

Consulte [o serviço](../../../../docs/services/backend.md) antes de sugerir outra estrutura. Hoje os endpoints ficam em `app/api/v1/endpoints`, os DTOs em `app/schemas`, os casos de uso em `app/services`, e os modelos em `app/models`. Há repositório analítico injetável e serviços operacionais que recebem `Session` e usam ORM diretamente.

Esse arranjo é o ponto de partida. Organização por domínio pode ajudar quando surgirem responsabilidades independentes, mas não exige migrar tudo para `app/features`. Extrair um repositório vale quando isola consultas relevantes, elimina repetição ou permite trocar a fonte; uma classe que só repassa chamadas não melhora a arquitetura.

| Fronteira | Responsabilidade |
| --- | --- |
| HTTP | Validar entrada com Pydantic, resolver dependências, chamar o caso de uso, selecionar status e schema de resposta. |
| Serviço | Aplicar regras, cálculos e transições; coordenar dependências e a unidade de trabalho. |
| Persistência/fonte | Executar consultas parametrizadas, preservar granularidade e implementar acesso à fonte acordada. |
| Schema | Descrever entrada/saída, nulidade, limites e metadados; separar payload de criação, atualização e resposta. |

## Contratos e erros

Use `response_model` explícito; não serialize livremente todos os atributos do ORM. Em Pydantic 2, a conversão de atributos pode usar `ConfigDict(from_attributes=True)` e `model_validate`. Em atualizações parciais, diferencie campo omitido de `null` explícito com `model_dump(exclude_unset=True)`, respeitando o contrato.

Nos novos casos de uso, prefira erros de domínio sem imports de FastAPI/Starlette. Faça a tradução para HTTP na fronteira, com handlers compartilhados quando houver reutilização. Preserve os formatos já consumidos; mudar envelope ou status exige revisar consumidores e testes. Documente endpoints com os recursos normais do FastAPI; crie abstração de metadados apenas se a repetição justificar.

## Dados e segurança

O [catálogo analítico](../../../../docs/contracts/analytics-api.md) define versão, disponibilidade e proveniência. Fonte sintética precisa ser ativada explicitamente e identificada como demonstração; falha da Gold não deve virar sucesso com fixture silenciosa. Ausência é diferente de zero.

Valide limites de paginação, ordenação e filtros; use ordenação determinística. Autorize o acesso ao recurso no servidor. IDs, filtros ou botões ocultos no cliente não são controle de acesso. Separe credenciais e escrita operacional do acesso analítico somente leitura da IA.

Fontes: [aplicações maiores](https://fastapi.tiangolo.com/tutorial/bigger-applications/), [modelos de resposta](https://fastapi.tiangolo.com/tutorial/response-model/) e [validação por atributos no Pydantic 2](https://docs.pydantic.dev/latest/concepts/models/#arbitrary-class-instances).
