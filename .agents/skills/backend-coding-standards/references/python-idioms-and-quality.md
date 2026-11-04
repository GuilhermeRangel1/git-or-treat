# Python, tipos e legibilidade

## Versão e contratos

Confira a versão alvo no Docker/CI e as ferramentas de desenvolvimento antes de usar sintaxe nova. O alvo atual do backend é Python 3.12; a instalação local pode estar em outra versão. Não introduza sintaxe do Python 3.14 por inferência a partir da versão do seu terminal.

Use `list[T]`, uniões `T | None`, retorno explícito em funções públicas e nomes do domínio. Evite `Any` em contratos estáveis: Pydantic descreve JSON externo; `TypedDict`, dataclasses ou protocolos descrevem estruturas internas quando pertinentes. Converta dados de bibliotecas na fronteira; `cast` não valida dados em execução.

## Expressar intenção

- Use nomes diferentes quando muda o significado do valor. Reatribuir um acumulador ou um construtor de consulta com a mesma semântica não é uma violação por si só.
- Divida cálculos densos em etapas que revelem unidade, denominador e arredondamento. A fórmula vem da Gold/dicionário aprovado, não de uma simplificação conveniente no serviço.
- Trate precondições com retornos antecipados ou erros claros. Use `match`, comprehensions e `:=` quando reduzirem esforço de leitura; não como requisito estilístico.
- Documente invariantes, unidade, efeitos e exceções relevantes. Uma docstring que apenas repete o nome da função acrescenta pouco.
- Evite argumentos padrão mutáveis e estado compartilhado alterável entre requisições. `frozen=True` ajuda em DTOs internos, mas não congela profundamente listas ou dicionários contidos.

## Dinheiro, datas e ausências

Defina precisão e serialização monetária no contrato. Prefira representação decimal exata ou unidades inteiras quando a regra exigir exatidão; converter um `float` já arredondado para `Decimal` não recupera precisão perdida. Não altere tipos de colunas ou migrações como ajuste de estilo.

Distinga competência de faturamento, data de pagamento e timestamp de atualização. Para instantes, explicite fuso e normalização; competências seguem a definição do contrato. Trate `None` antes de cálculos e mantenha zero legítimo. Percentual com denominador zero precisa de resultado indisponível e motivo, não infinito ou zero inventado.

## Exceções e diagnóstico

Capture exceções específicas na tradução para respostas de domínio/HTTP. Uma captura ampla é apropriada para rollback seguido de `raise`, não para silenciar falha e retornar sucesso. Use logs com contexto operacional e sem payloads pessoais, credenciais ou SQL sensível. Preserve a causa da exceção para diagnóstico interno quando isso for seguro.

Fontes: [tipagem Python 3.12](https://docs.python.org/3.12/library/typing.html), [Decimal](https://docs.python.org/3.12/library/decimal.html) e [Pydantic 2](https://docs.pydantic.dev/latest/concepts/models/).
