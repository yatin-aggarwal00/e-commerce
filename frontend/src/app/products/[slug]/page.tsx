import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";

import { AddToCart } from "@/components/AddToCart";
import { Gallery } from "@/components/Gallery";
import { api, ApiError } from "@/lib/api";
import { formatPrice } from "@/lib/format";
import type { ProductDetail } from "@/lib/types";

export const revalidate = 120;

async function fetchProduct(slug: string): Promise<ProductDetail | null> {
  try {
    return await api.getProduct(slug);
  } catch (e) {
    if (e instanceof ApiError && e.status === 404) return null;
    throw e;
  }
}

export async function generateMetadata({
  params,
}: {
  params: { slug: string };
}): Promise<Metadata> {
  const product = await fetchProduct(params.slug);
  if (!product) return { title: "Product not found" };
  const desc = product.description.slice(0, 160);
  return {
    title: product.name,
    description: desc,
    openGraph: {
      title: product.name,
      description: desc,
      images: product.images[0] ? [product.images[0].url] : [],
    },
  };
}

export default async function ProductPage({ params }: { params: { slug: string } }) {
  const product = await fetchProduct(params.slug);
  if (!product) notFound();

  const prices = product.variants.map((v) => v.price_cents);
  const minPrice = prices.length ? Math.min(...prices) : null;
  const currency = product.variants[0]?.currency ?? "usd";
  const anyInStock = product.variants.some((v) => v.in_stock);

  // Product structured data for rich search results (SEO acceptance criterion).
  const jsonLd = {
    "@context": "https://schema.org",
    "@type": "Product",
    name: product.name,
    description: product.description,
    image: product.images.map((i) => i.url),
    category: product.category?.name,
    material: product.material || undefined,
    offers: {
      "@type": "AggregateOffer",
      priceCurrency: currency.toUpperCase(),
      lowPrice: minPrice != null ? (minPrice / 100).toFixed(2) : undefined,
      offerCount: product.variants.length,
      availability: anyInStock
        ? "https://schema.org/InStock"
        : "https://schema.org/OutOfStock",
    },
  };

  return (
    <div>
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }}
      />

      <nav className="mb-6 text-sm text-brand-500">
        <Link href="/products" className="hover:underline">
          Shop
        </Link>
        {product.category && (
          <>
            {" / "}
            <Link href={`/products?category=${product.category.slug}`} className="hover:underline">
              {product.category.name}
            </Link>
          </>
        )}
        {" / "}
        <span className="text-brand-700">{product.name}</span>
      </nav>

      <div className="grid gap-10 md:grid-cols-2">
        <Gallery images={product.images} alt={product.name} />

        <div>
          <h1 className="text-2xl font-bold md:text-3xl">{product.name}</h1>
          <p className="mt-2 text-2xl font-semibold text-brand-700">
            {formatPrice(minPrice, currency)}
          </p>
          <span
            className={`badge mt-3 ${anyInStock ? "bg-emerald-100 text-emerald-800" : "bg-gray-200 text-gray-700"}`}
          >
            {anyInStock ? "In stock" : "Out of stock"}
          </span>

          <p className="mt-5 whitespace-pre-line text-brand-700">{product.description}</p>

          <dl className="mt-5 grid grid-cols-2 gap-2 text-sm">
            {product.material && (
              <>
                <dt className="text-brand-400">Material</dt>
                <dd>{product.material}</dd>
              </>
            )}
            {product.room_type && (
              <>
                <dt className="text-brand-400">Room</dt>
                <dd>{product.room_type}</dd>
              </>
            )}
            {product.variants[0]?.dimensions && (
              <>
                <dt className="text-brand-400">Dimensions</dt>
                <dd>{product.variants[0].dimensions}</dd>
              </>
            )}
          </dl>

          <div className="mt-8">
            <AddToCart variants={product.variants} />
          </div>
        </div>
      </div>
    </div>
  );
}
