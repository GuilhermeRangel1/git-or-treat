# Busca da UC por município e classe

**Estado:** aprovado em 2026-11-02
**Requisito relacionado:** WEB-03

## Objetivo

Permitir localizar unidades consumidoras sem conhecer o número da UC, usando município, classe de consumo ou ambos. O texto do número continua disponível e pode ser combinado com esses filtros.

## Desenho

- A busca permanece em `/uc-360`. O formulário terá número da UC, município e classe, com opções obtidas da rota existente `/api/v1/analytics/options` e estado vazio equivalente a “Todos”.
- O envio aceita qualquer combinação não vazia dos três critérios. Sem texto e sem filtros, não consulta a API e orienta a pessoa a escolher pelo menos um critério.
- `GET /api/v1/ucs` aceitará `municipio` e `classe` opcionais além de `q`; todos os critérios serão aplicados no servidor antes da ordenação e paginação. A Gold v2 usará igualdade nos campos cadastrais de `visao_360_uc`; a fonte sintética seguirá o mesmo contrato.
- A URL guardará `q`, `municipio`, `classe` e `search_page`. Alterar critérios reinicia a página. Resultados paginados mostram o total para os filtros aplicados.
- Ao abrir uma UC, os critérios e o período atual seguem para o detalhe. “Voltar à busca” os restaura.
- Opções e resultados pertencem à publicação Gold ativa. A interface não combina opções de uma publicação com resultados de outra.

## Fora do escopo

Busca por bairro, novos campos cadastrais, ordenação adicional e alterações no conteúdo do detalhe da UC.

## Verificação proposta

- Backend: filtros combinados e isolados, sem texto; paginação após filtragem; validação de município/classe e cobertura sintética/Gold v2 conforme os testes existentes.
- Frontend: formulário aceita filtros sem texto, combinação com texto, estados vazio/carregando/erro, mudança de página e preservação dos critérios ao abrir/voltar do detalhe.
- Gates: testes direcionados, lint, formatação, build e diff-check. O estado oficial de WEB-03 não muda.
