# Reuso e conformidade do núcleo GenAI

Este documento descreve o recorte técnico do checkpoint 4.13. Os perfis Grid 360 e clima, suas fontes e todas as medidas desta prova são artificiais. A prova não certifica um esquema Gold nem conclui IA-01, IA-03 ou IA-06.

## Como conectar outro domínio

1. Crie um `DomainProfile` fora de `app/agent/`. Defina IDs lógicos únicos para domínio, métricas e dimensões; aliases, períodos, unidades, operadores, sensibilidade, campos de evidência classificados e textos de limitação. O perfil de clima em `ai-agent/tests/weather_fixture.py` é o exemplo mínimo executável; `app/profiles/grid360_demo.py` contém o exemplo do Grid 360.
2. Implemente `EvidenceSource.retrieve(plan: LogicalReadPlan) -> EvidenceLookupResult` em um adaptador externo ao núcleo. O método recebe apenas um plano aprovado e deve devolver proveniência compatível: fonte, fingerprint do plano, versão do catálogo, métrica, unidade, janela, filtros e dimensões. Retorne `no_evidence` quando não houver linhas, `needs_clarification` quando o recorte não puder ser aplicado, e exceções tipadas para indisponibilidade e acesso negado. A fonte deve respeitar limite, prazo e cancelamento; o núcleo também impõe seu próprio orçamento.
3. Monte a aplicação com `create_app(domain_profile=..., source_id=..., evidence_source=..., model_adapter=...)` ou chame `compose_core` diretamente. A política e o contexto de acesso devem apontar para o mesmo perfil e fonte. Uma instância do núcleo usa um único perfil. Para duas plataformas, crie duas composições independentes.
4. Acrescente uma `SourceSubject` em `ai-agent/tests/test_reusable_core.py` com fábrica da fonte, perguntas e resultados artificiais conhecidos. A matriz executa sucesso, ausência, filtro sem suporte, negação, resposta inválida, campo sensível, limite, timeout/cancelamento e proveniência. O teste separado de filtro válido sem linhas pode ser pulado se essa capacidade não existir; os controles de segurança continuam obrigatórios.
5. Execute, dentro de `ai-agent/`, `python -m pytest -q tests/test_reusable_core.py tests/test_import_boundaries.py` e depois a suíte completa. A API local usa uma identidade fictícia apenas para demonstração; integração real deve derivar identidade e escopos de autenticação confiável.

Nenhum dos passos exige editar `app/agent/`, `app/generation/`, `app/ports/` ou `app/schemas/` para acrescentar o perfil de clima. O teste de imports verifica essa fronteira, incluindo imports dinâmicos literais.

## Matriz do recorte sintético

| Controle | Grid 360 artificial | Clima artificial |
| --- | --- | --- |
| Métricas e unidades | Consumo e demais métricas demonstrativas; `unidades fictícias` no caso exercitado | Chuva em `mm fictícios` e temperatura em `graus fictícios` |
| Vocabulário e filtro | “consumo”, município Olinda; fonte sem linha para recorte filtrado | “chuva”/“temperatura”, estações Arua/Bela; fonte sem linha para Bela |
| Fonte | `SyntheticScenarioTool` | `WeatherEvidenceSource` independente |
| Caminho positivo | Caso de uso direto e `POST /api/v1/questions`; insight sintético autorizado | Mesmo caso de uso direto e mesmo endpoint; insight sintético autorizado |
| Caminhos negativos | Sem linhas, filtro sem suporte declarado pela fonte, acesso negado, retorno inválido, excesso de linhas, prazo/cancelamento e proveniência divergente | Mesma matriz; filtro válido sem linhas usa a estação Bela |
| Proteção e isolamento | Campos pessoais inventados descartados, troca de escopo negada, cache e eventos isolados, fallback após indisponibilidade | Mesmas verificações em composição simultânea |

## Limites demonstrados

- O interpretador atual é lexical e depende de aliases e períodos previstos no perfil. Um perfil novo não ensina automaticamente fórmulas, sinônimos, joins ou perguntas livres.
- O plano atual representa leitura lógica com filtros definidos no catálogo. O adaptador precisa traduzir e impor a consulta permitida na sua fonte; esta prova não executa SQL nem verifica credencial de banco somente leitura.
- O `EvidenceGuard` aceita medida numérica classificada e reduz a evidência a observações aprovadas. Outros formatos de resultado exigem desenho e revisão de contrato.
- A referência da fonte é conferida contra o plano antes de ser transformada em `source_id` e hash estável. O identificador original não chega ao modelo ou à API; o adaptador deve manter o vínculo interno para reprodução da consulta. O hash não substitui uma referência de lote Gold aprovada.
- No insight, a referência enviada pelo cliente também vira um identificador opaco antes de chegar ao modelo ou à resposta. O cache só guarda resposta fundamentada por IDs de observação presentes na evidência fornecida.
- O insight da tela exige contexto de acesso com perfil, fonte e escopo de leitura compatíveis. As observações ainda são fornecidas pelo cliente; métrica e filtros livres da tela não provam autorização de uma consulta Gold.
- Fallback injetado, inclusive sob cache, é rejeitado na composição se o número máximo de tentativas exceder `max_model_calls`. O contador de eventos representa a chamada lógica ao wrapper, não cada tentativa do provedor.
- A fonte de clima existe somente em `tests/`; não é uma integração de produção. Os testes negativos com mutações verificam a reação do núcleo a falhas de fonte, sem certificar um cliente Gold externo.
- O cache em memória pode ser compartilhado na prova porque sua chave inclui escopo autorizado, plano e evidência. Persistência, invalidade por lote Gold, autenticação e isolamento entre processos precisam de integração e verificação próprias.
- Os eventos têm estrutura segura e correlação; o destino padrão não persiste auditoria. A confirmação de escrita, retenção e controle de acesso a uma trilha real continuam pendentes.
- A fonte do Grid 360 e a fonte de clima usam apenas dados inventados. Nenhuma medida aqui valida resultado de negócio, qualidade de dados ou decisão operacional.

O contrato externo com Backend/Dados (4.1) e a Gold real continuam pendentes. A Etapa 4 como um todo permanece aberta até esse acordo.
