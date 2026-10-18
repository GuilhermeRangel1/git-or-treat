import { useRef, useState, type CSSProperties, type PointerEvent } from "react";
import "./panorama-artwork.css";

type Point = readonly [number, number];
type FlowStyle = CSSProperties & {
  "--route"?: number;
  "--arrival"?: number;
  "--segment"?: number;
};

// The two paths retain the original Figma artwork's coordinates (220 × 110).
const routePoints: Point[][] = [
  [
    [0, 88],
    [40, 88],
    [66, 30],
    [98, 90],
    [124, 50],
    [150, 74],
    [220, 16],
  ],
  [
    [0, 104],
    [40, 104],
    [66, 46],
    [98, 106],
    [124, 66],
    [150, 90],
    [220, 32],
  ],
];

const routes = routePoints.map((points) => ({
  points,
  path: points
    .map(([x, y], index) => `${index === 0 ? "M" : "L"}${x} ${y}`)
    .join(""),
}));

function nearestRoutePoint([x, y]: Point, points: Point[]) {
  const lengths = points
    .slice(1)
    .map(([endX, endY], index) =>
      Math.hypot(endX - points[index][0], endY - points[index][1]),
    );
  const total = lengths.reduce((sum, length) => sum + length, 0);
  let travelled = 0;
  let nearest = { distance: Infinity, arrival: 0 };

  for (let index = 0; index < lengths.length; index++) {
    const [startX, startY] = points[index];
    const dx = points[index + 1][0] - startX;
    const dy = points[index + 1][1] - startY;
    const fraction = Math.max(
      0,
      Math.min(
        1,
        ((x - startX) * dx + (y - startY) * dy) / lengths[index] ** 2,
      ),
    );
    const distance = Math.hypot(
      x - startX - fraction * dx,
      y - startY - fraction * dy,
    );
    if (distance < nearest.distance) {
      nearest = {
        distance,
        arrival: (travelled + fraction * lengths[index]) / total,
      };
    }
    travelled += lengths[index];
  }
  return nearest;
}

const dots = Array.from({ length: 50 }, (_, index) => {
  const point: Point = [
    38 + (index % 10) * 23,
    10 + Math.floor(index / 10) * 19,
  ];
  const nearby = routes.map(({ points }, route) => ({
    ...nearestRoutePoint(point, points),
    route,
  }));
  const nearest = nearby.reduce((first, next) =>
    first.distance < next.distance ? first : next,
  );
  return { point, spark: nearest.distance < 10 ? nearest : null };
});

export default function PanoramaArtwork() {
  const [cycle, setCycle] = useState(0);
  const svgRef = useRef<SVGSVGElement>(null);

  function replay(event: PointerEvent<HTMLDivElement>) {
    if (
      event.pointerType !== "mouse" ||
      window.matchMedia("(prefers-reduced-motion: reduce)").matches
    )
      return;
    if (
      svgRef.current
        ?.getAnimations({ subtree: true })
        .some(({ playState }) => playState === "running")
    )
      return;
    setCycle((previous) => previous + 1);
  }

  return (
    <div
      aria-hidden="true"
      className="energy-flow absolute -bottom-3 left-[calc(50%_+_72px)] z-20 hidden aspect-[127/60] w-[clamp(180px,21vw,290px)] lg:block xl:-bottom-4"
      onPointerEnter={replay}
    >
      <svg
        key={cycle}
        ref={svgRef}
        width="100%"
        height="100%"
        viewBox="0 0 254 120"
        fill="none"
        focusable="false"
        data-phase={cycle === 0 ? "intro" : "replay"}
        className="energy-flow__drawing block"
      >
        <g className="energy-flow__grid">
          {dots.map(({ point: [cx, cy] }, index) => (
            <circle key={index} cx={cx} cy={cy} r={1.4} />
          ))}
        </g>
        {routes.map(({ path }, route) => (
          <g key={path} style={{ "--route": route } as FlowStyle}>
            <path d={path} pathLength={1} className="energy-flow__line" />
            {[0.14, 0.065, 0.014].map((segment, index) => (
              <path
                key={segment}
                d={path}
                pathLength={1}
                style={{ "--segment": segment } as FlowStyle}
                className={`energy-flow__pulse energy-flow__pulse--${index}`}
              />
            ))}
          </g>
        ))}
        <g className="energy-flow__nodes">
          <circle cx={66} cy={30} r={2.8} />
          <circle cx={124} cy={66} r={2.8} />
          <circle cx={150} cy={74} r={2.8} />
          <circle cx={220} cy={16} r={3} className="energy-flow__terminal" />
        </g>
        {dots.map(
          ({ point: [cx, cy], spark }, index) =>
            spark && (
              <circle
                key={index}
                cx={cx}
                cy={cy}
                r={2.2}
                className="energy-flow__spark"
                style={
                  {
                    "--route": spark.route,
                    "--arrival": spark.arrival,
                  } as FlowStyle
                }
              />
            ),
        )}
      </svg>
    </div>
  );
}
