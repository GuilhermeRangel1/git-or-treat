import PanoramaArtwork from "./PanoramaArtwork";

export default function PanoramaPage() {
  return (
    <div className="relative flex items-start gap-6">
      <div className="relative z-10 min-w-0 flex-1">
        <h1 className="font-heading text-[26px] leading-[34px] font-semibold lg:w-fit lg:text-[32px] lg:leading-10 lg:tracking-[-0.64px]">
          Sua rede, em perspectiva.
        </h1>
        <p className="mt-2 text-sm leading-[22px] text-muted">
          Um panorama da operação comercial, do atendimento e da continuidade.
        </p>
      </div>
      <PanoramaArtwork />
    </div>
  );
}
