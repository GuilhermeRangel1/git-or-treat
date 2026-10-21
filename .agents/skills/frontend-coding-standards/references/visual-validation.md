# Figma, testes e validação da entrega

## Escolher a referência visual

Use [o registro do protótipo](../../../../docs/design/grid360-prototype.md), [a arquitetura implementada](../../../../docs/architecture/frontend.md) e o [arquivo Grid 360](https://www.figma.com/design/oTjmpIBgbA7OOYb9ZmMG9K). Identifique frame, tema e viewport da fatia solicitada; os registros têm datas e podem descrever etapas anteriores.

Para implementar um frame, use a skill `figma:figma-design-to-code` antes de obter contexto de design; para trabalhar no protótipo, consulte `git-or-treat-figma` e as skills Figma aplicáveis. Se o MCP ou frame não estiver acessível, use a evidência disponível, declare o limite e não afirme uma conferência atual do arquivo.

Compare hierarquia, tipografia, cores semânticas, espaçamentos, dimensões, quebras e estados nos dois temas. Reutilize layout/componentes existentes e preserve as decisões posteriores aprovadas. Imagens do enunciado não entram no repositório. Uma captura do design não deve substituir texto e controles reais.

O Figma especifica intenção visual e interações demonstrativas. Fórmulas, transições operacionais, autorização e validade dos dados vêm do PRD/contratos/backend. Números sintéticos desenhados não são resultados do case; lacunas do design não autorizam inventar comportamento de negócio.

## Verificações por tipo de mudança

| Mudança | O que observar |
| --- | --- |
| Layout/tema | Navegação mantém estrutura e estado pertinente; temas claro/escuro; viewport estreito/intermediário/desktop; zoom sem perda de ações. |
| Consulta/contrato | API exercitada, decoder, filtros na chave, cancelamento, ausência, zero, parcial e erro; fonte sintética identificada. |
| Formulário/ordem | Teclado, rótulos, erro, submissão repetida, falha de servidor e confirmação persistida quando a integração estiver no escopo. |
| Diálogo/menu | Abrir, focar, navegar, fechar por Escape e retornar foco. |
| Movimento | Início, repouso, replay e preferência por movimento reduzido. |
| Insight | Período/filtros correspondem à tela e resposta antiga é identificada após mudar o recorte. |

Teste o comportamento que a pessoa vê com Vitest/Testing Library; prefira consultas por papel e nome acessível. Verifique transporte/contrato separadamente quando isso localizar falhas melhor. Evite snapshots extensos e testes que apenas repetem constantes da implementação.

Para mudança visual ou interação, inspecione no navegador a fatia afetada; jsdom não comprova geometria, contraste ou reflow. Não crie testes de produto para uma alteração apenas documental de skill.

## Gates existentes

Na pasta `frontend`, confira os scripts e execute os aplicáveis/obrigatórios:

```bash
npm run check:boundaries
npm run format:check
npm run lint
npm test
npm run build
```

Versões resolvidas estão no lockfile; os comandos presentes no `package.json`/CI são a referência. Build cobre tipos e empacotamento, não acessibilidade nem reconciliação com Gold. Fronteiras não podem ser contornadas desativando o verificador.

Relate arquivos, comportamento, verificações executadas e limitações. Registre no PRD evidência do requisito entregue conforme o workflow local; integração sintética, preparação visual e instalação de skills não concluem requisitos funcionais. Guarde exploração/capturas locais em `work/`, sem segredos ou dados pessoais.

Fontes: [Testing Library](https://testing-library.com/docs/react-testing-library/intro/) e [princípios de consultas acessíveis](https://testing-library.com/docs/queries/about/#priority).
