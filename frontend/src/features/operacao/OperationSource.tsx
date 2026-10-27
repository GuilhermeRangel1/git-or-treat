import type { OperationMetadata } from "./contract";
import { formatUpdatedAt } from "./operation-format";

export default function OperationSource({
  source,
}: {
  source?: OperationMetadata["source"];
}) {
  if (!source) return null;
  return (
    <p className="text-xs text-muted">
      {source.is_demo
        ? "Demonstração · dados sintéticos"
        : `Fonte ${source.kind}`}
      {" · "}Atualizado em {formatUpdatedAt(source.updated_at)} UTC
    </p>
  );
}
