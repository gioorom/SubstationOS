"use client";

import { AssetCard } from "./AssetCard";

import type { CommissioningAsset } from "@/types/commissioning";

interface AssetGridProps {
  assets: CommissioningAsset[];
  onSelect?: (asset: CommissioningAsset) => void;
}

export function AssetGrid({
  assets,
  onSelect,
}: AssetGridProps) {
  return (
    <section
      className="
        grid
        gap-6
        grid-cols-1
        md:grid-cols-2
        xl:grid-cols-3
      "
    >
      {assets.map((asset) => (
        <AssetCard
          key={asset.id}
          asset={asset}
          onSelect={onSelect}
        />
      ))}
    </section>
  );
}