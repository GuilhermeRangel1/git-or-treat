import { useEffect, useRef } from "react";

type Props = {
  theme: "light" | "dark";
  logoSrc: string;
  reducedMotion: boolean;
};

type Piece = {
  x: number;
  y: number;
  originX: number;
  originY: number;
  delay: number;
  rotation: number;
  color: string;
};

const clamp = (value: number) => Math.max(0, Math.min(1, value));
const ease = (value: number) => 1 - (1 - value) ** 3;
const paths = [
  [
    [-410, -145],
    [-270, -145],
    [-210, -85],
    [-150, -85],
  ],
  [
    [-385, 25],
    [-265, 25],
    [-215, -25],
    [-150, -25],
  ],
  [
    [-350, 165],
    [-245, 165],
    [-185, 105],
    [-140, 105],
  ],
  [
    [-145, -230],
    [-145, -165],
    [-95, -115],
  ],
  [
    [410, -150],
    [285, -150],
    [215, -80],
    [150, -80],
  ],
  [
    [390, 40],
    [275, 40],
    [225, -10],
    [150, -10],
  ],
  [
    [350, 180],
    [255, 180],
    [185, 110],
    [140, 110],
  ],
  [
    [135, 235],
    [135, 165],
    [90, 120],
  ],
];

function sampleMark(mark: HTMLImageElement): Piece[] {
  const sampler = document.createElement("canvas");
  sampler.width = sampler.height = 144;
  const ctx = sampler.getContext("2d", { willReadFrequently: true });
  if (!ctx) return [];
  ctx.drawImage(mark, 0, 0, 144, 144);
  const pixels = ctx.getImageData(0, 0, 144, 144).data;
  const pieces: Piece[] = [];
  let seed = 360;
  const random = () => {
    seed = (seed * 16807) % 2147483647;
    return (seed - 1) / 2147483646;
  };
  for (let y = 0; y < 144; y += 3) {
    for (let x = 0; x < 144; x += 3) {
      const i = (y * 144 + x) * 4;
      if (pixels[i + 3] < 110) continue;
      const angle = random() * Math.PI * 2;
      const distance = 200 + random() * 240;
      pieces.push({
        x: (x - 72) * 1.8,
        y: (y - 72) * 1.8,
        originX: Math.cos(angle) * distance,
        originY: Math.sin(angle) * distance * 0.63,
        delay: 600 + random() * 1200,
        rotation: (random() - 0.5) * Math.PI,
        color: `rgb(${pixels[i]}, ${pixels[i + 1]}, ${pixels[i + 2]})`,
      });
    }
  }
  return pieces;
}

/** A rede converge em um mosaico amostrado da marca SVG original, sem redesenhá-la. */
export default function EnergyArtwork({
  theme,
  logoSrc,
  reducedMotion,
}: Props) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const timeline = useRef({ elapsed: 0 });
  const cursorRef = useRef({ x: 0, y: 0, targetX: 0, targetY: 0 });

  useEffect(() => {
    const canvas = canvasRef.current;
    const ctx = canvas?.getContext("2d");
    if (!canvas) return;
    if (!ctx) {
      canvas.dataset.unavailable = "true";
      return;
    }
    if (reducedMotion)
      timeline.current.elapsed = Math.max(5000, timeline.current.elapsed);

    let disposed = false;
    let frame: number | null = null;
    let previous: number | null = null;
    let lastPaint = 0;
    let width = 0;
    let height = 0;
    let pieces: Piece[] = [];
    let ready = false;
    const cursor = cursorRef.current;
    if (reducedMotion)
      Object.assign(cursor, { x: 0, y: 0, targetX: 0, targetY: 0 });
    const styles = getComputedStyle(canvas);
    const wire = styles.getPropertyValue("--art-wire").trim();
    const goiaba = styles.getPropertyValue("--accent-goiaba").trim();
    const pistache = styles.getPropertyValue("--accent-pistache").trim();

    const paint = () => {
      if (!width || !height || !ready) return;
      const elapsed = timeline.current.elapsed;
      const scale = Math.min(width / 850, height / 440);
      ctx.clearRect(0, 0, width, height);
      ctx.save();
      ctx.translate(width / 2, height / 2);
      ctx.scale(scale, scale);

      // Trilhas angulares e nós: uma rede abstrata, sem dados operacionais.
      const networkAlpha = reducedMotion
        ? 0.28
        : 0.18 + 0.28 * (1 - clamp((elapsed - 1100) / 2300));
      for (let i = 0; i < paths.length; i++) {
        const path = paths[i];
        ctx.globalAlpha = networkAlpha;
        ctx.strokeStyle = wire;
        ctx.lineWidth = 1;
        ctx.beginPath();
        path.forEach(([x, y], index) =>
          index ? ctx.lineTo(x, y) : ctx.moveTo(x, y),
        );
        ctx.stroke();

        for (const [x, y] of path.slice(0, -1)) {
          ctx.fillStyle = i % 3 ? goiaba : pistache;
          ctx.fillRect(x - 2.5, y - 2.5, 5, 5);
          ctx.strokeRect(x - 6, y - 6, 12, 12);
        }

        if (!reducedMotion) {
          const travel = ((elapsed / 3800 + i * 0.16) % 1) * (path.length - 1);
          const segment = Math.floor(travel);
          const t = travel - segment;
          const [x0, y0] = path[segment];
          const [x1, y1] = path[segment + 1];
          ctx.globalAlpha = 0.75;
          ctx.fillStyle = i % 3 ? goiaba : pistache;
          ctx.beginPath();
          ctx.arc(x0 + (x1 - x0) * t, y0 + (y1 - y0) * t, 2.5, 0, Math.PI * 2);
          ctx.fill();
        }
      }

      ctx.globalAlpha = 1;
      const breathing = reducedMotion
        ? 1
        : 1 + Math.sin(elapsed / 2300) * 0.012;
      ctx.translate(cursor.x, cursor.y);
      ctx.scale(breathing, breathing);
      for (const piece of pieces) {
        const progress = reducedMotion
          ? 1
          : clamp((elapsed - piece.delay) / 1500);
        if (progress <= 0) continue;
        const eased = ease(progress);
        const x = piece.originX + (piece.x - piece.originX) * eased;
        const y = piece.originY + (piece.y - piece.originY) * eased;
        ctx.save();
        ctx.translate(x, y);
        ctx.rotate(piece.rotation * (1 - eased));
        ctx.globalAlpha = clamp(progress * 2) * (0.84 + 0.16 * eased);
        ctx.fillStyle = piece.color;
        const side = 4.2 * (0.5 + eased * 0.5);
        ctx.beginPath();
        ctx.roundRect(-side / 2, -side / 2, side, side, 1.1);
        ctx.fill();
        ctx.restore();
      }

      // Um único pulso de fechamento, suave o bastante para não virar um flash.
      const arrival = (elapsed - 3150) / 1100;
      if (!reducedMotion && arrival >= 0 && arrival <= 1) {
        ctx.globalAlpha = (1 - arrival) * 0.26;
        ctx.strokeStyle = pistache;
        ctx.lineWidth = 1.5;
        ctx.beginPath();
        ctx.arc(0, 0, 110 + ease(arrival) * 110, 0, Math.PI * 2);
        ctx.stroke();
      }
      ctx.restore();
      canvas.dataset.phase = elapsed >= 3400 ? "rest" : "assembling";
    };

    const tick = (now: number) => {
      frame = null;
      if (previous !== null)
        timeline.current.elapsed += Math.min(now - previous, 100);
      previous = now;
      cursor.x += (cursor.targetX - cursor.x) * 0.04;
      cursor.y += (cursor.targetY - cursor.y) * 0.04;
      if (timeline.current.elapsed < 4000 || now - lastPaint >= 40) {
        paint();
        lastPaint = now;
      }
      if (!disposed && !reducedMotion && !document.hidden)
        frame = requestAnimationFrame(tick);
    };

    const stop = () => {
      if (frame !== null) cancelAnimationFrame(frame);
      frame = null;
      previous = null;
    };
    const start = () => {
      paint();
      if (ready && frame === null && !document.hidden && !reducedMotion)
        frame = requestAnimationFrame(tick);
    };
    const measure = () => {
      const box = canvas.getBoundingClientRect();
      width = box.width;
      height = box.height;
      const density = Math.min(devicePixelRatio || 1, 2);
      canvas.width = Math.max(1, Math.round(width * density));
      canvas.height = Math.max(1, Math.round(height * density));
      ctx.setTransform(density, 0, 0, density, 0, 0);
      start();
    };
    const visibility = () => (document.hidden ? stop() : start());
    const pointer = (event: PointerEvent) => {
      if (reducedMotion || event.pointerType !== "mouse") return;
      const box = canvas.getBoundingClientRect();
      cursor.targetX = ((event.clientX - box.left) / box.width - 0.5) * 14;
      cursor.targetY = ((event.clientY - box.top) / box.height - 0.5) * 14;
    };
    const leave = () => {
      cursor.targetX = 0;
      cursor.targetY = 0;
    };
    const observer = new ResizeObserver(measure);
    observer.observe(canvas);
    canvas.addEventListener("pointermove", pointer, { passive: true });
    canvas.addEventListener("pointerleave", leave);
    document.addEventListener("visibilitychange", visibility);

    const mark = new Image();
    mark.onload = () => {
      if (disposed) return;
      pieces = sampleMark(mark);
      if (pieces.length === 0) {
        canvas.dataset.unavailable = "true";
        return;
      }
      ready = true;
      measure();
    };
    mark.onerror = () => {
      if (disposed) return;
      canvas.dataset.unavailable = "true";
    };
    mark.src = logoSrc;

    return () => {
      disposed = true;
      stop();
      observer.disconnect();
      canvas.removeEventListener("pointermove", pointer);
      canvas.removeEventListener("pointerleave", leave);
      document.removeEventListener("visibilitychange", visibility);
      mark.onload = null;
      mark.onerror = null;
    };
  }, [theme, logoSrc, reducedMotion]);

  return (
    <canvas ref={canvasRef} className="energy-canvas" aria-hidden="true" />
  );
}
