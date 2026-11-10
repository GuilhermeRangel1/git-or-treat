/** A cor indica se o valor soma ou subtrai; o número ao lado continua sendo a informação. */
export default function PanoramaDiagnosisBar({
  value,
  max,
  label,
}: {
  value: number;
  max: number;
  label: string;
}) {
  return (
    <div
      role="img"
      aria-label={label}
      className="h-2.5 min-w-0 overflow-hidden rounded-full bg-canvas"
    >
      {value !== 0 && max > 0 ? (
        <div
          className={`h-full min-w-0.5 rounded-full ${value < 0 ? "bg-danger/50" : "bg-success/50"}`}
          style={{ width: `${(Math.abs(value) / max) * 100}%` }}
        />
      ) : null}
    </div>
  );
}
