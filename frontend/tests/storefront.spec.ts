import { expect, test } from "@playwright/test";

// These smoke tests assume the API is seeded (python -m app.seed) and both
// services are running. They exercise the core storefront journey.

test("home page renders hero and navigation", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { name: /furniture that feels like home/i })).toBeVisible();
  await expect(page.getByRole("link", { name: /shop/i }).first()).toBeVisible();
});

test("can browse to the product listing", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("link", { name: /shop the collection/i }).click();
  await expect(page).toHaveURL(/\/products/);
  await expect(page.getByRole("heading", { name: /all furniture/i })).toBeVisible();
});

test("search navigates to results", async ({ page }) => {
  await page.goto("/products?q=sofa");
  await expect(page.getByText(/results for/i)).toBeVisible();
});

test("product detail exposes Product structured data", async ({ page, request }) => {
  // Pull the first product slug from the API, then assert JSON-LD is present.
  const res = await request.get(
    `${process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1"}/catalog/products?page_size=1`,
  );
  const data = await res.json();
  test.skip(data.items.length === 0, "no seeded products");
  const slug = data.items[0].slug;

  await page.goto(`/products/${slug}`);
  const ld = page.locator('script[type="application/ld+json"]');
  await expect(ld).toHaveCount(1);
  const json = JSON.parse((await ld.textContent()) ?? "{}");
  expect(json["@type"]).toBe("Product");
});
