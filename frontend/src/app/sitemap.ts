import type { MetadataRoute } from "next";

import { api } from "@/lib/api";

const SITE = process.env.NEXT_PUBLIC_SITE_URL ?? "http://localhost:3000";

export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  const staticRoutes: MetadataRoute.Sitemap = [
    { url: `${SITE}/`, changeFrequency: "daily", priority: 1 },
    { url: `${SITE}/products`, changeFrequency: "daily", priority: 0.9 },
  ];

  try {
    const [products, categories] = await Promise.all([
      api.listProducts({ page_size: 100 }),
      api.listCategories(),
    ]);
    const productRoutes: MetadataRoute.Sitemap = products.items.map((p) => ({
      url: `${SITE}/products/${p.slug}`,
      changeFrequency: "weekly",
      priority: 0.7,
    }));
    const categoryRoutes: MetadataRoute.Sitemap = categories.map((c) => ({
      url: `${SITE}/products?category=${c.slug}`,
      changeFrequency: "weekly",
      priority: 0.6,
    }));
    return [...staticRoutes, ...categoryRoutes, ...productRoutes];
  } catch {
    return staticRoutes;
  }
}
