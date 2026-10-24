// Highlight geometry: regions are in PDF points (origin top-left, research R4); the page is
// drawn `scale` pixels per point.

import type { Region } from "@/lib/types";

export interface Box {
  left: number;
  top: number;
  width: number;
  height: number;
}

/** A region's position and size in pixels on a page drawn at `scale` pixels per point. */
export function scaleRegion(region: Region, scale: number): Box {
  return {
    left: region.x0 * scale,
    top: region.y0 * scale,
    width: (region.x1 - region.x0) * scale,
    height: (region.y1 - region.y0) * scale,
  };
}
