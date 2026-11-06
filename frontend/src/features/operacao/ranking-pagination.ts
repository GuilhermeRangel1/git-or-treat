export type PageItem = number | "ellipsis";

/**
 * Páginas visíveis da paginação numerada: sempre a primeira, a última e a
 * vizinhança da página atual. Uma lacuna de uma única página mostra o número;
 * lacunas maiores mostram reticências.
 */
export function pageWindow(current: number, count: number): PageItem[] {
  if (count <= 1) return [1];
  const keep = new Set<number>([1, count, current - 1, current, current + 1]);
  if (current <= 2) {
    keep.add(2);
    keep.add(3);
  }
  if (current >= count - 1) {
    keep.add(count - 1);
    keep.add(count - 2);
  }
  const pages = [...keep]
    .filter((page) => page >= 1 && page <= count)
    .sort((a, b) => a - b);
  const items: PageItem[] = [];
  pages.forEach((page, index) => {
    const previous = pages[index - 1];
    if (previous !== undefined && page - previous === 2) {
      items.push(previous + 1);
    } else if (previous !== undefined && page - previous > 2) {
      items.push("ellipsis");
    }
    items.push(page);
  });
  return items;
}
