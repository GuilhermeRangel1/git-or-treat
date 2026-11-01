# GENAI-09 — primeira pergunta real: evidência local

## Resultado em 01/11/2026

Integração executável real pela API: login individual → POST /api/v1/ai/questions → planejamento HTTP GenAI → prontidão observada no PostgreSQL → executor restrito → síntese Gemini → resposta answered com referência durável. A jornada visual do portal ainda não foi executada nesta prova.

Base de código: 8274009 com alterações locais na branch feat/genai-primeira-pergunta-real. Backend usa app.main:app; GenAI usa app.gold_runtime:create_gold_app, perfil Gold v2 e fonte gold.local. PostgreSQL 16: container genai08-gold-v2-postgres e volume genai08-gold-v2-data, previamente carregado pelo importador oficial. C01/C02/C04 passaram e foram aprovados pela pessoa usuária apenas para esta entrega local. Nenhuma aprovação foi inferida para os demais controles.

## Reprodução privada

A amostra privada fica em work/genai09-local, ignorado pelo Git. result.json contém a pergunta, controle independente e envelope público, sem senha ou cookie. model-result.json contém a saída do modelo e evidência minimizada para diagnóstico autorizado; não publicar esses arquivos. O roteiro smoke.py cria identidade temporária orders:read, faz login HTTP e remove a conta em finally. Credenciais ficam no ambiente privado.

Pergunta: receita de um município em mês explícito coberto pelo lote. O recorte é escolhido deterministicamente pela competência mais recente e município ordenado com receita não nula. Controle independente, separado do compilador de planos:

```sql
SELECT competencia, municipio, SUM(receita_total_reais) AS total
FROM gold_v2.diagnostico_receita
WHERE municipio IS NOT NULL
GROUP BY competencia, municipio
HAVING SUM(receita_total_reais) IS NOT NULL
ORDER BY competencia DESC, municipio
LIMIT 1;
```

Comando privado observado: docker exec -e PYTHONPATH=/repo/backend -w /repo/backend genai09-local-backend-direct python /repo/work/genai09-local/smoke.py. Resultado: login 200, pergunta 200, answered, sem erro e com audit_reference. Conta removida ao final. O total Decimal do controle confere com a observação; a representação numérica e unidade dessa observação aparecem na resposta. Período, filtros e referência de origem conferem entre evidência e contrato público. O identificador do lote permanece na trilha interna autorizada; não é publicado no documento.

## Correções e verificações

- Criado entrypoint Gold implantável que reutiliza create_app; auditoria obrigatória e execução exclusivamente no Backend.
- Prompt genai-grounding-v3 esclarece que filtro de município não vira dimensão da linha agregada. A v2 produziu claims com dimensão ausente na observação e foi corretamente recusada; a v3 respondeu sem relaxar o guard.
- Backend aceita eventos de prompts v1/v2/v3; referência opaca fica visível no Assistente.
- GenAI: 99 testes de runtime/claims/adaptador e 25 de EvidenceGuard passaram. Backend: 3 de auditoria passaram, com aviso preexistente Starlette/httpx. Interface: 12 testes, tipos/build e fronteiras passaram; lint sem erros, com aviso preexistente AuthProvider.
- Prontidão pela rede host levou 32,94 s e uma chamada pública encerrou com 504. A ligação direta entre containers permitiu completar o fluxo dentro do prazo existente. Não foi aumentado o limite de 35 s.

## Limites

Ainda faltam navegação real do portal, repetição desta fatia com vazio/ambiguidade/acesso negado/indisponibilidade e falhas de modelo/auditoria, replay administrativo da referência desta resposta e revisão integrada dos consumidores. A evidência HTTP não conclui IA-01 nem GENAI-09 integralmente. Dataset, payloads privados e chaves não entram no Git. Instrumentação diagnóstica local não integra o código de produção.
