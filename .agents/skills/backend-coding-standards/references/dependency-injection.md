# Injeção de dependências, concorrência e ciclo de vida

## Composição

Use `Annotated[T, Depends(factory)]` para dependências em parâmetros. O serviço pode receber colaboradores por parâmetros ou construtor; evite resolver dependências HTTP dentro da regra de negócio. Reutilize `get_db` e a composição existentes em vez de criar uma segunda fábrica de sessões.

Exemplo compatível com a sessão síncrona atual, a adaptar no módulo de rotas pertinente:

```python
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.inspections import OrderCreateRequest
from app.services import inspections

router = APIRouter()
Database = Annotated[Session, Depends(get_db)]


@router.post("/orders")
def create_order(payload: OrderCreateRequest, db: Database):
    return inspections.create_order(db, payload)
```

O exemplo demonstra a composição; a rota de produto deve preservar seu `response_model`, status, prefixo e controles de acesso existentes.

## Dependências com efeitos de validação

Em `dependencies=[...]`, passe objetos `Depends`, por exemplo `dependencies=[Depends(verify_access)]`. Aliases `Annotated` pertencem às anotações dos parâmetros.

Para uma classe com `__call__`, `Depends(instance)` executa a instância chamável. `Depends(factory)` executa a fábrica; retornar uma instância não chama automaticamente seu `__call__`. Uma proteção de acesso ou limite de requisições precisa ser realmente executada e testada. Contadores em memória são locais ao processo, não um limite distribuído.

## Sync e async

Com SQLAlchemy `Session` e I/O bloqueante, use rota `def`, executada pelo FastAPI no pool de threads. `async def` faz sentido com bibliotecas aguardáveis ao longo do caminho. A chamada comum de uma função `def` dentro de `async def` não é deslocada automaticamente para esse pool. Não migre para `AsyncSession` apenas para uniformizar assinaturas.

Uma sessão pertence a uma unidade de trabalho; não a compartilhe entre requisições, tarefas concorrentes ou workers. Trabalho em segundo plano cria e fecha seus próprios recursos. Prefira `lifespan` ao introduzir recursos da aplicação que precisem iniciar e encerrar juntos, como clientes HTTP reutilizáveis; diferencie esses recursos das sessões por requisição. Feche recursos em `finally` ou context managers.

Fontes: [concorrência no FastAPI](https://fastapi.tiangolo.com/async/), [instâncias chamáveis](https://fastapi.tiangolo.com/advanced/advanced-dependencies/), [dependências em decorators](https://fastapi.tiangolo.com/tutorial/dependencies/dependencies-in-path-operation-decorators/) e [sessões SQLAlchemy 2](https://docs.sqlalchemy.org/en/20/orm/session_basics.html#is-the-session-thread-safe-is-asyncsession-safe-to-share-in-concurrent-tasks).
