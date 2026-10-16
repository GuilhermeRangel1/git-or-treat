# Serviço: agente de inteligência artificial

**Escopo:** IA-01 a IA-08 do [PRD](../PRD.md). **Estado:** adaptador Gemini opcional, interpretação determinística inicial e ferramentas analíticas sintéticas estão preparadas; ainda não estão integrados ao endpoint, à Gold, ao backend do portal ou ao frontend. **Stack do case:** Python integrado ao FastAPI e banco local Gold; framework de agente à escolha. O código configura `gemini-3.5-flash-lite` como padrão do adaptador e permite escolher outro ID, como `gemini-3.6-flash`; a escolha definitiva do provedor continua aberta pela equipe.

## Duas formas de IA obrigatórias

1. **Agente conversacional Text-to-SQL no portal:** interpreta português cotidiano, consulta Gold e devolve resposta clara, numérica e fundamentada.
2. **Insight embutido em uma tela:** interpreta o dado que o usuário vê e sugere o que investigar, mantendo vínculo explícito com filtros e período da tela.

O mesmo dicionário Gold deve reger a conversa e o insight. A interface precisa mostrar qual parte é dado observado e qual parte é interpretação gerada. Uma sugestão de investigação não deve ser apresentada como causa comprovada.

## Contrato de uma resposta confiável

Cada resposta quantitativa deve conter: conclusão direta; métrica e unidade; competência/janela; filtros e geografia/classe; valor e comparação quando solicitados; fonte Gold e trilha auditável da consulta ou parâmetros; ressalvas relevantes. Se não há coluna, histórico ou granularidade para responder, dizer isso. Distinguir inferência de dado observado. Não executar ferramentas com efeito de escrita.

## Preparação sintética implementada

- O interpretador inicial é baseado em regras explícitas. Reconhece termos configurados, preserva frases de métrica/período/geografia/classe e pede esclarecimento para “conta de luz” sem detalhe, períodos ausentes ou bases de comparação ambíguas, mais de um domínio e locais desconhecidos.
- Uma correção explícita na própria pergunta pode substituir um filtro anterior (“em Olinda, não, em Jaboatão”). Várias localidades sem marca de correção interrompem o fluxo para esclarecimento.
- O planner de preparação só consulta a ferramenta sintética depois que a interpretação está pronta. Ele ainda não é usado por `POST /api/v1/questions`.
- A busca de cenários entrega somente fixtures marcadas `is_demo`. Se classe, geografia, período ou filtros pedidos não estiverem representados, retorna ausência de evidência.
- A ferramenta de comparação recebe dois valores artificiais tipados; só compara mesma unidade e granularidade, e não calcula percentual com base zero. A operação aritmética é demonstrativa, não fórmula oficial de receita, consumo, DEC/FEC ou outro indicador da V-Energy.
- Esses componentes não consultam Gold, não provam o comportamento do Gemini e não concluem requisitos IA do PRD. Follow-up entre turnos, resposta gerada e fluxo HTTP integrado permanecem pendentes.

## Fluxo controlado proposto

1. Identificar intenção, entidades, período, filtros e ambiguidades. Reconhecer sinônimos do setor.
2. Validar se há informação no dicionário e permissão para consultar a métrica.
3. Produzir consulta limitada a tabelas/colunas de leitura, com limite de linhas, timeout e validação independente da saída do modelo.
4. Executar com usuário de banco somente leitura e capturar consulta/parâmetros, versão dos dados e resultado agregado.
5. Formular resposta a partir do resultado obtido, com checagem de números e política de “não sei”.
6. No insight de tela, receber contexto estruturado da tela; não confiar apenas em texto livre que possa contradizer os filtros reais.

## Política de respostas e auditoria

| Situação | Resposta esperada |
| --- | --- |
| Pergunta com métrica, período e recorte definidos | Consultar fonte permitida, conferir cálculo e responder com valor, unidade, filtros, período e origem. |
| Termo cotidiano com mapeamento seguro | Explicitar a interpretação, por exemplo “conta de luz” como fatura, antes do número quando houver mais de uma leitura plausível. |
| Ambiguidade que muda o número | Perguntar qual definição/janela usar; não escolher silenciosamente entre faturado e pago ou entre competência e pagamento. |
| Coluna, período ou grão insuficiente | Dizer exatamente qual dado falta e qual parte, se alguma, pode ser respondida com segurança. |
| Pedido de escrever/apagar dados ou acessar fora do escopo | Recusar a ação e manter consulta somente leitura; não transformar o pedido em SQL executável. |
| Consulta válida com zero linhas ou denominador zero | Informar ausência de base, sem fabricar zero ou percentual. |

Registrar internamente pergunta, interpretação de entidades/métricas, consulta/parâmetros aprovados, lote Gold, quantidade de linhas e resultado agregado, resposta e eventuais avisos. A trilha deve permitir que um analista reproduza a resposta sem expor credenciais ou dados pessoais no navegador. Definir retenção e acesso a essa trilha antes da implementação.

## Riscos que precisam de testes

- SQL de escrita, múltiplas instruções, acesso a tabelas internas, consulta sem limite, dados pessoais e prompt injection em textos do dataset.
- Sinônimos e ambiguidades: “conta de luz”, “falta de luz”, “último ano”, “receita” e “queda de consumo” podem exigir esclarecimento.
- Multiplicação por joins, percentuais com base zero/pequena, séries faltantes e diferenças entre competência e pagamento.
- Follow-up que herda filtro errado ou contexto de outra conversa.
- Resposta fluente sem sustentação: comparar números diretamente com Gold e exigir citação interna verificável.

## Conjunto de perguntas de aceitação

| Tema | Exemplo ou intenção do case | O que conferir |
| --- | --- | --- |
| GD e consumo | Quantas UCs com solar em Olinda tiveram queda de consumo superior a 30%? | Base comparável, janela, definição de queda e campo real que identifica solar. |
| Receita residencial | Qual bairro mais perdeu volume residencial no último ano? | Métrica de volume, janela, contribuição absoluta versus percentual e hierarquia geográfica. |
| Receita comercial | Quanto cresceu a receita comercial em Jaboatão? | Conceito de receita, comparação temporal e valor absoluto/percentual solicitados. |
| Atendimento | Pergunta sobre conta alta de uma UC. | Privacidade, disponibilidade de histórico e distinção de consumo, tarifa/bandeira e pagamento. |
| Continuidade | Pergunta sobre “falta de luz” em um bairro/alimentador. | Mapeamento para interrupções, cobertura e limite do DEC/FEC simplificado. |
| Impossível/ambígua | Pergunta por dado ausente, termo sem definição ou causa não observável. | Pedido de esclarecimento ou “não sei” justificado. |
| Segurança | Instrução para alterar banco ou obedecer texto de um chamado. | Nenhuma escrita ou ampliação de privilégio, mesmo se o modelo sugerir. |

Esses exemplos não são respostas esperadas; os números só podem ser preenchidos depois da Gold validada. IA-08 automatiza regressão desse conjunto, mas os IDs obrigatórios precisam de conferência numérica independente mesmo sem o diferencial.

## Avaliação

Preparar casos representativos para consumo, faturamento, rede, atendimento, geografia, classe, GD e perguntas impossíveis. Conferir correção numérica e recusa adequada. IA-08 é diferencial de automação; mesmo sem ele, evidência manual reproduzível é necessária para IA-01 a IA-06.
