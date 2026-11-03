import { Component, type ReactNode } from "react";

/** Renderer failure must not remove the validated table or response. */
export default class ChartBoundary extends Component<
  { children: ReactNode },
  { failed: boolean }
> {
  state = { failed: false };
  static getDerivedStateFromError() {
    return { failed: true };
  }
  render() {
    return this.state.failed ? (
      <p role="status" className="mt-4 text-sm text-muted">
        Não foi possível desenhar o gráfico. Os valores continuam disponíveis na
        tabela e no CSV.
      </p>
    ) : (
      this.props.children
    );
  }
}
