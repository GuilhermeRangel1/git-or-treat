# Frontend — Grid360

SPA React + TypeScript + Vite, com Tailwind CSS e ícones Lucide. A fundação arquitetural está preparada. A sidebar, o topo do Panorama e os textos superiores das demais páginas seguem o Figma nos temas claro/escuro, com navegação mobile; as outras seis áreas permanecem sem conteúdo de negócio. Não há dados mockados ou integração de dados.

A [arquitetura](../docs/architecture/frontend.md) define responsabilidades, dependências, tema, transporte HTTP e política de estado. A escolha está registrada na [ADR-0001](../docs/decisions/0001-arquitetura-frontend.md). O [PRD](../docs/PRD.md) governa os critérios funcionais.

## Executar

A partir de `frontend/`:

```sh
npm ci
npm run dev
```

O ambiente de CI usa Node.js 22; use uma versão compatível com os requisitos declarados pelo Vite instalado. O Docker de desenvolvimento está disponível em `Dockerfile.dev`.

Abrir a interface visual não exige API. Para futuras requisições, copie `.env.example` para `.env.local` e configure `VITE_API_URL`. Essa URL é pública; credenciais não pertencem a variáveis `VITE_*`. Em desenvolvimento há fallback para `http://localhost:8000`. Fora dele, uma requisição sem configuração falha explicitamente.

## Verificar

```sh
npm run check:boundaries
npm run format:check
npm run lint
npm test
npm run build
```

`npm run format` aplica formatação e `npm run test:watch` acompanha os testes durante o desenvolvimento. As verificações também são executadas na CI.

## Escopo visual atual

Branch `feat/visual-frontend`, renomeada de `refactor/arquitetura-frontend`. A [referência Figma](https://www.figma.com/design/oTjmpIBgbA7OOYb9ZmMG9K?node-id=15-164) orienta a sidebar de 224 px e o cabeçalho do Panorama. O rodapé demonstrativo e a linha de dados sintéticos foram retirados conforme pedido. O Panorama termina antes dos filtros. As demais páginas mostram apenas os títulos, subtítulos e rótulos superiores do protótipo; o Assistente tem apenas o painel central de abertura, sem exemplos, envio ou funcionamento de chat.

Os ícones usam Lucide; a logo é um asset local. A decoração do Panorama usa um único SVG no componente: desenha as linhas, transmite pulsos e repousa em cerca de 3,7 s; passar o mouse repete os pulsos. A preferência por movimento reduzido mantém o desenho estático. O tema é persistido quando o armazenamento permite. No mobile, o menu pode ser aberto, fechado com botão/Escape e usado para navegar. Há foco visível e atalho para o conteúdo.

Para conferir a fatia: abra `/panorama` em 1440 × 1024 e 390 × 844, alterne os dois temas, navegue nas sete áreas e exercite o menu mobile. Nenhum filtro, valor, gráfico ou chamada de API deve aparecer. A construção de KPIs, gráficos, consultas, filtros funcionais, ordens e IA depende de autorização e contratos próprios.
