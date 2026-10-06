"use client";

import Image from "next/image";
import { useState } from "react";

import type { ProductImage } from "@/lib/types";

export function Gallery({ images, alt }: { images: ProductImage[]; alt: string }) {
  const [active, setActive] = useState(0);
  if (images.length === 0) {
    return <div className="flex aspect-square items-center justify-center rounded-lg bg-brand-100 text-brand-300">No image</div>;
  }
  return (
    <div className="space-y-3">
      <div className="relative aspect-square overflow-hidden rounded-lg bg-brand-100">
        <Image
          src={images[active].url}
          alt={images[active].alt || alt}
          fill
          priority
          sizes="(max-width: 768px) 100vw, 50vw"
          className="object-cover"
        />
      </div>
      {images.length > 1 && (
        <div className="flex gap-2">
          {images.map((img, i) => (
            <button
              key={img.id}
              onClick={() => setActive(i)}
              aria-label={`View image ${i + 1}`}
              className={`relative h-16 w-16 overflow-hidden rounded-md border-2 ${
                i === active ? "border-brand-600" : "border-transparent"
              }`}
            >
              <Image src={img.url} alt={img.alt || alt} fill sizes="64px" className="object-cover" />
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
