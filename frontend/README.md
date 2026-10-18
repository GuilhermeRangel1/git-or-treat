# Frontend — Grid360

SPA React + TypeScript + Vite, com Tailwind CSS e ícones Lucide. A fundação arquitetural está preparada; as sete páginas permanecem vazias e sem integração de dados.

A [arquitetura](../docs/architecture/frontend.md) define responsabilidades, dependências, tema, transporte HTTP e política de estado. A escolha está registrada na [ADR-0001](../docs/decisions/0001-arquitetura-frontend.md). O [PRD](../docs/PRD.md) governa os critérios funcionais.

## Executar

A partir de `frontend/`:

```sh
npm ci
npm run dev
```

O ambiente de CI usa Node.js 22; use uma versão compatível com os requisitos declarados pelo Vite instalado. O Docker de desenvolvimento está disponível em `Dockerfile.dev`.

Abrir as páginas vazias não exige API. Para futuras requisições, copie `.env.example` para `.env.local` e configure `VITE_API_URL`. Essa URL é pública; credenciais não pertencem a variáveis `VITE_*`. Em desenvolvimento há fallback para `http://localhost:8000`. Fora dele, uma requisição sem configuração falha explicitamente.

## Verificar

```sh
npm run check:boundaries
npm run format:check
npm run lint
npm test
npm run build
```

`npm run format` aplica formatação e `npm run test:watch` acompanha os testes durante o desenvolvimento. As verificações também são executadas na CI.

## Próxima etapa

Após encerrar a arquitetura, os elementos puramente visuais poderão ser alinhados ao Figma em uma etapa separada. A construção de KPIs, gráficos, consultas, filtros funcionais, ordens e IA depende de autorização e contratos próprios.
