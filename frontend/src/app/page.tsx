import Link from "next/link";

import { ProductCard } from "@/components/ProductCard";
import { api } from "@/lib/api";
import type { Category, ProductListItem } from "@/lib/types";

// Home is SEO-critical: render on the server and revalidate periodically (ISR).
export const revalidate = 120;

export default async function HomePage() {
  let categories: Category[] = [];
  let featured: ProductListItem[] = [];
  try {
    categories = await api.listCategories();
    featured = (await api.listProducts({ sort: "newest", page_size: 8 })).items;
  } catch {
    // Backend may be unavailable during a cold build; render an empty shell.
  }

  return (
    <div className="space-y-14">
      <section className="card overflow-hidden bg-gradient-to-br from-brand-100 to-brand-50 p-8 md:p-14">
        <div className="max-w-xl">
          <h1 className="text-3xl font-bold leading-tight text-brand-900 md:text-5xl">
            Furniture that feels like home.
          </h1>
          <p className="mt-4 text-brand-600">
            Thoughtfully designed sofas, beds and tables — built to last, delivered to your door.
          </p>
          <Link href="/products" className="btn-primary mt-6">
            Shop the collection
          </Link>
        </div>
      </section>

      {categories.length > 0 && (
        <section>
          <h2 className="mb-4 text-xl font-semibold">Shop by room</h2>
          <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 md:grid-cols-5">
            {categories.map((c) => (
              <Link
                key={c.id}
                href={`/products?category=${c.slug}`}
                className="card flex items-center justify-center p-6 text-center font-medium hover:bg-brand-100"
              >
                {c.name}
              </Link>
            ))}
          </div>
        </section>
      )}

      <section>
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-xl font-semibold">New arrivals</h2>
          <Link href="/products" className="text-sm text-brand-600 hover:underline">
            View all →
          </Link>
        </div>
        {featured.length > 0 ? (
          <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
            {featured.map((p) => (
              <ProductCard key={p.id} product={p} />
            ))}
          </div>
        ) : (
          <p className="text-brand-500">
            No products yet. Seed the backend with <code>python -m app.seed</code>.
          </p>
        )}
      </section>
    </div>
  );
}
