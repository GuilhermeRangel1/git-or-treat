# Tailwind 4, temas e acessibilidade

## Tokens e identidade existentes

Use `frontend/src/styles/tokens.css` e seu `@theme inline` como ponte entre variáveis e utilitários. Exemplos disponíveis: `bg-canvas`, `bg-surface`, `text-content`, `text-muted`, `border-control`, `text-brand`, `text-success` e `text-danger`. Preserve `data-theme` e o provedor atual nos modos claro/escuro.

A direção visual aprovada usa cacau, goiaba e pistache; Manrope, DM Sans e IBM Plex Mono. Consulte o frame e os tokens para os valores reais. Não substitua cores por aliases de outro significado para satisfazer lint. Quando faltar um papel semântico necessário, defina-o conscientemente nos dois temas e conecte-o ao Tailwind.

O projeto usa Tailwind 4 com Vite; não copie instalação/configuração de Tailwind 3 por hábito. Mantenha CSS de efeitos específicos junto ao componente quando isso tornar o efeito legível. Valores arbitrários são possíveis para geometria específica do design; repetição de um valor de identidade pode indicar token ausente.

## Classes completas

O Tailwind precisa encontrar classes completas no código. Troque `bg-${color}-600` por um mapa fechado de variantes. Para valores contínuos vindos de dados, como largura de barra, valide limites/unidade e use estilo ou variável CSS, sem interpolar um nome de classe incompleto.

Exemplo apresentacional com os tokens atuais; os estados abaixo descrevem disponibilidade visual, não o ciclo de ordens:

```tsx
const appearance = {
  available: "border-success text-success",
  unavailable: "border-control text-muted",
  error: "border-danger text-danger",
} as const;

type AvailabilityLabelProps = {
  state: keyof typeof appearance;
  children: string;
};

export function AvailabilityLabel({ state, children }: AvailabilityLabelProps) {
  return (
    <span className={`rounded-md border px-2 py-1 ${appearance[state]}`}>
      {children}
    </span>
  );
}
```

O texto fornece significado além da cor. Usar tokens não garante contraste automaticamente: confira o par de cores, o tamanho e o fundo no contexto real.

## Semântica e interação

HTML nativo é válido: links navegam, botões executam ações e formulários submetem. Reutilize os componentes locais quando cobrirem a necessidade; não imponha wrappers para todos os elementos. Botões que não submetem usam `type="button"`. Controles só com ícone precisam de nome acessível; ícones decorativos ficam ocultos das tecnologias assistivas.

Garanta foco visível e sequência de tabulação previsível. Diálogos precisam de título, foco inicial adequado, contenção do foco enquanto modais, Escape e retorno ao acionador; o menu existente usa `dialog` nativo. Mensagens dinâmicas importantes podem usar anúncio apropriado sem repetir toda a tela a cada atualização.

Tabelas usam cabeçalhos/associações e ordenação identificável; gráficos têm resumo ou alternativa textual. Cor e hover não podem ser a única forma de transmitir estado ou revelar uma ação. Para condições JSX numéricas, use comparações booleanas como `items.length > 0` para não renderizar `0` acidentalmente.

## Responsividade e movimento

Preserve leitura, acesso aos controles e rolagem com tela estreita, texto ampliado e zoom. Desenhos desktop/mobile não dispensam testar larguras intermediárias e conteúdo extenso.

Prefira CSS para transições simples. Preserve a sequência finita e o replay deliberado do ornamento do Panorama; não o transforme em loop automático por padrão. Respeite `prefers-reduced-motion`, sem movimento essencial para compreender ou operar a tela. Não presuma que Motion está instalado.

Fontes: [tokens Tailwind 4](https://tailwindcss.com/docs/theme), [detecção de classes](https://tailwindcss.com/docs/detecting-classes-in-source-files), [estados e movimento reduzido](https://tailwindcss.com/docs/hover-focus-and-other-states#prefers-reduced-motion) e [WCAG 2.2](https://www.w3.org/TR/WCAG22/).
