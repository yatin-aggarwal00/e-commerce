import type { Metadata } from "next";

import { Filters } from "@/components/Filters";
import { Pagination } from "@/components/Pagination";
import { ProductCard } from "@/components/ProductCard";
import { api, type ProductQuery } from "@/lib/api";
import type { Category, Facets, Page as PageT, ProductListItem } from "@/lib/types";

export const metadata: Metadata = {
  title: "Shop all furniture",
  description: "Browse, filter and sort our full furniture catalogue.",
};

type SearchParams = Record<string, string | string[] | undefined>;

function one(v: string | string[] | undefined): string | undefined {
  return Array.isArray(v) ? v[0] : v;
}

export default async function ProductsPage({
  searchParams,
}: {
  searchParams: SearchParams;
}) {
  const page = Number(one(searchParams.page) ?? "1") || 1;
  const query: ProductQuery = {
    q: one(searchParams.q),
    category: one(searchParams.category),
    room_type: one(searchParams.room_type),
    material: one(searchParams.material),
    color: one(searchParams.color),
    price_min: one(searchParams.price_min) ? Number(one(searchParams.price_min)) : undefined,
    price_max: one(searchParams.price_max) ? Number(one(searchParams.price_max)) : undefined,
    in_stock: one(searchParams.in_stock) === "true" || undefined,
    sort: one(searchParams.sort),
    page,
    page_size: 12,
  };

  let results: PageT<ProductListItem> = { items: [], total: 0, page, page_size: 12 };
  let facets: Facets = {
    room_types: [],
    materials: [],
    colors: [],
    price_min_cents: 0,
    price_max_cents: 0,
  };
  let categories: Category[] = [];
  try {
    [results, facets, categories] = await Promise.all([
      api.listProducts(query),
      api.getFacets(),
      api.listCategories(),
    ]);
  } catch {
    /* backend unreachable — render empty state */
  }

  const makeHref = (p: number) => {
    const sp = new URLSearchParams();
    Object.entries(searchParams).forEach(([k, v]) => {
      const val = one(v);
      if (val && k !== "page") sp.set(k, val);
    });
    sp.set("page", String(p));
    return `/products?${sp.toString()}`;
  };

  return (
    <div className="grid gap-8 md:grid-cols-[220px_1fr]">
      <Filters facets={facets} categories={categories} />

      <section>
        <div className="mb-4 flex items-center justify-between">
          <h1 className="text-xl font-semibold">
            {query.q ? `Results for “${query.q}”` : "All furniture"}
          </h1>
          <span className="text-sm text-brand-500">{results.total} items</span>
        </div>

        {results.items.length > 0 ? (
          <div className="grid grid-cols-2 gap-4 lg:grid-cols-3">
            {results.items.map((p) => (
              <ProductCard key={p.id} product={p} />
            ))}
          </div>
        ) : (
          <p className="py-16 text-center text-brand-500">
            No products match your filters.
          </p>
        )}

        <Pagination
          page={results.page}
          total={results.total}
          pageSize={results.page_size}
          makeHref={makeHref}
        />
      </section>
    </div>
  );
}
