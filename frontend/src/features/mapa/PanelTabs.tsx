import { useRef, type KeyboardEvent } from "react";
import { tabId, tabPanelId } from "./tab-ids";

export type PanelTab = { id: string; label: string };

/**
 * Abas acessíveis (padrão WAI-ARIA): setas, Home e End trocam de aba; só a
 * aba ativa entra na ordem de tabulação.
 */
export default function PanelTabs({
  prefix,
  label,
  tabs,
  active,
  onChange,
}: {
  prefix: string;
  label: string;
  tabs: PanelTab[];
  active: string;
  onChange: (id: string) => void;
}) {
  const buttons = useRef(new Map<string, HTMLButtonElement>());

  function move(event: KeyboardEvent, index: number) {
    const last = tabs.length - 1;
    const next =
      event.key === "ArrowRight"
        ? index === last
          ? 0
          : index + 1
        : event.key === "ArrowLeft"
          ? index === 0
            ? last
            : index - 1
          : event.key === "Home"
            ? 0
            : event.key === "End"
              ? last
              : null;
    if (next === null) return;
    event.preventDefault();
    const target = tabs[next];
    if (!target) return;
    onChange(target.id);
    buttons.current.get(target.id)?.focus();
  }

  return (
    <div
      role="tablist"
      aria-label={label}
      className="flex gap-1 border-b border-border"
    >
      {tabs.map((tab, index) => {
        const selected = tab.id === active;
        return (
          <button
            key={tab.id}
            ref={(element) => {
              if (element) buttons.current.set(tab.id, element);
              else buttons.current.delete(tab.id);
            }}
            type="button"
            role="tab"
            id={tabId(prefix, tab.id)}
            aria-selected={selected}
            aria-controls={tabPanelId(prefix, tab.id)}
            tabIndex={selected ? 0 : -1}
            onClick={() => onChange(tab.id)}
            onKeyDown={(event) => move(event, index)}
            className={`-mb-px min-h-11 cursor-pointer border-b-2 px-3 text-sm transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand ${
              selected
                ? "border-brand font-semibold text-content"
                : "border-transparent text-muted hover:text-content"
            }`}
          >
            {tab.label}
          </button>
        );
      })}
    </div>
  );
}
