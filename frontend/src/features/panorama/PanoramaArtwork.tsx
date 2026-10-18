import { useTheme } from "@/shared/theme/useTheme";
import energyLight from "./assets/energy-light.svg";
import energyDark from "./assets/energy-dark.svg";
import dots0Light from "./assets/dots-0-light.svg";
import dots1Light from "./assets/dots-1-light.svg";
import dots2Light from "./assets/dots-2-light.svg";
import dots3Light from "./assets/dots-3-light.svg";
import dots0Dark from "./assets/dots-0-dark.svg";
import dots1Dark from "./assets/dots-1-dark.svg";
import dots2Dark from "./assets/dots-2-dark.svg";
import dots3Dark from "./assets/dots-3-dark.svg";

const artwork = {
  light: {
    energy: energyLight,
    dots: [dots0Light, dots1Light, dots2Light, dots3Light, dots0Light],
  },
  dark: {
    energy: energyDark,
    dots: [dots0Dark, dots1Dark, dots2Dark, dots3Dark, dots0Dark],
  },
};

export default function PanoramaArtwork() {
  const { theme } = useTheme();
  const { energy, dots } = artwork[theme];
  return (
    <div
      aria-hidden="true"
      className="pointer-events-none relative hidden h-[110px] w-[254px] shrink-0 lg:block"
    >
      <div className="absolute top-0 right-0 flex h-[120px] w-56 flex-col gap-4 p-2 opacity-35">
        {dots.map((src, index) => (
          <img
            key={index}
            src={src}
            alt=""
            width={208}
            height={3}
            className="h-[3px] w-52 shrink-0"
          />
        ))}
      </div>
      <img
        src={energy}
        alt=""
        width={220}
        height={110}
        className="relative h-[110px] w-[220px]"
      />
    </div>
  );
}
