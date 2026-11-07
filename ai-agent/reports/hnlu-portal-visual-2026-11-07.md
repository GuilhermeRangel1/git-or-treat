# Validação visual mínima da NLU — 2026-11-07

## Escopo executado

- Stack local Docker: frontend, Backend, agente e banco saudáveis.
- Login no portal com conta comercial temporária provisionada no ambiente local.
- Jornada `Panorama → Perguntar à IA → Assistente` exercitada no navegador.
- Pergunta sintética de faturamento total em junho de 2026 enviada pelo Assistente.
- Resposta exibida como fundamentada, com indicador, unidade, definição, competência, fonte e evidência consultável.
- A sessão foi invalidada ao remover as contas temporárias. Cinco contas criadas pelo bootstrap local e os dois arquivos de credenciais foram removidos; nenhum número observado da Gold foi copiado para este relatório.

## Resultado e limite

A jornada visual autenticada mínima passou para uma pergunta de faturamento. Isso complementa a prova HTTP Gold v2 registrada em `hnlu-gold-e2e-2026-11-07.md`, mas não prova estabilidade do Gemini nem fecha HNLU-08. Permanecem sem validação visual os avisos, exportação, fundamentos detalhados, insights, sessões independentes, concorrência, indisponibilidade, replay/cache entre modos e rollback.

## Reprodução

1. Iniciar a stack pelo fluxo documentado em `docs/agents/tooling.md`.
2. Provisionar uma conta local temporária pelo `backend/scripts/bootstrap_local_auth.py`, usando credencial descartável que não seja salva no repositório.
3. Entrar no portal, abrir o Assistente e perguntar `Quanto foi o faturamento total em junho de 2026?`.
4. Confirmar resposta fundamentada e metadados do recorte; remover a conta e os arquivos privados de credencial ao terminar.
