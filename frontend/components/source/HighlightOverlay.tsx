import { scaleRegion } from "@/lib/geometry";
import type { Region } from "@/lib/types";

/** Amber boxes over the rendered page marking exactly the words the model read (FR-013). */
export function HighlightOverlay({ regions, page, scale }: { regions: Region[]; page: number; scale: number }) {
  const onPage = regions.filter((region) => region.page === page);
  if (onPage.length === 0) return null;
  return (
    <div role="img" aria-label="Highlighted passage" className="pointer-events-none absolute inset-0">
      {onPage.map((region, index) => {
        const box = scaleRegion(region, scale);
        return (
          <div
            key={index}
            data-region
            className="absolute rounded-[2px] bg-highlight/60 mix-blend-multiply outline outline-1 outline-amber/70"
            style={{ left: `${box.left}px`, top: `${box.top}px`, width: `${box.width}px`, height: `${box.height}px` }}
          />
        );
      })}
    </div>
  );
}
