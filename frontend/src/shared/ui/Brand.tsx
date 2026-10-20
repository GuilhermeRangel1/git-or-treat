import { useTheme } from "@/shared/theme/useTheme";
import logoLight from "./assets/grid360-light.svg";
import logoDark from "./assets/grid360-dark.svg";

export default function Brand() {
  const { theme } = useTheme();
  return (
    <div className="flex h-10 shrink-0 items-center gap-2.5 text-content">
      <img
        src={theme === "dark" ? logoDark : logoLight}
        alt=""
        width={32}
        height={32}
        className="size-8 shrink-0"
      />
      <span className="font-heading text-[32px] leading-10 font-semibold tracking-[-0.64px]">
        grid360
      </span>
    </div>
  );
}
