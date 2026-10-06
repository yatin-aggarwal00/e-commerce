import Image from "next/image";
import Link from "next/link";

import { formatPrice } from "@/lib/format";
import type { ProductListItem } from "@/lib/types";

export function ProductCard({ product }: { product: ProductListItem }) {
  return (
    <Link
      href={`/products/${product.slug}`}
      className="card group overflow-hidden transition-shadow hover:shadow-md"
    >
      <div className="relative aspect-[4/3] bg-brand-100">
        {product.thumbnail ? (
          <Image
            src={product.thumbnail}
            alt={product.name}
            fill
            sizes="(max-width: 768px) 50vw, 25vw"
            className="object-cover transition-transform duration-300 group-hover:scale-105"
          />
        ) : (
          <div className="flex h-full items-center justify-center text-brand-300">No image</div>
        )}
        {!product.in_stock && (
          <span className="badge absolute left-2 top-2 bg-gray-800/80 text-white">
            Out of stock
          </span>
        )}
      </div>
      <div className="p-4">
        <h3 className="line-clamp-1 font-medium text-brand-900">{product.name}</h3>
        <p className="mt-0.5 text-xs text-brand-400">
          {[product.room_type, product.material].filter(Boolean).join(" · ")}
        </p>
        <p className="mt-2 font-semibold text-brand-700">
          {formatPrice(product.min_price_cents, product.currency)}
        </p>
      </div>
    </Link>
  );
}
