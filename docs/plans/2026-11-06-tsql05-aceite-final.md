# TSQL-05 — aceite final em observação

Data: 06/11/2026. Branch: feat/genai-text-to-sql. IDs IA-01/02/08; estados oficiais dos requisitos preservados. TSQL-05 concluída no escopo de gerador em observação, sem ativação pública.

Configuração uniforme: Gemini configurado localmente, prompt text-to-sql-f1-12, temperatura 0, saída até 1.536 tokens, uma tentativa SDK por solicitação. Corpus de desenvolvimento F1 congelado, artificial, 40 IDs; não é conjunto reservado independente.

Resultado: 40/40 intenções exatas; 29 candidatos aprovados pelo revisor Backend e executados em PostgreSQL 16 artificial com correspondência às referências independentes; 11 estados esperados de esclarecimento/limitação. Zero divergência semântica ou numérica observada. Quatro solicitações falharam por indisponibilidade do provedor e foram retestadas na mesma configuração: 44 tentativas, 40 casos concluídos. As falhas iniciais não foram apagadas; o resultado não significa 100% de disponibilidade na primeira tentativa.

Evidência privada em work/: text-to-sql-f1-gemini-f1-12-full-capture.json e quatro arquivos full-retry por ID; text-to-sql-f1-f1-12-final-report.json com diferenças por caso/proveniência/tentativas; text-to-sql-f1-f1-12-final-numeric.json com resultados e referências. As capturas brutas anteriores permanecem preservadas. Os 40 resultados desta matriz usam exclusivamente f1-12 e o mesmo limite de saída.

Foi usado o avaliador real tests.text_to_sql_f1_baseline.run com o banco isolado text_to_sql_f1_test, fixture artificial e candidatos capturados, sem consultar Gold real. O avaliador confere a intenção por campo, revisão estrutural/semântica e resultados contra controles independentes. Container descartável removido após a prova.

Verificações locais anteriores da configuração final: 71 testes de gerador/contrato/captura/telemetria passaram e Ruff passou. Não houve alteração de código depois desses testes. Revisão local pelo agente; sem revisão externa.

A pessoa usuária autorizou teto acumulado US$ 2,50 antes desta matriz. Reserva conservadora final US$ 2,319857, incluindo os quatro retestes; preço pago como referência, não cobrança confirmada. Chave informada como Free Tier, faturamento não alterado.

Limites: aceite restrito aos 40 casos de desenvolvimento artificial, com retestes explícitos em indisponibilidade. Não comprova generalização, holdout, jornada pública ou execução generativa sobre Gold real. TSQL-06/07 e demais integrações preservam seus próprios critérios. Os registros anteriores de pendência da TSQL-05 são históricos, superados por este aceite uniforme.
